"""Market-data endpoints: candles, order-book density, cross-exchange comparison."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..comparison import compare_exchanges
from ..config import settings
from ..density import analyze_order_book
from ..density_tracker import annotate_wall_ages
from ..exchanges import manager

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/config")
async def get_config() -> dict[str, Any]:
    """Expose default configuration so the frontend can populate controls."""
    return {
        "exchanges": settings.exchanges,
        "default_exchange": settings.default_exchange,
        "default_symbol": settings.default_symbol,
        "symbols": settings.screener_symbols,
        "timeframe": settings.timeframe,
        "orderbook_limit": settings.orderbook_limit,
        "history_candles": settings.history_candles,
    }


@router.get("/candles")
async def get_candles(
    symbol: str = Query(default=settings.default_symbol),
    exchange: str = Query(default=settings.default_exchange),
    timeframe: str = Query(default=settings.timeframe),
    limit: int = Query(default=500, ge=10, le=10000),
) -> dict[str, Any]:
    try:
        candles = await manager.fetch_ohlcv(symbol, exchange, timeframe, limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"{exchange}: {exc}") from exc
    return {
        "symbol": symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "candles": [
            {"time": int(c[0] // 1000), "open": c[1], "high": c[2], "low": c[3],
             "close": c[4], "volume": c[5]}
            for c in candles
        ],
    }


@router.get("/orderbook")
async def get_orderbook(
    symbol: str = Query(default=settings.default_symbol),
    exchange: str = Query(default=settings.default_exchange),
    limit: int = Query(default=settings.orderbook_limit, ge=5, le=1000),
    zscore: float | None = Query(default=None),
) -> dict[str, Any]:
    try:
        ob = await manager.fetch_order_book(symbol, exchange, limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"{exchange}: {exc}") from exc
    analysis = analyze_order_book(ob, zscore_threshold=zscore)
    all_walls = analysis.get("bid_walls", []) + analysis.get("ask_walls", [])
    annotate_wall_ages(symbol, exchange, all_walls)
    analysis.update({"symbol": symbol, "exchange": exchange})
    return analysis


@router.get("/compare")
async def get_comparison(
    symbol: str = Query(default=settings.default_symbol),
    exchanges: str | None = Query(default=None, description="Comma-separated ccxt ids"),
) -> dict[str, Any]:
    exchange_ids = (
        [e.strip() for e in exchanges.split(",") if e.strip()]
        if exchanges
        else settings.exchanges
    )
    return await compare_exchanges(symbol, exchange_ids)
