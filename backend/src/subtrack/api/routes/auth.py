"""Registration, login, and token refresh (architecture §2.5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_current_user, get_db
from subtrack.db.models import User
from subtrack.security import auth

router = APIRouter()


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^\S+@\S+\.\S+$")
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


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
