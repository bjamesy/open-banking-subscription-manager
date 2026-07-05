from __future__ import annotations

import subtrack.config as config_module
from subtrack.security import crypto


def test_roundtrip(monkeypatch) -> None:
    key = crypto.generate_key()
    # Point settings at a known key without touching the environment/.env.
    settings = config_module.get_settings()
    monkeypatch.setattr(settings, "encryption_key", key, raising=False)

    secret = "access-sandbox-abc123"
    encrypted = crypto.encrypt(secret)

    assert encrypted != secret
    assert crypto.decrypt(encrypted) == secret
