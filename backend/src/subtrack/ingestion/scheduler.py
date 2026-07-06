"""Polling fallback (architecture §2.2, §5.2).

Webhooks are the primary sync trigger; this scheduled poll is the correctness
guarantee for Items whose webhooks were missed (app downtime, delivery
failure). Runs in-process via APScheduler — safe under the single-instance
deployment assumption (§6.3); move out-of-process (Celery/Redis) if the app
ever runs multiple instances.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from subtrack.config import get_settings
from subtrack.db.base import get_sessionmaker
from subtrack.detection.engine import run_detection
from subtrack.ingestion.sync import sync_item
from subtrack.providers.base import BankingProvider
from subtrack.providers.factory import get_provider

logger = logging.getLogger(__name__)

_scheduler = None


def poll_all_items(provider: Optional[BankingProvider] = None) -> int:
    """Sync every active Item and re-run detection per affected user.

    Each Item is synced in its own transaction; one failing Item (e.g. an
    expired access token) doesn't block the rest. Returns the number of Items
    successfully synced.
    """
    from subtrack.db.models import Item

    provider = provider or get_provider()
    session = get_sessionmaker()()
    synced = 0
    try:
        items = list(session.scalars(select(Item).where(Item.status == "active")))
        user_ids = set()
        for item in items:
            try:
                sync_item(session, item, provider)
                user_ids.add(item.user_id)
                synced += 1
            except Exception:
                session.rollback()
                logger.exception("poll sync failed for item %s", item.plaid_item_id)

        for user_id in user_ids:
            try:
                run_detection(session, user_id)
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("poll detection failed for user %s", user_id)
    finally:
        session.close()
    logger.info("poll complete: %d/%d items synced", synced, len(items))
    return synced


def start_scheduler():
    """Start the in-process poll scheduler. No-op if disabled (interval 0)."""
    global _scheduler
    hours = get_settings().sync_poll_interval_hours
    if hours <= 0 or _scheduler is not None:
        return None

    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(poll_all_items, "interval", hours=hours, id="sync-poll")
    _scheduler.start()
    logger.info("sync poll scheduler started (every %dh)", hours)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
