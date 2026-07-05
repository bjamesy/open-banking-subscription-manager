"""Resolve the active BankingProvider. Import is lazy so the app can boot
without the Plaid SDK present until a provider is actually used."""
from __future__ import annotations

from subtrack.providers.base import BankingProvider


def get_provider() -> BankingProvider:
    from subtrack.providers.plaid.provider import PlaidProvider

    return PlaidProvider()
