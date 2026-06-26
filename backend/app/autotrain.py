"""Continuous self-learning: a background task that periodically retrains every
screener pair so the models keep adapting to fresh market data with no manual
"Train" click.

The loop runs inside the FastAPI event loop. Each cycle fetches the latest
history for a pair and retrains its model off the event loop (LightGBM is
CPU-bound), persisting the model and recording honest metrics for the cabinet.
State of the last/next cycle is exposed via :data:`state` for the UI.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .config import settings
from .db import record_training_run
from .exchanges import manager
from .ml.model import store

logger = logging.getLogger("screener.autotrain")

# Lightweight, JSON-serializable view of the trainer's progress for the API.
state: dict[str, Any] = {
    "enabled": settings.autotrain_enabled,
    "interval_minutes": settings.autotrain_interval_minutes,
    "running": False,
    "cycle": 0,
    "last_started_at": None,
    "last_finished_at": None,
    "next_run_at": None,
    "last_trained": 0,
    "last_failed": 0,
    "current_symbol": None,
    "per_symbol": {},  # symbol -> {ok, accuracy, macro_f1, profit_factor, trained_at, error}
}


async def _train_symbol(symbol: str) -> dict[str, Any]:
    exchange = settings.default_exchange
    timeframe = settings.timeframe
    key = store.make_key(exchange, symbol, timeframe)
    candles = await manager.fetch_ohlcv(
        symbol, exchange, timeframe, settings.history_candles
    )
    model = await asyncio.to_thread(store.train, candles, key, 12, 0.004)
    record_training_run(symbol, exchange, timeframe, model.result)
    bt = model.result.backtest or {}
    return {
        "ok": True,
        "accuracy": model.result.accuracy,
        "macro_f1": model.result.macro_f1,
        "profit_factor": bt.get("profit_factor"),
        "win_rate": bt.get("win_rate"),
        "n_trades": bt.get("n_trades"),
        "trained_at": model.result.trained_at,
    }


async def _run_cycle() -> None:
    state["running"] = True
    state["cycle"] += 1
    state["last_started_at"] = time.time()
    trained = failed = 0
    for symbol in settings.screener_symbols:
        state["current_symbol"] = symbol
        try:
            info = await _train_symbol(symbol)
            state["per_symbol"][symbol] = info
            trained += 1
            logger.info(
                "autotrain %s: acc=%.3f macroF1=%.3f pf=%s",
                symbol,
                info["accuracy"],
                info["macro_f1"],
                info.get("profit_factor"),
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            state["per_symbol"][symbol] = {
                "ok": False,
                "error": str(exc),
                "trained_at": time.time(),
            }
            logger.warning("autotrain %s failed: %s", symbol, exc)
    state["current_symbol"] = None
    state["last_trained"] = trained
    state["last_failed"] = failed
    state["last_finished_at"] = time.time()
    state["running"] = False


async def run_loop() -> None:
    """Forever loop: retrain all pairs every ``autotrain_interval_minutes``."""
    if not settings.autotrain_enabled:
        logger.info("autotrain disabled (SCREENER_AUTOTRAIN_ENABLED=false)")
        return
    await asyncio.sleep(max(0, settings.autotrain_initial_delay_seconds))
    interval = max(60, settings.autotrain_interval_minutes * 60)
    while True:
        try:
            await _run_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("autotrain cycle crashed; will retry next interval")
        state["next_run_at"] = time.time() + interval
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
