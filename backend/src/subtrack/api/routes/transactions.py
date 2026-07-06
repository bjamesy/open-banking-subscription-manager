"""Stored transactions, filtered and paginated (architecture §2.5)."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_current_user, get_db
from subtrack.db.models import Account, Item, Transaction, User

router = APIRouter()


class TransactionOut(BaseModel):
    id: int
    account_id: int
    amount: float
    currency: Optional[str] = None
    merchant_raw: str
    merchant_normalized: Optional[str] = None
    posted_at: date

    model_config = {"from_attributes": True}


class TransactionPage(BaseModel):
    items: List[TransactionOut]
    total: int
    limit: int
    offset: int


@router.get("")
def list_transactions(
    account_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionPage:
    query = (
        select(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .join(Item, Account.item_id == Item.id)
        .where(Item.user_id == user.id, Transaction.removed.is_(False))
    )
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if start_date is not None:
        query = query.where(Transaction.posted_at >= start_date)
    if end_date is not None:
        query = query.where(Transaction.posted_at <= end_date)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Transaction.posted_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return TransactionPage(
        items=[TransactionOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
