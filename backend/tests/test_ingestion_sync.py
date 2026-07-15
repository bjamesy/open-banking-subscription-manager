"""Exercises sync_item end-to-end against an in-memory DB with a fake provider —
no Plaid credentials or network needed."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import subtrack.config as config_module
from subtrack.db.base import Base
from subtrack.db.models import Account, Item, Transaction, User
from subtrack.ingestion.sync import sync_item
from subtrack.providers.base import (
    BankingProvider,
    LinkToken,
    ProviderAccount,
    ProviderTransaction,
    ReauthRequiredError,
    SyncResult,
    TokenExchange,
)
from subtrack.security import crypto


class FakeProvider(BankingProvider):
    def __init__(
        self,
        result: Optional[SyncResult] = None,
        accounts: Optional[List[ProviderAccount]] = None,
        exc: Optional[Exception] = None,
    ):
        self._result = result
        self._accounts = accounts or []
        self._exc = exc
        self.last_link_token_access_token: Optional[str] = "__unset__"

    def create_link_token(
        self, client_user_id: str, access_token: Optional[str] = None
    ) -> LinkToken:
        self.last_link_token_access_token = access_token
        return LinkToken(link_token="fake-link-token")

    def exchange_public_token(self, public_token: str) -> TokenExchange:
        raise NotImplementedError

    def sync_transactions(self, access_token: str, cursor: Optional[str]) -> SyncResult:
        if self._exc:
            raise self._exc
        return self._result

    def get_accounts(self, access_token: str) -> List[ProviderAccount]:
        return self._accounts


def _txn(txn_id: str, account_id: str, amount: str, desc: str, day: int) -> ProviderTransaction:
    return ProviderTransaction(
        provider_transaction_id=txn_id,
        provider_account_id=account_id,
        amount=Decimal(amount),
        description=desc,
        posted_at=date(2026, 6, day),
        currency="CAD",
        raw={"transaction_id": txn_id},
    )


@pytest.fixture()
def session(monkeypatch) -> Session:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture()
def item(session: Session) -> Item:
    user = User(email="t@example.com", password_hash="!")
    session.add(user)
    session.flush()
    item = Item(
        user_id=user.id,
        plaid_item_id="item-1",
        access_token_encrypted=crypto.encrypt("access-test-token"),
    )
    session.add(item)
    session.add(Account(item_id=1, plaid_account_id="acct-1", name="Chequing"))
    session.commit()
    return item


def test_sync_upserts_and_advances_cursor(session: Session, item: Item) -> None:
    provider = FakeProvider(
        SyncResult(
            added=[_txn("t1", "acct-1", "15.49", "NETFLIX.COM 123", 1)],
            modified=[],
            removed_ids=[],
            cursor="cursor-2",
        ),
        accounts=[],
    )
    touched = sync_item(session, item, provider)

    assert touched == 1
    assert item.cursor == "cursor-2"
    assert item.last_synced_at is not None
    row = session.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "t1"))
    assert row is not None and row.merchant_raw == "NETFLIX.COM 123"


def test_sync_modified_updates_and_removed_flags(session: Session, item: Item) -> None:
    # Seed t1, then a second sync modifies it and removes it via removed_ids.
    sync_item(
        session,
        item,
        FakeProvider(
            SyncResult(added=[_txn("t1", "acct-1", "10.00", "SPOTIFY", 1)],
                       modified=[], removed_ids=[], cursor="c1"),
            accounts=[],
        ),
    )
    sync_item(
        session,
        item,
        FakeProvider(
            SyncResult(added=[], modified=[_txn("t1", "acct-1", "11.00", "SPOTIFY", 2)],
                       removed_ids=["t1"], cursor="c2"),
            accounts=[],
        ),
    )
    row = session.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "t1"))
    assert row.amount == Decimal("11.00")
    assert row.removed is True
    assert session.scalars(select(Transaction)).all().__len__() == 1  # no duplicate


def test_sync_item_propagates_reauth_required(session: Session, item: Item) -> None:
    """sync_item itself doesn't catch provider errors — that's rescan_items's
    job (it persists Item.status/error); sync_item just re-raises."""
    provider = FakeProvider(exc=ReauthRequiredError("ITEM_LOGIN_REQUIRED", "bad login"))
    with pytest.raises(ReauthRequiredError):
        sync_item(session, item, provider)


def test_sync_creates_missing_account_instead_of_dropping(
    session: Session, item: Item
) -> None:
    """Transactions for an account added after link must not be lost —
    the cursor advances past them, so they'd never be re-delivered."""
    provider = FakeProvider(
        SyncResult(
            added=[_txn("t9", "acct-new", "8.99", "DISNEY PLUS", 3)],
            modified=[],
            removed_ids=[],
            cursor="c9",
        ),
        accounts=[
            ProviderAccount(provider_account_id="acct-1", name="Chequing"),
            ProviderAccount(provider_account_id="acct-new", name="Credit Card"),
        ],
    )
    touched = sync_item(session, item, provider)

    assert touched == 1
    new_account = session.scalar(
        select(Account).where(Account.plaid_account_id == "acct-new")
    )
    assert new_account is not None and new_account.name == "Credit Card"
    row = session.scalar(select(Transaction).where(Transaction.plaid_transaction_id == "t9"))
    assert row is not None and row.account_id == new_account.id
