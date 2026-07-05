"""Subscription routes (architecture §3.4): list, confirm/dismiss, manual add."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_current_user, get_db
from subtrack.db.models import DetectedSubscription, User

router = APIRouter()


class SubscriptionOut(BaseModel):
    id: int
    merchant_normalized: str
    amount: float
    currency: Optional[str] = None
    cadence: Optional[str] = None
    confidence_score: Optional[float] = None
    status: str
    next_expected_charge: Optional[date] = None
    detection_source: Optional[str] = None

    model_config = {"from_attributes": True}


class StatusPatch(BaseModel):
    status: str = Field(pattern="^(confirmed|dismissed)$")


class ManualSubscription(BaseModel):
    merchant: str = Field(min_length=1, max_length=512)
    amount: Decimal = Field(gt=0)
    currency: Optional[str] = None
    cadence: Optional[str] = Field(
        default=None, pattern="^(weekly|biweekly|monthly|quarterly|yearly|custom)$"
    )
    next_expected_charge: Optional[date] = None


@router.get("")
def list_subscriptions(
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[SubscriptionOut]:
    query = select(DetectedSubscription).where(
        DetectedSubscription.user_id == user.id
    )
    if status:
        query = query.where(DetectedSubscription.status.in_(status.split(",")))
    else:
        query = query.where(
            DetectedSubscription.status.in_(["detected", "confirmed"])
        )
    return [SubscriptionOut.model_validate(r) for r in db.scalars(query)]


@router.patch("/{subscription_id}")
def update_status(
    subscription_id: int,
    body: StatusPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    row = db.scalar(
        select(DetectedSubscription).where(
            DetectedSubscription.id == subscription_id,
            DetectedSubscription.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    row.status = body.status
    db.commit()
    return SubscriptionOut.model_validate(row)


@router.post("", status_code=201)
def add_manual(
    body: ManualSubscription,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    row = DetectedSubscription(
        user_id=user.id,
        merchant_normalized=body.merchant.strip().lower(),
        amount=body.amount,
        currency=body.currency,
        cadence=body.cadence,
        confidence_score=1.0,
        status="confirmed",
        next_expected_charge=body.next_expected_charge,
        detection_source="manual",
    )
    db.add(row)
    db.commit()
    return SubscriptionOut.model_validate(row)
