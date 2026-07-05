"""FastAPI dependencies."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from subtrack.db.base import get_sessionmaker
from subtrack.providers.base import BankingProvider
from subtrack.providers.factory import get_provider


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def get_banking_provider() -> BankingProvider:
    return get_provider()
