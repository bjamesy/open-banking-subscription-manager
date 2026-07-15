"""Plaid Link routes (architecture §3.1).

`/link/token` creates a Link token for the browser widget — in update mode
(when `item_id` is given) it re-authenticates an existing Item's bank login
instead of creating a new one. `/link/exchange` swaps the public_token for an
access token, persists an encrypted Item plus its accounts, and runs a
best-effort initial sync + detection.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_banking_provider, get_current_user, get_db
from subtrack.db.models import Account, Item, User
from subtrack.detection.engine import run_detection
from subtrack.ingestion.sync import sync_item
from subtrack.providers.base import BankingProvider, ReauthRequiredError
from subtrack.security import crypto

router = APIRouter()


class LinkTokenRequest(BaseModel):
    item_id: Optional[int] = None


class ExchangeRequest(BaseModel):
    public_token: str


@router.post("/token")
def create_link_token(
    body: LinkTokenRequest = LinkTokenRequest(),
    user: User = Depends(get_current_user),
    provider: BankingProvider = Depends(get_banking_provider),
    db: Session = Depends(get_db),
) -> dict:
    access_token = None
    if body.item_id is not None:
        item = db.scalar(
            select(Item).where(Item.id == body.item_id, Item.user_id == user.id)
        )
        if item is None:
            raise HTTPException(status_code=404, detail="item not found")
        access_token = crypto.decrypt(item.access_token_encrypted)

    try:
        token = provider.create_link_token(
            client_user_id=str(user.id), access_token=access_token
        )
    except Exception as exc:  # provider/SDK errors -> 400 for the client
        raise HTTPException(status_code=400, detail=str(exc))
    return {"link_token": token.link_token}


@router.post("/exchange")
def exchange_public_token(
    body: ExchangeRequest,
    user: User = Depends(get_current_user),
    provider: BankingProvider = Depends(get_banking_provider),
    db: Session = Depends(get_db),
) -> dict:
    try:
        exchanged = provider.exchange_public_token(body.public_token)
        accounts = provider.get_accounts(exchanged.access_token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    item = Item(
        user_id=user.id,
        plaid_item_id=exchanged.item_id,
        access_token_encrypted=crypto.encrypt(exchanged.access_token),
        status="active",
    )
    db.add(item)
    db.flush()

    for acct in accounts:
        db.add(
            Account(
                item_id=item.id,
                plaid_account_id=acct.provider_account_id,
                name=acct.name,
                mask=acct.mask,
                type=acct.type,
                subtype=acct.subtype,
                currency=acct.currency,
            )
        )
    db.commit()

    # Best-effort initial sync + detection so the dashboard has data
    # immediately. Plaid commonly returns PRODUCT_NOT_READY right after link;
    # the Item is already persisted, so a failure here must not fail the
    # exchange — the user can retry via POST /accounts/rescan.
    initial_sync = "ok"
    try:
        sync_item(db, item, provider)
        run_detection(db, user.id)
        db.commit()
    except ReauthRequiredError as exc:
        db.rollback()
        item.status = "error"
        item.error = exc.code
        db.commit()
        initial_sync = "pending"
    except Exception:
        db.rollback()
        initial_sync = "pending"

    return {
        "item_id": item.plaid_item_id,
        "accounts": len(accounts),
        "initial_sync": initial_sync,
    }
