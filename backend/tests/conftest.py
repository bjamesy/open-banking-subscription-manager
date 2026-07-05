from __future__ import annotations

import os

# Deterministic settings for tests before subtrack.config is imported anywhere.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_subtrack.db")
