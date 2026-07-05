"""FastAPI application entrypoint. Run: uvicorn subtrack.main:app --reload"""
from __future__ import annotations

from fastapi import FastAPI

from subtrack.api.routes import auth, health, link, subscriptions, webhooks


def create_app() -> FastAPI:
    app = FastAPI(title="SubTrack API", version="0.0.1")
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(link.router, prefix="/link", tags=["link"])
    app.include_router(
        subscriptions.router, prefix="/subscriptions", tags=["subscriptions"]
    )
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
    return app


app = create_app()
