"""Transaction sync orchestration (architecture §2.2, §3.2).

Drives a cursor-based sync for one Item: decrypt token -> provider.sync ->
upsert transactions -> advance cursor (atomically) -> enqueue detection.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.db.models import Account, Item, Transaction
from subtrack.detection.engine import run_detection
from subtrack.providers.base import (
    BankingProvider,
    ProviderTransaction,
    ReauthRequiredError,
)
from subtrack.security import crypto

logger = logging.getLogger(__name__)


def sync_item(session: Session, item: Item, provider: BankingProvider) -> int:
    """Sync one Item and return the number of transactions added/modified.

    The cursor and last_synced_at are committed in the same transaction as the
    upserts, so a failure re-syncs cleanly from the last good cursor.
    """
    access_token = crypto.decrypt(item.access_token_encrypted)
    result = provider.sync_transactions(access_token, item.cursor)

    account_map = {
        a.plaid_account_id: a.id
        for a in session.scalars(
            select(Account).where(Account.item_id == item.id)
        )
    }

    upserts = list(result.added) + list(result.modified)

    # Accounts can be added to an Item after the initial link. Because the
    # cursor advances past everything in this batch, silently skipping unknown
    # accounts would lose their transactions permanently — refresh accounts
    # from the provider instead and create any that are missing.
    unknown = {t.provider_account_id for t in upserts} - set(account_map)
    if unknown:
        for acct in provider.get_accounts(access_token):
            if acct.provider_account_id in unknown:
                account = Account(
                    item_id=item.id,
                    plaid_account_id=acct.provider_account_id,
                    name=acct.name,
                    mask=acct.mask,
                    type=acct.type,
                    subtype=acct.subtype,
                    currency=acct.currency,
                )
                session.add(account)
                session.flush()
                account_map[acct.provider_account_id] = account.id

    touched = 0
    for txn in upserts:
        account_id = account_map.get(txn.provider_account_id)
        if account_id is None:
            # Provider no longer reports this account; nothing safe to attach
            # the transaction to. This should not happen in practice.
            continue
        _upsert_transaction(session, account_id, txn)
        touched += 1

    if result.removed_ids:
        for row in session.scalars(
            select(Transaction).where(
                Transaction.plaid_transaction_id.in_(result.removed_ids)
            )
        ):
            row.removed = True

    item.cursor = result.cursor
    item.last_synced_at = datetime.now(timezone.utc)
    session.commit()
    return touched


def rescan_items(
    session: Session, items: Sequence[Item], provider: BankingProvider
) -> Tuple[int, int]:
    """Sync each Item best-effort, then run detection once per affected user.

    One failing Item (e.g. an expired access token) doesn't block the rest.
    Returns (items_synced, items_failed).
    """
    synced = 0
    failed = 0
    user_ids = set()
    for item in items:
        try:
            sync_item(session, item, provider)
            user_ids.add(item.user_id)
            synced += 1
        except ReauthRequiredError as exc:
            session.rollback()
            item.status = "error"
            item.error = exc.code
            session.commit()
            failed += 1
            logger.warning(
                "item %s needs re-auth: %s", item.plaid_item_id, exc.code
            )
        except Exception:
            session.rollback()
            failed += 1
            logger.exception("rescan sync failed for item %s", item.plaid_item_id)

    for user_id in user_ids:
        try:
            run_detection(session, user_id)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("rescan detection failed for user %s", user_id)

    return synced, failed


def _upsert_transaction(
    session: Session, account_id: int, txn: ProviderTransaction
) -> None:
    existing = session.scalar(
        select(Transaction).where(
            Transaction.plaid_transaction_id == txn.provider_transaction_id
        )
    )
    if existing is None:
        session.add(
            Transaction(
                account_id=account_id,
                plaid_transaction_id=txn.provider_transaction_id,
                amount=txn.amount,
                currency=txn.currency,
                merchant_raw=txn.description,
                merchant_normalized=None,  # filled by detection preprocessing
                posted_at=txn.posted_at,
                removed=False,
                raw_payload=txn.raw,
            )
        )
    else:
        existing.amount = txn.amount
        existing.currency = txn.currency
        existing.merchant_raw = txn.description
        existing.posted_at = txn.posted_at
        existing.removed = False
        existing.raw_payload = txn.raw
