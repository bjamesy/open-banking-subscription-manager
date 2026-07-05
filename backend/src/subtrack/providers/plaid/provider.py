"""Plaid implementation of BankingProvider.

Adapted from the cresidential project's `plaid_service.py` / `routers/plaid.py`.
Key changes for SubTrack:
- country codes default to CA (was hardcoded US) — verify coverage, architecture §6.2
- `sync_transactions` returns added / modified / removed (cresidential took only `added`)
- credentials come from `subtrack.config.Settings` (was module-level os.getenv)

The Plaid SDK is imported lazily inside methods so importing this module (e.g.
during app startup or tests) does not require the SDK to be installed.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import List, Optional

from subtrack.config import get_settings
from subtrack.providers.base import (
    BankingProvider,
    LinkToken,
    ProviderAccount,
    ProviderTransaction,
    SyncResult,
    TokenExchange,
)


class PlaidProvider(BankingProvider):
    def _client(self):
        import plaid
        from plaid.api import plaid_api

        settings = get_settings()
        env_map = {
            "sandbox": plaid.Environment.Sandbox,
            "production": plaid.Environment.Production,
        }
        configuration = plaid.Configuration(
            host=env_map.get(settings.plaid_env, plaid.Environment.Sandbox),
            api_key={
                "clientId": settings.plaid_client_id,
                "secret": settings.plaid_secret,
            },
        )
        return plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def create_link_token(self, client_user_id: str) -> LinkToken:
        from plaid.model.country_code import CountryCode
        from plaid.model.link_token_create_request import LinkTokenCreateRequest
        from plaid.model.link_token_create_request_user import (
            LinkTokenCreateRequestUser,
        )
        from plaid.model.products import Products

        settings = get_settings()
        response = self._client().link_token_create(
            LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=client_user_id),
                client_name=settings.plaid_client_name,
                products=[Products(p) for p in settings.plaid_products_list],
                country_codes=[CountryCode(c) for c in settings.plaid_country_codes_list],
                language="en",
            )
        )
        return LinkToken(link_token=response.link_token)

    def exchange_public_token(self, public_token: str) -> TokenExchange:
        from plaid.model.item_public_token_exchange_request import (
            ItemPublicTokenExchangeRequest,
        )

        response = self._client().item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=public_token)
        )
        return TokenExchange(
            access_token=response.access_token, item_id=response.item_id
        )

    def sync_transactions(
        self, access_token: str, cursor: Optional[str]
    ) -> SyncResult:
        from plaid.model.transactions_sync_request import TransactionsSyncRequest

        client = self._client()
        added: List[ProviderTransaction] = []
        modified: List[ProviderTransaction] = []
        removed_ids: List[str] = []
        next_cursor = cursor or ""

        while True:
            kwargs = {"access_token": access_token}
            if next_cursor:
                kwargs["cursor"] = next_cursor
            response = client.transactions_sync(TransactionsSyncRequest(**kwargs))

            added.extend(self._to_txn(t) for t in response.added)
            modified.extend(self._to_txn(t) for t in response.modified)
            removed_ids.extend(r.transaction_id for r in response.removed)
            next_cursor = response.next_cursor

            if not response.has_more:
                break

        return SyncResult(
            added=added,
            modified=modified,
            removed_ids=removed_ids,
            cursor=next_cursor,
            has_more=False,
        )

    def get_accounts(self, access_token: str) -> List[ProviderAccount]:
        from plaid.model.accounts_get_request import AccountsGetRequest

        response = self._client().accounts_get(
            AccountsGetRequest(access_token=access_token)
        )
        return [
            ProviderAccount(
                provider_account_id=a.account_id,
                name=a.name,
                mask=a.mask,
                type=str(a.type) if a.type is not None else None,
                subtype=str(a.subtype) if a.subtype is not None else None,
                currency=a.balances.iso_currency_code if a.balances else None,
            )
            for a in response.accounts
        ]

    @staticmethod
    def _to_txn(t) -> ProviderTransaction:
        # plaid-python's to_dict() leaves datetime.date objects in the dict,
        # which the SQLAlchemy JSON column (json.dumps) cannot serialize —
        # round-trip through json with default=str to make it storage-safe.
        raw = t.to_dict() if hasattr(t, "to_dict") else {}
        raw = json.loads(json.dumps(raw, default=str))
        return ProviderTransaction(
            provider_transaction_id=t.transaction_id,
            provider_account_id=t.account_id,
            amount=Decimal(str(t.amount)),
            # `name` is more reliable than `merchant_name` in practice (per cresidential)
            description=t.name or t.merchant_name or "",
            posted_at=t.date,
            currency=t.iso_currency_code,
            raw=raw,
        )
