"""Core domain entities. See architecture.md §4.

Notes:
- `Item.access_token_encrypted` stores the Fernet-encrypted Plaid access token,
  never the plaintext. Encryption/decryption lives in `subtrack.security.crypto`
  and is applied at the service layer, not on the model.
- `Transaction.raw_payload` keeps the full provider object as JSON, stored as
  JSONB on Postgres (indexing/size) and plain JSON under sqlite dev via
  `.with_variant(...)` — one column type, no dialect branching elsewhere
  (architecture §6.7, resolved).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from subtrack.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Bumped on logout to revoke all outstanding refresh tokens (§5.5).
    token_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Item(Base):
    """A Plaid Item: one user's connection to one financial institution."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plaid_item_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    institution_name: Mapped[Optional[str]] = mapped_column(String(255))
    access_token_encrypted: Mapped[str] = mapped_column(String(1024))
    cursor: Mapped[Optional[str]] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), default="active")
    error: Mapped[Optional[str]] = mapped_column(String(512))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    plaid_account_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    mask: Mapped[Optional[str]] = mapped_column(String(16))
    type: Mapped[Optional[str]] = mapped_column(String(64))
    subtype: Mapped[Optional[str]] = mapped_column(String(64))
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    plaid_transaction_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    merchant_raw: Mapped[str] = mapped_column(String(512))
    merchant_normalized: Mapped[Optional[str]] = mapped_column(String(512), index=True)
    posted_at: Mapped[date] = mapped_column(Date, index=True)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DetectedSubscription(Base):
    __tablename__ = "detected_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"))
    merchant_normalized: Mapped[str] = mapped_column(String(512))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    cadence: Mapped[Optional[str]] = mapped_column(String(32))
    confidence_score: Mapped[Optional[float]] = mapped_column()
    # detected | confirmed | dismissed
    status: Mapped[str] = mapped_column(String(32), default="detected")
    next_expected_charge: Mapped[Optional[date]] = mapped_column(Date)
    # heuristic | ai
    detection_source: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RescanJob(Base):
    """Tracks a manual re-scan run as an in-process background task
    (architecture §5.2) so the triggering request can return immediately and
    the frontend can poll for completion."""

    __tablename__ = "rescan_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # pending | running | done | failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    items_synced: Mapped[Optional[int]] = mapped_column()
    items_failed: Mapped[Optional[int]] = mapped_column()
    error: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ConsentRecord(Base):
    """Audit log of privacy-notice consent grants (architecture §6.8) —
    append-only: each row is one grant, not a mutable flag, so there's a
    timestamped record of what was actually agreed to and when."""

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[str] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
