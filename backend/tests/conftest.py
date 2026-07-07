from __future__ import annotations

import os

# Deterministic settings for tests before subtrack.config is imported anywhere.
# Values are FORCED (not setdefault): pydantic-settings also reads backend/.env,
# and a real ANTHROPIC_API_KEY there would make tests call the live API.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_subtrack.db"
os.environ["PLAID_VERIFY_WEBHOOKS"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["PLAID_CLIENT_ID"] = ""
os.environ["PLAID_SECRET"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from subtrack.api.deps import get_db
from subtrack.db.base import Base
from subtrack.main import app


@pytest.fixture()
def client():
    """TestClient backed by a fresh shared in-memory database per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        # Expose the sessionmaker so tests can seed data behind the API.
        test_client.sessionmaker = TestingSession
        yield test_client
    finally:
        app.dependency_overrides.clear()
