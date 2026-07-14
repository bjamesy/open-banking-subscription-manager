"""FastAPI application entrypoint. Run: uvicorn subtrack.main:app --reload"""
from __future__ import annotations

from fastapi import FastAPI

from subtrack.api.routes import (
    accounts,
    auth,
    health,
    link,
    subscriptions,
    transactions,
)


def create_app() -> FastAPI:
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
