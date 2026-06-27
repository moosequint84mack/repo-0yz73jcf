"""SQLAlchemy ORM models for users, chat, signal history, and training runs."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Roles: "superuser" (admin) or "user".
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    # Inactive users cannot log in until a super-user activates them.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_superuser(self) -> bool:
        return self.role == "superuser"


class ChatMessage(Base):
    """Direct message between two users (user-to-user or user-to-support)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sender: Mapped[User] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped[User] = relationship("User", foreign_keys=[recipient_id])


class SignalLog(Base):
    """A signal snapshot persisted for analytics/history in the user cabinet."""

    __tablename__ = "signal_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # long/short/flat
    confluence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class TrainingRun(Base):
    """Persisted training metrics per pair (for drift tracking / cabinet analytics)."""

    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    macro_f1: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weighted_f1: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    n_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
