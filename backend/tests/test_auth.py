from __future__ import annotations

CREDS = {"email": "alice@example.com", "password": "s3cret-pass"}


def _register_and_login(client) -> dict:
    client.post("/auth/register", json=CREDS)
    token = client.post("/auth/login", json=CREDS).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_login_flow(client) -> None:
    r = client.post("/auth/register", json=CREDS)
    assert r.status_code == 201
    assert r.json()["email"] == CREDS["email"]

    # Duplicate email rejected
    assert client.post("/auth/register", json=CREDS).status_code == 409

    r = client.post("/auth/login", json=CREDS)
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password(client) -> None:
    client.post("/auth/register", json=CREDS)
    r = client.post("/auth/login", json={**CREDS, "password": "wrong-password"})
    assert r.status_code == 401


def test_subscriptions_requires_auth(client) -> None:
    assert client.get("/subscriptions").status_code == 401
    assert client.get(
        "/subscriptions", headers={"Authorization": "Bearer not-a-token"}
    ).status_code == 401


def test_subscriptions_with_token(client) -> None:
    headers = _register_and_login(client)
    r = client.get("/subscriptions", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_manual_add_confirm_dismiss(client) -> None:
    headers = _register_and_login(client)

    r = client.post(
        "/subscriptions",
        json={"merchant": "Netflix", "amount": "15.49", "cadence": "monthly"},
        headers=headers,
    )
    assert r.status_code == 201
    sub = r.json()
    assert sub["status"] == "confirmed"
    assert sub["detection_source"] == "manual"

    r = client.patch(
        f"/subscriptions/{sub['id']}", json={"status": "dismissed"}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"

    # Dismissed items are excluded from the default listing
    assert client.get("/subscriptions", headers=headers).json() == []

    # Unknown id -> 404
    r = client.patch("/subscriptions/9999", json={"status": "confirmed"}, headers=headers)
    assert r.status_code == 404
