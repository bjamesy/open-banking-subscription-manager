"""Password hashing and JWT access tokens (architecture §2.5, §5.5).

Uses `bcrypt` directly rather than passlib (passlib is unmaintained and warns
on bcrypt>=4.1). Tokens are short-lived HS256 JWTs via python-jose; the signing
secret comes from JWT_SECRET in the environment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from subtrack.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Malformed hash (e.g. legacy placeholder rows) -> treat as no match.
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> int:
    """Return the user id from a valid token; raise ValueError otherwise."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError("invalid token") from exc
