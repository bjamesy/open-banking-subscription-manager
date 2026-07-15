"""FastAPI application entrypoint. Run: uvicorn subtrack.main:app --reload"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from subtrack.api.routes import (
    accounts,
    auth,
    health,
    link,
    subscriptions,
    transactions,
)
from subtrack.config import get_settings

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    # Uvicorn configures its own `uvicorn.*` loggers independently of this —
    # this is what makes `logger.info(...)` calls in app code (subtrack.*)
    # visible at all; without it they're silently dropped below WARNING.
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    _configure_logging()
    logger.info("subtrack starting (log_level=%s)", get_settings().log_level)
    app = FastAPI(title="SubTrack API", version="0.0.1")
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(link.router, prefix="/link", tags=["link"])
    app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
    app.include_router(
        transactions.router, prefix="/transactions", tags=["transactions"]
    )
    app.include_router(
        subscriptions.router, prefix="/subscriptions", tags=["subscriptions"]
    )
    return app


app = create_app()
