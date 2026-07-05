"""Inbound Plaid webhooks (architecture §2.2, §5.2).

All requests must carry a valid Plaid-Verification JWT (rejected with 400
otherwise; PLAID_VERIFY_WEBHOOKS=false disables this for local testing only).
Transaction-update webhooks enqueue a background sync + detection run for the
affected Item.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select

from subtrack.config import get_settings
from subtrack.db.base import get_sessionmaker
from subtrack.db.models import Item
from subtrack.detection.engine import run_detection
from subtrack.ingestion.sync import sync_item
from subtrack.providers.factory import get_provider

logger = logging.getLogger(__name__)

router = APIRouter()

# Plaid webhook codes that mean new/updated transactions are available.
SYNC_CODES = {
    "SYNC_UPDATES_AVAILABLE",
    "INITIAL_UPDATE",
    "HISTORICAL_UPDATE",
    "DEFAULT_UPDATE",
}


@router.post("/plaid")
async def plaid_webhook(request: Request, background: BackgroundTasks) -> dict:
    body = await request.body()

    if get_settings().plaid_verify_webhooks:
        from subtrack.providers.plaid.webhook import verify_plaid_webhook

        header = request.headers.get("plaid-verification")
        if not header or not verify_plaid_webhook(body, header):
            raise HTTPException(status_code=400, detail="invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    webhook_code = payload.get("webhook_code")
    plaid_item_id = payload.get("item_id")

    if webhook_code in SYNC_CODES and plaid_item_id:
        background.add_task(_sync_and_detect, plaid_item_id)
        return {"status": "sync_enqueued", "webhook_code": webhook_code}

    return {"status": "ignored", "webhook_code": webhook_code}


def _sync_and_detect(plaid_item_id: str) -> None:
    """Background task: sync the Item's transactions, then run detection."""
    session = get_sessionmaker()()
    try:
        item = session.scalar(select(Item).where(Item.plaid_item_id == plaid_item_id))
        if item is None:
            logger.warning("webhook for unknown plaid_item_id %s", plaid_item_id)
            return
        sync_item(session, item, get_provider())
        run_detection(session, item.user_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("webhook-triggered sync failed for item %s", plaid_item_id)
    finally:
        session.close()
