"""Application configuration."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, overridable via environment variables (prefix SCREENER_)."""

    model_config = SettingsConfigDict(env_prefix="SCREENER_", env_file=".env", extra="ignore")

    # Exchanges enabled for multi-exchange comparison. Must be valid ccxt ids.
    # NOTE: Binance and Bybit return HTTP 451 (geo-restricted) from some server
    # regions; the defaults below are public APIs that respond without keys.
    exchanges: list[str] = ["okx", "kraken", "kucoin", "coinbase", "mexc"]

    # Default exchange used when a request does not specify one.
    default_exchange: str = "okx"

    # Default symbol shown on first load (unified ccxt symbol).
    default_symbol: str = "BTC/USDT"

    # Order-book depth (number of price levels) to fetch per side.
    orderbook_limit: int = 100

    # Candle timeframe and history window used for ML training.
    # Higher timeframe (1h) carries a far better signal/noise ratio than 5m for
    # next-move prediction: trends persist, microstructure noise averages out, so
    # the model and the trade signals are markedly more reliable.
    timeframe: str = "1h"
    history_candles: int = 4000  # ~166 days of 1h candles for richer training

    # --- Prediction target (self-learning) ---
    # How far ahead the classifier predicts, in candles, and the minimum move that
    # counts as up/down (triple-barrier widens this with each coin's ATR). On 1h
    # candles, horizon=8 ≈ an 8-hour outlook and a 1.2% floor filters out chop, so
    # the model learns *meaningful* moves instead of noise.
    ml_horizon: int = 8
    ml_threshold: float = 0.012

    # Density detection: a level is a "wall" if its size >= this many std devs
    # above the mean level size on its side of the book.
    density_zscore_threshold: float = 2.0

    # Cache TTL (seconds) for exchange responses to avoid hammering public APIs.
    cache_ttl_seconds: float = 3.0

    # CORS origins for the frontend dev server.
    cors_origins: list[str] = ["*"]

    # Where trained ML models are persisted.
    model_dir: str = "models"

    # --- Persistence (users, chat, signals, training runs) ---
    # SQLAlchemy URL. Defaults to a local SQLite file; override with
    # SCREENER_DATABASE_URL=postgresql+psycopg://... for a server deployment.
    database_url: str = "sqlite:///./screener.db"

    # --- Authentication ---
    # Secret used to sign JWT access tokens. MUST be overridden in production
    # via SCREENER_JWT_SECRET; a random secret is generated per-process if unset
    # (which invalidates tokens on restart — fine for dev, not for prod).
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # First super-user, seeded at startup if it does not yet exist.
    # Set both to provision the admin account on a fresh database.
    admin_email: str = "admin@screener.io"
    admin_password: str = ""  # if empty, a random one is generated and logged once

    # Whether self-registration is allowed. New accounts are created inactive
    # and must be activated by a super-user before they can log in.
    allow_self_registration: bool = True

    # --- Continuous self-learning ---
    # The screener retrains every pair on a fixed cadence so models keep adapting
    # to fresh market data without any manual "Train" click.
    autotrain_enabled: bool = True
    # Minutes between full retraining cycles of all screener symbols.
    autotrain_interval_minutes: int = 60
    # Wait this many seconds after startup before the first retraining cycle so
    # the API is responsive immediately on boot.
    autotrain_initial_delay_seconds: int = 30
    # Pairs the continuous trainer (and screener) operate on. All are liquid
    # markets available on the public APIs of the enabled exchanges.
    screener_symbols: list[str] = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT", "DOGE/USDT",
        "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "LTC/USDT", "TRX/USDT",
        "BCH/USDT", "ATOM/USDT", "UNI/USDT", "ETC/USDT", "NEAR/USDT", "FIL/USDT",
        "APT/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT", "SUI/USDT", "AAVE/USDT",
    ]


settings = Settings()
