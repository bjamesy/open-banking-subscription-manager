"""Linked accounts with institution and sync status (architecture §2.5)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import (
    get_banking_provider,
    get_current_user,
    get_db,
    get_session_factory,
)
from subtrack.db.models import Account, Item, RescanJob, User
from subtrack.ingestion.sync import rescan_items
from subtrack.providers.base import BankingProvider

logger = logging.getLogger(__name__)

router = APIRouter()


class AccountOut(BaseModel):
    id: int
    item_id: int
    name: str
    mask: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    currency: Optional[str] = None
    institution_name: Optional[str] = None
    item_status: str
    error: Optional[str] = None
    last_synced_at: Optional[datetime] = None


class RescanJobOut(BaseModel):
    id: int
    status: str
    items_synced: Optional[int] = None
    items_failed: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


@router.get("")
def list_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AccountOut]:
    rows = db.execute(
        select(Account, Item)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user.id)
        .order_by(Account.id)
    ).all()
    return [
        AccountOut(
            id=account.id,
            item_id=item.id,
            name=account.name,
            mask=account.mask,
            type=account.type,
            subtype=account.subtype,
            currency=account.currency,
            institution_name=item.institution_name,
            item_status=item.status,
            error=item.error,
            last_synced_at=item.last_synced_at,
        )
        for account, item in rows
    ]


class ReconnectOut(BaseModel):
    item_id: int
    item_status: str


@router.post("/{item_id}/reconnect")
def reconnect_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconnectOut:
    """Clear an Item's error state after the user completes Link update mode
    (architecture §5.2/§2.1) — the existing access_token remains valid once
    re-authenticated, so this just resets status; sync itself is left to the
    existing re-scan flow."""
    item = db.scalar(select(Item).where(Item.id == item_id, Item.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    item.status = "active"
    item.error = None
    db.commit()
    return ReconnectOut(item_id=item.id, item_status=item.status)


@router.post("/rescan", status_code=202)
def start_rescan(
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    provider: BankingProvider = Depends(get_banking_provider),
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
) -> RescanJobOut:
    """Kick off a manual re-sync of all the user's active bank connections
    plus detection, as an in-process background task (architecture §5.2 —
    sync is one-shot at link time by default; this is the on-demand
    alternative). Returns immediately with a job to poll via
    GET /accounts/rescan/{job_id}."""
    existing = db.scalar(
        select(RescanJob).where(
            RescanJob.user_id == user.id,
            RescanJob.status.in_(["pending", "running"]),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="a rescan is already in progress")

    job = RescanJob(user_id=user.id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    background.add_task(_run_rescan, job.id, provider, session_factory)
    return RescanJobOut.model_validate(job)


@router.get("/rescan/{job_id}")
def get_rescan_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RescanJobOut:
    job = db.scalar(
        select(RescanJob).where(RescanJob.id == job_id, RescanJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="rescan job not found")
    return RescanJobOut.model_validate(job)


def _run_rescan(job_id: int, provider: BankingProvider, session_factory) -> None:
    """Background task body: owns its own DB session, since the request's
    session closes once the response is sent."""
    session = session_factory()
    try:
        job = session.get(RescanJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        items = list(
            session.scalars(
                select(Item).where(
                    Item.user_id == job.user_id, Item.status == "active"
                )
            )
        )
        synced, failed = rescan_items(session, items, provider)

        job.status = "done"
        job.items_synced = synced
        job.items_failed = failed
        job.finished_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("rescan job %s failed", job_id)
        try:
            job = session.get(RescanJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:500]
                job.finished_at = datetime.now(timezone.utc)
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()
