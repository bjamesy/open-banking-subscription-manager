"""FastAPI application entrypoint. Run: uvicorn subtrack.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from subtrack.api.routes import (
    accounts,
    auth,
    health,
    link,
    subscriptions,
    transactions,
    webhooks,
)
from subtrack.config import get_settings
from subtrack.ingestion.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Polling fallback for missed webhooks (disabled in tests via
    # SYNC_POLL_INTERVAL_HOURS=0 or APP_ENV=test).
    if get_settings().app_env != "test":
        start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="SubTrack API", version="0.0.1", lifespan=lifespan)
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
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
    return app


app = create_app()
