"""Provider-agnostic banking interface (architecture §2.1, §5.1).

Everything outside `providers/` depends on `BankingProvider` and these plain
dataclasses, never on a specific aggregator's SDK. Swapping or adding an
aggregator (e.g. a Canadian-native provider if Plaid coverage falls short —
§6.2) means implementing this ABC and updating the factory.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional


@dataclass
class LinkToken:
    link_token: str


@dataclass
class TokenExchange:
    access_token: str
    item_id: str


@dataclass
class ProviderAccount:
    provider_account_id: str
    name: str
    mask: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    currency: Optional[str] = None


@dataclass
class ProviderTransaction:
    provider_transaction_id: str
    provider_account_id: str
    amount: Decimal
    description: str
    posted_at: date
    currency: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class SyncResult:
    added: List[ProviderTransaction]
    modified: List[ProviderTransaction]
    removed_ids: List[str]
    cursor: str
    has_more: bool = False


class ProviderError(Exception):
    """A provider call failed. `code`/`message` are provider-specific but kept
    provider-agnostic in shape so callers never need to know which aggregator
    is behind the ABC."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class ReauthRequiredError(ProviderError):
    """The access token needs Link update-mode re-authentication (e.g. Plaid's
    ITEM_LOGIN_REQUIRED) — the connection itself isn't broken, the user's bank
    login needs to be redone."""


class BankingProvider(ABC):
    @abstractmethod
    def create_link_token(
        self, client_user_id: str, access_token: Optional[str] = None
    ) -> LinkToken:
        ...

    @abstractmethod
    def exchange_public_token(self, public_token: str) -> TokenExchange:
        ...

    @abstractmethod
    def sync_transactions(self, access_token: str, cursor: Optional[str]) -> SyncResult:
        ...

    @abstractmethod
    def get_accounts(self, access_token: str) -> List[ProviderAccount]:
        ...

    @abstractmethod
    def remove_item(self, access_token: str) -> None:
        """Revoke this access token at the provider (architecture §6.8 —
        account deletion). Callers treat this as best-effort: a failure here
        should not block deleting the user's local data."""
        ...
