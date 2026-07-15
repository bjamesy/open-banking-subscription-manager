"""Registration, login, token refresh, and account deletion (architecture §2.5)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_banking_provider, get_current_user, get_db
from subtrack.db.models import Account, DetectedSubscription, Item, RescanJob, Transaction, User
from subtrack.providers.base import BankingProvider
from subtrack.security import auth, crypto

logger = logging.getLogger(__name__)

router = APIRouter()


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^\S+@\S+\.\S+$")
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class DeleteAccountRequest(BaseModel):
    password: Optional[str] = None


class GoogleLoginRequest(BaseModel):
    id_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _token_pair(user_id: int, version: int) -> TokenPair:
    return TokenPair(
        access_token=auth.create_access_token(user_id),
        refresh_token=auth.create_refresh_token(user_id, version),
    )


@router.post("/register", status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=email, password_hash=auth.hash_password(body.password))
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email}


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_db)) -> TokenPair:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not auth.verify_password(body.password, user.password_hash):
        # Same error for unknown email and wrong password.
        raise HTTPException(status_code=401, detail="invalid credentials")
    return _token_pair(user.id, user.token_version)


@router.post("/google")
def google_login(body: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Verify a Google-issued ID token and log in, creating a User on first
    sign-in. Google accounts get the "!" password sentinel (already used by
    this codebase's own test fixtures for "no real password") — a Google
    login only auto-reuses an existing row when it carries that sentinel;
    a real password on the row means the email was claimed via /auth/register
    first, and we refuse to silently merge identities across auth methods
    (an unverified-email account-takeover vector, since registration has no
    email verification step)."""
    try:
        payload = auth.verify_google_id_token(body.id_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid Google credential")

    email = payload["email"].strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash="!")
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.password_hash != "!":
        raise HTTPException(
            status_code=409,
            detail="an account with this email already exists — sign in with your password",
        )
    return _token_pair(user.id, user.token_version)


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user_id, version = auth.decode_refresh_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    user = db.get(User, user_id)
    if user is None or user.token_version != version:
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    return _token_pair(user.id, user.token_version)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    """Revoke every outstanding refresh token for this user by bumping
    token_version — global, not per-device (architecture §5.5). Access tokens
    are unaffected and remain valid until their short natural expiry."""
    user.token_version += 1
    db.commit()


@router.delete("/me", status_code=204)
def delete_account(
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    provider: BankingProvider = Depends(get_banking_provider),
    db: Session = Depends(get_db),
) -> None:
    """Delete the current user and everything tied to them (architecture
    §6.8 — privacy compliance, right to deletion). Google-only accounts
    (password_hash="!") skip password confirmation — they have none to give,
    and a valid access token is already the trust boundary. Plaid revocation
    is best-effort per Item: a user's right to delete their own data
    shouldn't be blocked by Plaid being briefly unavailable."""
    if user.password_hash != "!":
        if not body.password or not auth.verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="incorrect password")

    items = list(db.scalars(select(Item).where(Item.user_id == user.id)))
    for item in items:
        try:
            provider.remove_item(crypto.decrypt(item.access_token_encrypted))
        except Exception:
            logger.exception(
                "failed to revoke Plaid item %s during account deletion", item.plaid_item_id
            )

    # FK-safe order: children before parents, no DB cascade to lean on.
    item_ids = select(Item.id).where(Item.user_id == user.id)
    account_ids = select(Account.id).where(Account.item_id.in_(item_ids))
    db.execute(delete(DetectedSubscription).where(DetectedSubscription.user_id == user.id))
    db.execute(delete(Transaction).where(Transaction.account_id.in_(account_ids)))
    db.execute(delete(Account).where(Account.item_id.in_(item_ids)))
    db.execute(delete(Item).where(Item.user_id == user.id))
    db.execute(delete(RescanJob).where(RescanJob.user_id == user.id))
    db.delete(user)
    db.commit()
