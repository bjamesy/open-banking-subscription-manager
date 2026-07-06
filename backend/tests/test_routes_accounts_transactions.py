from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from subtrack.db.models import Account, Item, Transaction

CREDS = {"email": "bob@example.com", "password": "s3cret-pass"}


def _auth_headers(client) -> dict:
    client.post("/auth/register", json=CREDS)
    token = client.post("/auth/login", json=CREDS).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed(client) -> None:
    """One item + account + three transactions for user 1."""
    with client.sessionmaker() as s:
        item = Item(
            user_id=1,
            plaid_item_id="item-1",
            institution_name="Test Bank",
            access_token_encrypted="x",
            last_synced_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        s.add(item)
        s.flush()
        account = Account(
            item_id=item.id, plaid_account_id="acct-1", name="Chequing", mask="1234"
        )
        s.add(account)
        s.flush()
        for i, (amount, day) in enumerate([("15.49", 1), ("9.99", 15), ("83.10", 20)]):
            s.add(
                Transaction(
                    account_id=account.id,
                    plaid_transaction_id=f"t{i}",
                    amount=Decimal(amount),
                    currency="CAD",
                    merchant_raw=f"MERCHANT {i}",
                    posted_at=date(2026, 6, day),
                    removed=False,
                )
            )
        s.commit()


def test_accounts_requires_auth(client) -> None:
    assert client.get("/accounts").status_code == 401
    assert client.get("/transactions").status_code == 401


def test_list_accounts(client) -> None:
    headers = _auth_headers(client)
    _seed(client)

    r = client.get("/accounts", headers=headers)
    assert r.status_code == 200
    accounts = r.json()
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Chequing"
    assert accounts[0]["institution_name"] == "Test Bank"
    assert accounts[0]["item_status"] == "active"
    assert accounts[0]["last_synced_at"] is not None


def test_list_transactions_filters_and_pagination(client) -> None:
    headers = _auth_headers(client)
    _seed(client)

    r = client.get("/transactions", headers=headers)
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 3
    # Newest first
    assert [t["posted_at"] for t in page["items"]] == [
        "2026-06-20", "2026-06-15", "2026-06-01",
    ]

    # Date filter
    page = client.get(
        "/transactions?start_date=2026-06-10&end_date=2026-06-16", headers=headers
    ).json()
    assert page["total"] == 1
    assert page["items"][0]["amount"] == 9.99

    # Pagination
    page = client.get("/transactions?limit=2&offset=2", headers=headers).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1


def test_transactions_scoped_to_user(client) -> None:
    _auth_headers(client)  # registers user 1, who owns the seeded data
    _seed(client)

    # A second user must not see user 1's data
    other = {"email": "eve@example.com", "password": "s3cret-pass"}
    client.post("/auth/register", json=other)
    other_token = client.post("/auth/login", json=other).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.get("/accounts", headers=other_headers).json() == []
    assert client.get("/transactions", headers=other_headers).json()["total"] == 0
