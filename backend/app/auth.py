"""Authentication: password hashing, JWT tokens, and FastAPI dependencies."""
from __future__ import annotations

import datetime as dt
import secrets

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models_db import User

# Token endpoint is informational here; the frontend sends the bearer token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# Fall back to a per-process random secret when none is configured (dev only).
_JWT_SECRET = settings.jwt_secret or secrets.token_urlsafe(48)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (handling the 72-byte input limit)."""
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:  # expired / invalid signature / malformed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(token)
    user = db.get(User, int(payload.get("sub", 0)))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-user privileges required",
        )
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    from sqlalchemy import select

    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
