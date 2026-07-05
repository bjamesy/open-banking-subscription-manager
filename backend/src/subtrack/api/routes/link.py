"""Plaid Link routes (architecture §3.1).

`/link/token` creates a Link token for the browser widget. `/link/exchange`
swaps the public_token for an access token, persists an encrypted Item plus its
accounts, and runs a best-effort initial sync + detection.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from subtrack.api.deps import get_banking_provider, get_current_user, get_db
from subtrack.db.models import Account, Item, User
from subtrack.detection.engine import run_detection
from subtrack.ingestion.sync import sync_item
from subtrack.providers.base import BankingProvider
from subtrack.security import crypto

router = APIRouter()


class ExchangeRequest(BaseModel):
    public_token: str


@router.post("/token")
def create_link_token(
    user: User = Depends(get_current_user),
    provider: BankingProvider = Depends(get_banking_provider),
) -> dict:
    try:
        token = provider.create_link_token(client_user_id=str(user.id))
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
    # exchange — the SYNC_UPDATES_AVAILABLE webhook (or the scheduled poll)
    # will sync later.
    initial_sync = "ok"
    try:
        sync_item(db, item, provider)
        run_detection(db, user.id)
        db.commit()
    except Exception:
        db.rollback()
        initial_sync = "pending"

    return {
        "item_id": item.plaid_item_id,
        "accounts": len(accounts),
        "initial_sync": initial_sync,
    }
