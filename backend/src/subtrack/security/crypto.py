"""Symmetric encryption for secrets at rest (Plaid access tokens).

Uses Fernet (from `cryptography`). The key is loaded from ENCRYPTION_KEY and is
never stored in the database. Rotating the key means re-encrypting Item rows.
"""
from __future__ import annotations

from cryptography.fernet import Fernet

from subtrack.config import get_settings


def generate_key() -> str:
    """Generate a new Fernet key. Use to populate ENCRYPTION_KEY."""
    return Fernet.generate_key().decode()


def _cipher() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with "
            "subtrack.security.crypto.generate_key()."
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _cipher().decrypt(ciphertext.encode()).decode()
