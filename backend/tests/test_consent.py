from __future__ import annotations

from sqlalchemy import select

from subtrack.api.routes.consent import CURRENT_VERSION
from subtrack.db.models import ConsentRecord

CREDS = {"email": "consent-test@example.com", "password": "s3cret-pass"}


def _auth_headers(client) -> dict:
    client.post("/auth/register", json=CREDS)
    token = client.post("/auth/login", json=CREDS).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_consent_requires_auth(client) -> None:
    assert client.get("/consent").status_code == 401
    assert client.post("/consent").status_code == 401


def test_fresh_user_has_not_consented(client) -> None:
    headers = _auth_headers(client)
    r = client.get("/consent", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"consented": False, "version": None, "granted_at": None}


def test_grant_and_check_consent(client) -> None:
    headers = _auth_headers(client)

    r = client.post("/consent", headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["consented"] is True
    assert body["version"] == CURRENT_VERSION
    assert body["granted_at"] is not None

    r = client.get("/consent", headers=headers)
    assert r.status_code == 200
    assert r.json()["consented"] is True
    assert r.json()["version"] == CURRENT_VERSION


def test_repeated_grants_append_rather_than_error(client) -> None:
    headers = _auth_headers(client)

    assert client.post("/consent", headers=headers).status_code == 201
    assert client.post("/consent", headers=headers).status_code == 201

    with client.sessionmaker() as s:
        rows = list(s.scalars(select(ConsentRecord)))
        assert len(rows) == 2
