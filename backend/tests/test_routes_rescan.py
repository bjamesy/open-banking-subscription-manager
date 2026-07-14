from __future__ import annotations

from sqlalchemy import select

import subtrack.config as config_module
from subtrack.api.deps import get_banking_provider, get_session_factory
from subtrack.db.models import Item, RescanJob, Transaction
from subtrack.main import app
from subtrack.providers.base import ProviderAccount, SyncResult
from subtrack.security import crypto
from tests.test_ingestion_sync import FakeProvider, _txn

CREDS = {"email": "bob@example.com", "password": "s3cret-pass"}


def _auth_headers(client) -> dict:
    client.post("/auth/register", json=CREDS)
    token = client.post("/auth/login", json=CREDS).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_item(client, status: str = "active") -> None:
    with client.sessionmaker() as s:
        s.add(
            Item(
                user_id=1,
                plaid_item_id="item-1",
                access_token_encrypted=crypto.encrypt("access-test-token"),
                status=status,
            )
        )
        s.commit()


def _override_provider_and_sessions(client, provider) -> None:
    app.dependency_overrides[get_banking_provider] = lambda: provider
    app.dependency_overrides[get_session_factory] = lambda: client.sessionmaker


def test_rescan_requires_auth(client) -> None:
    assert client.post("/accounts/rescan").status_code == 401
    assert client.get("/accounts/rescan/1").status_code == 401


def test_rescan_runs_in_background_and_completes(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    _seed_item(client)

    provider = FakeProvider(
        SyncResult(
            added=[_txn("t1", "acct-1", "15.49", "NETFLIX.COM 123", 1)],
            modified=[],
            removed_ids=[],
            cursor="cursor-2",
        ),
        accounts=[ProviderAccount(provider_account_id="acct-1", name="Chequing")],
    )
    _override_provider_and_sessions(client, provider)

    # TestClient runs BackgroundTasks synchronously to completion before this
    # call returns, but the response body reflects job state at the moment
    # the route function returned — i.e. still "pending".
    r = client.post("/accounts/rescan", headers=headers)
    assert r.status_code == 202
    job_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # By now the background task has already finished (TestClient executes it
    # inline), so a follow-up GET reflects the completed job.
    r2 = client.get(f"/accounts/rescan/{job_id}", headers=headers)
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "done"
    assert body["items_synced"] == 1
    assert body["items_failed"] == 0

    with client.sessionmaker() as s:
        row = s.scalar(
            select(Transaction).where(Transaction.plaid_transaction_id == "t1")
        )
        assert row is not None
        item = s.scalar(select(Item).where(Item.plaid_item_id == "item-1"))
        assert item.last_synced_at is not None


def test_rescan_skips_inactive_items(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    _seed_item(client, status="error")

    _override_provider_and_sessions(
        client,
        FakeProvider(
            SyncResult(added=[], modified=[], removed_ids=[], cursor="c1"), accounts=[]
        ),
    )

    r = client.post("/accounts/rescan", headers=headers)
    job_id = r.json()["id"]
    body = client.get(f"/accounts/rescan/{job_id}", headers=headers).json()
    assert body["status"] == "done"
    assert body["items_synced"] == 0
    assert body["items_failed"] == 0


def test_rescan_conflicts_while_already_running(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)

    with client.sessionmaker() as s:
        s.add(RescanJob(user_id=1, status="running"))
        s.commit()

    r = client.post("/accounts/rescan", headers=headers)
    assert r.status_code == 409


def test_rescan_job_not_visible_to_other_user(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    _auth_headers(client)  # registers user 1

    with client.sessionmaker() as s:
        job = RescanJob(user_id=1, status="done", items_synced=0, items_failed=0)
        s.add(job)
        s.commit()
        job_id = job.id

    other = {"email": "eve@example.com", "password": "s3cret-pass"}
    client.post("/auth/register", json=other)
    other_token = client.post("/auth/login", json=other).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.get(f"/accounts/rescan/{job_id}", headers=other_headers).status_code == 404
