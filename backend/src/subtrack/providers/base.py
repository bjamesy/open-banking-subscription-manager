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


class BankingProvider(ABC):
    @abstractmethod
    def create_link_token(self, client_user_id: str) -> LinkToken:
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
