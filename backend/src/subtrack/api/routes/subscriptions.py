"""Subscription routes (architecture §3.4)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_db
from subtrack.db.models import DetectedSubscription

router = APIRouter()


class SubscriptionOut(BaseModel):
    id: int
    merchant_normalized: str
    amount: float
    currency: Optional[str] = None
    cadence: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


@router.get("")
def list_subscriptions(db: Session = Depends(get_db)) -> List[SubscriptionOut]:
    # TODO(auth): filter by authenticated user_id.
    rows = db.scalars(
        select(DetectedSubscription).where(
            DetectedSubscription.status.in_(["detected", "confirmed"])
        )
    )
    return [SubscriptionOut.model_validate(r) for r in rows]
