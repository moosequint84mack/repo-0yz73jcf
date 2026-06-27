"""Database engine, session factory, and startup initialization/seeding."""
from __future__ import annotations

import logging
import secrets
from collections.abc import Iterator
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models_db import Base, SignalLog, TrainingRun, User

if TYPE_CHECKING:
    from typing import Any

    from .ml.model import TrainResult

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


def record_training_run(
    symbol: str,
    exchange: str,
    timeframe: str,
    result: TrainResult,
) -> None:
    """Persist a training run's honest metrics for drift tracking / cabinet analytics.

    Best-effort: failures are logged and swallowed so a DB hiccup never breaks
    training itself.
    """
    bt = result.backtest or {}
    try:
        with SessionLocal() as db:
            db.add(
                TrainingRun(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    accuracy=float(result.accuracy),
                    macro_f1=float(result.macro_f1),
                    weighted_f1=float(result.weighted_f1),
                    n_samples=int(result.n_train) + int(result.n_test),
                    profit_factor=bt.get("profit_factor"),
                    win_rate=bt.get("win_rate"),
                    expectancy=bt.get("expectancy_pct"),
                    trades=bt.get("n_trades"),
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist training run for %s", symbol)


def record_signal(
    symbol: str,
    exchange: str,
    timeframe: str,
    plan: dict[str, Any],
    prediction: dict[str, Any] | None,
) -> None:
    """Persist a signal snapshot for the cabinet activity feed (best-effort)."""
    lev = plan.get("leverage") or {}
    try:
        with SessionLocal() as db:
            db.add(
                SignalLog(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    action=str(plan.get("action", "flat")),
                    confluence=float(plan.get("confluence", 0.0) or 0.0),
                    entry=plan.get("entry"),
                    stop=plan.get("stop"),
                    target=plan.get("target"),
                    leverage=(lev.get("leverage") if isinstance(lev, dict) else None),
                    ml_confidence=(prediction or {}).get("confidence"),
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist signal for %s", symbol)


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
