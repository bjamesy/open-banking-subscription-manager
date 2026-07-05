"""Registration and login (architecture §2.5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from subtrack.api.deps import get_db
from subtrack.db.models import User
from subtrack.security import auth

router = APIRouter()


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^\S+@\S+\.\S+$")
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
def login(body: Credentials, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not auth.verify_password(body.password, user.password_hash):
        # Same error for unknown email and wrong password.
        raise HTTPException(status_code=401, detail="invalid credentials")
    return TokenOut(access_token=auth.create_access_token(user.id))
