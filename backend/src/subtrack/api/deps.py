"""FastAPI dependencies."""
from __future__ import annotations

from typing import Iterator, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from subtrack.db.base import get_sessionmaker
from subtrack.db.models import User
from subtrack.providers.base import BankingProvider
from subtrack.providers.factory import get_provider
from subtrack.security import auth

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def get_banking_provider() -> BankingProvider:
    return get_provider()


def get_session_factory():
    """Session factory for background tasks, which outlive the request-scoped
    `get_db` session. Its own dependency purely so tests can override it to
    point at the test database (see test_routes_rescan.py)."""
    return get_sessionmaker()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        user_id = auth.decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user
