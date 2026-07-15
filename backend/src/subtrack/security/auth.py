"""Password hashing and JWT tokens (architecture §2.5, §5.5).

Uses `bcrypt` directly rather than passlib (passlib is unmaintained and warns
on bcrypt>=4.1). Two token types, both HS256 via python-jose with the signing
secret from JWT_SECRET:

- access tokens: short-lived (ACCESS_TOKEN_EXPIRE_MINUTES), sent as Bearer
- refresh tokens: longer-lived (REFRESH_TOKEN_EXPIRE_DAYS), exchanged at
  /auth/refresh for a new pair

Tokens carry a `type` claim and each decoder enforces it, so a refresh token
cannot be used as an access token or vice versa. Refresh tokens additionally
carry a `ver` claim checked against `User.token_version` in /auth/refresh —
bumping it (on logout) revokes every outstanding refresh token for that user.
Access tokens are unversioned and stay valid until their short natural expiry
even after logout; that window is the accepted tradeoff for not checking a DB
column on every request.

Google Sign-In (`verify_google_id_token`) verifies a client-obtained ID token
against Google's public keys rather than issuing our own — /auth/google then
mints the same access/refresh pair as password login, so token_version
revocation applies uniformly regardless of how a session started.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

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


def _encode(
    user_id: int,
    token_type: str,
    lifetime: timedelta,
    extra: Optional[dict] = None,
) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": datetime.now(timezone.utc) + lifetime,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str, expected_type: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != expected_type:
            raise ValueError("wrong token type")
        return payload
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError("invalid token") from exc


def create_access_token(user_id: int) -> str:
    minutes = get_settings().access_token_expire_minutes
    return _encode(user_id, "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: int, version: int) -> str:
    days = get_settings().refresh_token_expire_days
    return _encode(user_id, "refresh", timedelta(days=days), extra={"ver": version})


def decode_access_token(token: str) -> int:
    """Return the user id from a valid access token; raise ValueError otherwise."""
    return int(_decode(token, "access")["sub"])


def decode_refresh_token(token: str) -> Tuple[int, int]:
    """Return (user_id, version) from a valid refresh token; raise ValueError otherwise."""
    payload = _decode(token, "refresh")
    try:
        return int(payload["sub"]), int(payload["ver"])
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid token") from exc


def verify_google_id_token(token: str) -> dict:
    """Verify a Google Identity Services credential and return its claims.

    Signature-checked against Google's public keys (via google-auth), with
    `aud` required to match GOOGLE_CLIENT_ID. Raises ValueError on any
    failure, including an unverified email — never raises anything else.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    settings = get_settings()
    try:
        payload = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.google_client_id
        )
    except Exception as exc:
        raise ValueError("invalid Google ID token") from exc
    if not payload.get("email_verified"):
        raise ValueError("Google email not verified")
    return payload
