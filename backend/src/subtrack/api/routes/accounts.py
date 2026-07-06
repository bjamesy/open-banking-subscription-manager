"""Linked accounts with institution and sync status (architecture §2.5)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_current_user, get_db
from subtrack.db.models import Account, Item, User

router = APIRouter()


class AccountOut(BaseModel):
    id: int
    name: str
    mask: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    currency: Optional[str] = None
    institution_name: Optional[str] = None
    item_status: str
    last_synced_at: Optional[datetime] = None


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
            name=account.name,
            mask=account.mask,
            type=account.type,
            subtype=account.subtype,
            currency=account.currency,
            institution_name=item.institution_name,
            item_status=item.status,
            last_synced_at=item.last_synced_at,
        )
        for account, item in rows
    ]
