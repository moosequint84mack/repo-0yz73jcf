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
    timeframe: str = "5m"
    history_candles: int = 16000  # ~2 months of 5m candles for richer training

    # Density detection: a level is a "wall" if its size >= this many std devs
    # above the mean level size on its side of the book.
    density_zscore_threshold: float = 2.0

    # Cache TTL (seconds) for exchange responses to avoid hammering public APIs.
    cache_ttl_seconds: float = 3.0

    # CORS origins for the frontend dev server.
    cors_origins: list[str] = ["*"]

    # Where trained ML models are persisted.
    model_dir: str = "models"


settings = Settings()
