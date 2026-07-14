"""Application configuration, loaded from environment variables.

All secrets (Plaid credentials, Anthropic key, Fernet encryption key, JWT secret)
come from the environment only and are never written to the database.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"

    # Persistence
    database_url: str = "sqlite:///./subtrack.db"

    # Plaid (see providers/plaid). PLAID_ENV is sandbox | production.
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    # SubTrack targets Canada; verify Plaid coverage (architecture §6.2).
    plaid_country_codes: str = "CA"
    plaid_products: str = "transactions"
    plaid_client_name: str = "SubTrack"

    # Anthropic (AI-assisted detection). Model is an open question (§6.5).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # Detection (§2.4). Heuristic candidates below the threshold are escalated
    # to the AI pass (when an API key is configured).
    detection_confidence_threshold: float = 0.7
    detection_min_occurrences: int = 2

    # Fernet key for encrypting Plaid access tokens at rest.
    encryption_key: str = ""

    # Auth (§6.4)
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    @property
    def plaid_country_codes_list(self) -> List[str]:
        return [c.strip() for c in self.plaid_country_codes.split(",") if c.strip()]

    @property
    def plaid_products_list(self) -> List[str]:
        return [p.strip() for p in self.plaid_products.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
