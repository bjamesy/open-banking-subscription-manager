from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

import subtrack.config as config_module
from subtrack.api.deps import get_banking_provider
from subtrack.db.models import Account, DetectedSubscription, Item, RescanJob, Transaction, User
from subtrack.main import app
from subtrack.security import crypto
from tests.test_ingestion_sync import FakeProvider

CREDS = {"email": "delete-me@example.com", "password": "s3cret-pass"}


def _auth_headers(client, creds=CREDS) -> dict:
    client.post("/auth/register", json=creds)
    token = client.post("/auth/login", json=creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_full_account(client, email: str = CREDS["email"]) -> int:
    """One Item + Account + Transaction + DetectedSubscription + RescanJob
    for the given user, mirroring a real linked-and-detected account."""
    with client.sessionmaker() as s:
        user = s.scalar(select(User).where(User.email == email))
        item = Item(
            user_id=user.id,
            plaid_item_id="item-delete-1",
            access_token_encrypted=crypto.encrypt("access-test-token"),
            status="active",
        )
        s.add(item)
        s.flush()
        account = Account(item_id=item.id, plaid_account_id="acct-delete-1", name="Chequing")
        s.add(account)
        s.flush()
        s.add(
            Transaction(
                account_id=account.id,
                plaid_transaction_id="t-delete-1",
                amount=Decimal("15.49"),
                currency="CAD",
                merchant_raw="NETFLIX.COM",
                merchant_normalized="netflix",
                posted_at=date(2026, 6, 1),
            )
        )
        s.add(
            DetectedSubscription(
                user_id=user.id,
                account_id=account.id,
                merchant_normalized="netflix",
                amount=Decimal("15.49"),
                currency="CAD",
                cadence="monthly",
                status="detected",
                detection_source="heuristic",
            )
        )
        s.add(RescanJob(user_id=user.id, status="done", items_synced=1, items_failed=0))
        s.commit()
        return user.id


def _counts(client, user_id: int) -> dict:
    with client.sessionmaker() as s:
        return {
            "user": s.get(User, user_id) is not None,
            "items": len(list(s.scalars(select(Item).where(Item.user_id == user_id)))),
            "accounts": len(
                list(
                    s.scalars(
                        select(Account).join(Item).where(Item.user_id == user_id)
                    )
                )
            ),
            "transactions": len(
                list(
                    s.scalars(
                        select(Transaction)
                        .join(Account)
                        .join(Item)
                        .where(Item.user_id == user_id)
                    )
                )
            ),
            "subscriptions": len(
                list(
                    s.scalars(
                        select(DetectedSubscription).where(
                            DetectedSubscription.user_id == user_id
                        )
                    )
                )
            ),
            "rescan_jobs": len(
                list(s.scalars(select(RescanJob).where(RescanJob.user_id == user_id)))
            ),
        }


def test_delete_account_requires_auth(client) -> None:
    r = client.request("DELETE", "/auth/me", json={"password": "whatever"})
    assert r.status_code == 401


def test_delete_account_wrong_password_deletes_nothing(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    user_id = _seed_full_account(client)

    r = client.request(
        "DELETE", "/auth/me", json={"password": "not-the-password"}, headers=headers
    )
    assert r.status_code == 401

    counts = _counts(client, user_id)
    assert counts == {
        "user": True,
        "items": 1,
        "accounts": 1,
        "transactions": 1,
        "subscriptions": 1,
        "rescan_jobs": 1,
    }


def test_delete_account_success_cascades_everything(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    user_id = _seed_full_account(client)

    provider = FakeProvider()
    app.dependency_overrides[get_banking_provider] = lambda: provider

    r = client.request("DELETE", "/auth/me", json={"password": CREDS["password"]}, headers=headers)
    assert r.status_code == 204

    counts = _counts(client, user_id)
    assert counts == {
        "user": False,
        "items": 0,
        "accounts": 0,
        "transactions": 0,
        "subscriptions": 0,
        "rescan_jobs": 0,
    }
    assert provider.removed_access_tokens == ["access-test-token"]

    # The account is gone — the same credentials no longer work.
    r = client.post("/auth/login", json=CREDS)
    assert r.status_code == 401


def test_delete_account_survives_plaid_revocation_failure(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    user_id = _seed_full_account(client)

    provider = FakeProvider(remove_item_exc=RuntimeError("plaid is down"))
    app.dependency_overrides[get_banking_provider] = lambda: provider

    r = client.request("DELETE", "/auth/me", json={"password": CREDS["password"]}, headers=headers)
    assert r.status_code == 204

    counts = _counts(client, user_id)
    assert counts["user"] is False
    assert counts["items"] == 0


def test_delete_google_only_account_skips_password(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    google_creds = {"email": "google-only@example.com", "password": "irrelevant"}
    with client.sessionmaker() as s:
        s.add(User(email=google_creds["email"], password_hash="!"))
        s.commit()

    # No password login exists for this user — get an access token via the
    # session directly by minting one the same way /auth/google would.
    import subtrack.security.auth as auth_module

    with client.sessionmaker() as s:
        user = s.scalar(select(User).where(User.email == google_creds["email"]))
        token = auth_module.create_access_token(user.id)
        user_id = user.id

    headers = {"Authorization": f"Bearer {token}"}
    r = client.request("DELETE", "/auth/me", json={}, headers=headers)
    assert r.status_code == 204

    with client.sessionmaker() as s:
        assert s.get(User, user_id) is None
