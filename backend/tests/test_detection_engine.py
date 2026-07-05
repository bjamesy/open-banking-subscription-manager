"""Heuristic detection engine tests with synthetic transaction histories.

No ANTHROPIC_API_KEY is set in tests, so the AI pass is a no-op and low-
confidence heuristic candidates pass through unchanged.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from subtrack.db.base import Base
from subtrack.db.models import Account, DetectedSubscription, Item, Transaction, User
from subtrack.detection.engine import run_detection


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        user = User(email="t@example.com", password_hash="!")
        s.add(user)
        s.flush()
        item = Item(user_id=user.id, plaid_item_id="item-1", access_token_encrypted="x")
        s.add(item)
        s.flush()
        s.add(Account(item_id=item.id, plaid_account_id="acct-1", name="Chequing"))
        s.commit()
        yield s


def _add_txns(session: Session, merchant: str, amount: str, dates: List[date]) -> None:
    for d in dates:
        session.add(
            Transaction(
                account_id=1,
                plaid_transaction_id=f"{merchant}-{amount}-{d.isoformat()}",
                amount=Decimal(amount),
                currency="CAD",
                merchant_raw=merchant,
                posted_at=d,
                removed=False,
            )
        )
    session.commit()


def test_detects_monthly_subscription(session: Session) -> None:
    _add_txns(
        session,
        "NETFLIX.COM 8721938",
        "15.49",
        [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)],
    )
    written = run_detection(session, user_id=1)
    session.commit()

    assert written == 1
    sub = session.scalar(select(DetectedSubscription))
    assert sub.merchant_normalized == "netflix"
    assert sub.cadence == "monthly"
    assert sub.status == "detected"
    assert sub.detection_source == "heuristic"
    assert sub.confidence_score >= 0.7
    # Next charge = last occurrence + median gap (31 days here)
    assert sub.next_expected_charge == date(2026, 5, 6)


def test_ignores_irregular_spending(session: Session) -> None:
    _add_txns(
        session,
        "GROCERY MART",
        "83.12",
        [date(2026, 1, 3), date(2026, 1, 21), date(2026, 3, 2)],
    )
    # Different amounts at the same merchant also break the amount cluster
    _add_txns(session, "GROCERY MART", "41.55", [date(2026, 2, 11)])

    assert run_detection(session, user_id=1) == 0
    assert session.scalar(select(DetectedSubscription)) is None


def test_ignores_inflows(session: Session) -> None:
    # Plaid convention: negative amount = money in (e.g. payroll)
    _add_txns(
        session,
        "EMPLOYER PAYROLL",
        "-2000.00",
        [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)],
    )
    assert run_detection(session, user_id=1) == 0


def test_weekly_cadence(session: Session) -> None:
    _add_txns(
        session,
        "SPOTIFY",
        "5.99",
        [date(2026, 3, d) for d in (1, 8, 15, 22, 29)],
    )
    run_detection(session, user_id=1)
    session.commit()

    sub = session.scalar(select(DetectedSubscription))
    assert sub is not None and sub.cadence == "weekly"


def test_rerun_preserves_user_status(session: Session) -> None:
    _add_txns(
        session,
        "NETFLIX.COM 123",
        "15.49",
        [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)],
    )
    run_detection(session, user_id=1)
    session.commit()

    sub = session.scalar(select(DetectedSubscription))
    sub.status = "dismissed"  # user dismisses it
    session.commit()

    # New charge arrives; detection re-runs
    _add_txns(session, "NETFLIX.COM 123", "15.49", [date(2026, 4, 5)])
    run_detection(session, user_id=1)
    session.commit()

    subs = session.scalars(select(DetectedSubscription)).all()
    assert len(subs) == 1  # no duplicate created
    assert subs[0].status == "dismissed"  # user's decision preserved
    # Data refreshed: last occurrence (Apr 5) + median gap (31 days)
    assert subs[0].next_expected_charge == date(2026, 5, 6)
