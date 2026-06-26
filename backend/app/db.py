"""Database engine, session factory, and startup initialization/seeding."""
from __future__ import annotations

import logging
import secrets
from collections.abc import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models_db import Base, User

logger = logging.getLogger("screener.db")

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and seed the first super-user if the database is fresh."""
    Base.metadata.create_all(bind=engine)
    _seed_superuser()


def _seed_superuser() -> None:
    # Imported lazily to avoid a circular import (auth imports config only).
    from .auth import hash_password

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == settings.admin_email))
        if existing is not None:
            return
        password = settings.admin_password or secrets.token_urlsafe(12)
        admin = User(
            email=settings.admin_email,
            display_name="Administrator",
            password_hash=hash_password(password),
            role="superuser",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        if not settings.admin_password:
            logger.warning(
                "Seeded super-user %s with a generated password: %s "
                "(set SCREENER_ADMIN_PASSWORD to control it)",
                settings.admin_email,
                password,
            )
        else:
            logger.info("Seeded super-user %s", settings.admin_email)
