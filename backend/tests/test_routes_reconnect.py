from __future__ import annotations

from sqlalchemy import select

import subtrack.config as config_module
from subtrack.api.deps import get_banking_provider
from subtrack.db.models import Item
from subtrack.main import app
from subtrack.security import crypto
from tests.test_ingestion_sync import FakeProvider

CREDS = {"email": "bob@example.com", "password": "s3cret-pass"}


def _auth_headers(client) -> dict:
    client.post("/auth/register", json=CREDS)
    token = client.post("/auth/login", json=CREDS).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_item(client, status: str = "error", error: str = "ITEM_LOGIN_REQUIRED") -> int:
    with client.sessionmaker() as s:
        item = Item(
            user_id=1,
            plaid_item_id="item-1",
            access_token_encrypted=crypto.encrypt("access-test-token"),
            status=status,
            error=error,
        )
        s.add(item)
        s.commit()
        return item.id


def test_reconnect_requires_auth(client) -> None:
    assert client.post("/accounts/1/reconnect").status_code == 401


def test_reconnect_resets_errored_item(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    item_id = _seed_item(client)

    r = client.post(f"/accounts/{item_id}/reconnect", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"item_id": item_id, "item_status": "active"}

    with client.sessionmaker() as s:
        item = s.scalar(select(Item).where(Item.id == item_id))
        assert item.status == "active"
        assert item.error is None


def test_reconnect_unknown_item_404(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    assert client.post("/accounts/9999/reconnect", headers=headers).status_code == 404


def test_reconnect_other_users_item_404(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    _auth_headers(client)  # registers user 1 (bob), who owns the seeded item
    item_id = _seed_item(client)

    other = {"email": "eve@example.com", "password": "s3cret-pass"}
    client.post("/auth/register", json=other)
    other_token = client.post("/auth/login", json=other).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.post(f"/accounts/{item_id}/reconnect", headers=other_headers).status_code == 404


def test_link_token_update_mode_passes_existing_access_token(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)
    item_id = _seed_item(client)

    provider = FakeProvider()
    app.dependency_overrides[get_banking_provider] = lambda: provider

    r = client.post("/link/token", json={"item_id": item_id}, headers=headers)
    assert r.status_code == 200
    assert r.json()["link_token"] == "fake-link-token"
    assert provider.last_link_token_access_token == "access-test-token"


def test_link_token_normal_mode_omits_access_token(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)

    provider = FakeProvider()
    app.dependency_overrides[get_banking_provider] = lambda: provider

    r = client.post("/link/token", headers=headers)
    assert r.status_code == 200
    assert provider.last_link_token_access_token is None


def test_link_token_update_mode_unknown_item_404(client, monkeypatch) -> None:
    monkeypatch.setattr(
        config_module.get_settings(), "encryption_key", crypto.generate_key(), raising=False
    )
    headers = _auth_headers(client)

    app.dependency_overrides[get_banking_provider] = lambda: FakeProvider()

    r = client.post("/link/token", json={"item_id": 9999}, headers=headers)
    assert r.status_code == 404
