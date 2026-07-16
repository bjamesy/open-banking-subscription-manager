"""Privacy-notice consent (architecture §6.8).

Consent is an append-only log, not a mutable flag — each POST adds a new
ConsentRecord, so there's a timestamped record of what was actually agreed
to and when. Status checks are scoped to CURRENT_VERSION specifically: an
older grant doesn't count as current consent, which is what makes a version
bump meaningful if the disclosure text changes materially.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_current_user, get_db
from subtrack.db.models import ConsentRecord, User

router = APIRouter()

# Bump on any material change to the disclosure text shown in ConnectBank.tsx.
CURRENT_VERSION = "2026-07"


class ConsentStatus(BaseModel):
    consented: bool
    version: Optional[str] = None
    granted_at: Optional[datetime] = None


@router.get("")
def get_consent_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ConsentStatus:
    record = db.scalar(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user.id, ConsentRecord.version == CURRENT_VERSION)
        .order_by(ConsentRecord.granted_at.desc())
    )
    if record is None:
        return ConsentStatus(consented=False)
    return ConsentStatus(consented=True, version=record.version, granted_at=record.granted_at)


@router.post("", status_code=201)
def grant_consent(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ConsentStatus:
    record = ConsentRecord(user_id=user.id, version=CURRENT_VERSION)
    db.add(record)
    db.commit()
    db.refresh(record)
    return ConsentStatus(consented=True, version=record.version, granted_at=record.granted_at)
