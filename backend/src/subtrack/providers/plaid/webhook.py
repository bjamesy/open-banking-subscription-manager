"""Plaid webhook signature verification (architecture §5.2).

Plaid signs webhooks with an ES256 JWT in the `Plaid-Verification` header. The
JWT's `request_body_sha256` claim must match the SHA-256 of the raw request
body. Verification keys are fetched per key-id via the Plaid API.

Webhook payload/signature handling is Plaid-specific by nature and lives here,
not on the BankingProvider ABC (architecture §5.1).
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

# Simple in-process cache of verification keys by key id.
_KEY_CACHE: Dict[str, dict] = {}

# Reject webhooks whose JWT was issued more than 5 minutes ago (Plaid guidance).
MAX_TOKEN_AGE_SECONDS = 5 * 60


def verify_plaid_webhook(body: bytes, verification_header: str) -> bool:
    """Return True iff the Plaid-Verification JWT is valid for this body."""
    try:
        from jose import jwt

        header = jwt.get_unverified_header(verification_header)
        if header.get("alg") != "ES256":
            return False

        key = _get_verification_key(header["kid"])
        claims = jwt.decode(
            verification_header, key, algorithms=["ES256"],
            options={"verify_aud": False},
        )

        issued_at = claims.get("iat", 0)
        if time.time() - issued_at > MAX_TOKEN_AGE_SECONDS:
            return False

        body_hash = hashlib.sha256(body).hexdigest()
        return bool(claims.get("request_body_sha256") == body_hash)
    except Exception:
        logger.warning("Plaid webhook verification failed", exc_info=True)
        return False


def _get_verification_key(key_id: str) -> dict:
    cached = _KEY_CACHE.get(key_id)
    if cached is not None:
        return cached

    from plaid.model.webhook_verification_key_get_request import (
        WebhookVerificationKeyGetRequest,
    )

    from subtrack.providers.plaid.provider import PlaidProvider

    client = PlaidProvider()._client()
    response = client.webhook_verification_key_get(
        WebhookVerificationKeyGetRequest(key_id=key_id)
    )
    key = response.key.to_dict()
    _KEY_CACHE[key_id] = key
    return key
