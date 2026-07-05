"""Inbound Plaid webhooks (architecture §2.2, §5.2).

TODO(security): verify the Plaid-Verification JWT signature before processing.
Requests with an invalid/missing signature must be rejected with 400.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/plaid")
async def plaid_webhook(request: Request) -> dict:
    payload = await request.json()
    webhook_code = payload.get("webhook_code")
    # TODO: on SYNC_UPDATES_AVAILABLE, enqueue sync_item for the affected item_id.
    return {"status": "received", "webhook_code": webhook_code}
