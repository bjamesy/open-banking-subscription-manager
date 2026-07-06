"""poll_all_items: the missed-webhook correctness fallback."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import subtrack.config as config_module
import subtrack.ingestion.scheduler as scheduler_module
from subtrack.db.base import Base
from subtrack.db.models import Account, Item, Transaction, User
from subtrack.ingestion.scheduler import poll_all_items
from subtrack.providers.base import ProviderTransaction, SyncResult
from subtrack.security import crypto
from tests.test_ingestion_sync import FakeProvider


@pytest.fixture()
def sessionmaker_(monkeypatch):
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(),
        raising=False,
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(scheduler_module, "get_sessionmaker", lambda: factory)
    return factory


def _seed_item(factory, plaid_item_id: str, status: str = "active") -> None:
    with factory() as s:
        user = s.scalar(select(User))
        if user is None:
            user = User(email="t@example.com", password_hash="!")
            s.add(user)
            s.flush()
        item = Item(
            user_id=user.id,
            plaid_item_id=plaid_item_id,
            access_token_encrypted=crypto.encrypt(f"token-{plaid_item_id}"),
            status=status,
        )
        s.add(item)
        s.flush()
        s.add(
            Account(
                item_id=item.id, plaid_account_id=f"acct-{plaid_item_id}", name="Chq"
            )
        )
        s.commit()


def test_poll_syncs_active_items_only(sessionmaker_) -> None:
    _seed_item(sessionmaker_, "item-active")
    _seed_item(sessionmaker_, "item-errored", status="error")

    provider = FakeProvider(
        SyncResult(
            added=[
                ProviderTransaction(
                    provider_transaction_id="p1",
                    provider_account_id="acct-item-active",
                    amount=Decimal("9.99"),
                    description="SPOTIFY",
                    posted_at=date(2026, 7, 1),
                    currency="CAD",
                )
            ],
            modified=[],
            removed_ids=[],
            cursor="c1",
        ),
        accounts=[],
    )

    assert poll_all_items(provider) == 1  # only the active item

    with sessionmaker_() as s:
        txn = s.scalar(select(Transaction))
        assert txn is not None and txn.merchant_raw == "SPOTIFY"
        active = s.scalar(select(Item).where(Item.plaid_item_id == "item-active"))
        assert active.cursor == "c1"
        errored = s.scalar(select(Item).where(Item.plaid_item_id == "item-errored"))
        assert errored.cursor is None  # untouched
