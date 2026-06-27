"""ML endpoints: train the pattern classifier and predict the next move."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import autotrain
from ..config import settings
from ..db import record_signal, record_training_run
from ..density import analyze_order_book
from ..exchanges import manager
from ..ml.model import store
from ..signals import build_trade_signal

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/autotrain")
async def autotrain_status() -> dict[str, Any]:
    """Status of the continuous self-learning loop (last/next cycle, per-pair)."""
    return autotrain.state


class TrainRequest(BaseModel):
    symbol: str = Field(default=settings.default_symbol)
    exchange: str = Field(default=settings.default_exchange)
    timeframe: str = Field(default=settings.timeframe)
    history: int = Field(default=settings.history_candles, ge=300, le=20000)
    horizon: int = Field(default=settings.ml_horizon, ge=1, le=200)
    threshold: float = Field(default=settings.ml_threshold, gt=0, le=0.2)


class PredictRequest(BaseModel):
    symbol: str = Field(default=settings.default_symbol)
    exchange: str = Field(default=settings.default_exchange)
    timeframe: str = Field(default=settings.timeframe)


class TrainAllRequest(BaseModel):
    symbols: list[str]
    exchange: str = Field(default=settings.default_exchange)
    timeframe: str = Field(default=settings.timeframe)
    history: int = Field(default=settings.history_candles, ge=300, le=20000)
    horizon: int = Field(default=settings.ml_horizon, ge=1, le=200)
    threshold: float = Field(default=settings.ml_threshold, gt=0, le=0.2)


class SignalRequest(BaseModel):
    symbol: str = Field(default=settings.default_symbol)
    exchange: str = Field(default=settings.default_exchange)
    timeframe: str = Field(default=settings.timeframe)
    reward_ratio: float = Field(default=1.5, ge=0.5, le=5.0)
    proximity_pct: float = Field(default=0.6, ge=0.05, le=5.0)
    min_confidence: float = Field(default=0.34, ge=0.0, le=1.0)
    equity: float = Field(default=1000.0, gt=0, le=1e9)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=100.0)
    leverage: float | None = Field(default=None, ge=1.0, le=500.0)


def _result_payload(result: Any, top_n_features: int = 15) -> dict[str, Any]:
    data = asdict(result)
    importances = data.get("feature_importances", {})
    data["feature_importances"] = dict(list(importances.items())[:top_n_features])
    return data


@router.post("/train")
async def train(req: TrainRequest) -> dict[str, Any]:
    try:
        candles = await manager.fetch_ohlcv(req.symbol, req.exchange, req.timeframe, req.history)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"{req.exchange}: {exc}") from exc

    key = store.make_key(req.exchange, req.symbol, req.timeframe)
    try:
        # LightGBM training is CPU-bound; run it off the event loop.
        model = await asyncio.to_thread(
            store.train, candles, key, req.horizon, req.threshold
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record_training_run(req.symbol, req.exchange, req.timeframe, model.result)
    return {
        "key": key,
        "symbol": req.symbol,
        "exchange": req.exchange,
        "timeframe": req.timeframe,
        "candles_fetched": len(candles),
        "result": _result_payload(model.result),
    }


@router.post("/train-all")
async def train_all(req: TrainAllRequest) -> dict[str, Any]:
    """Batch-train one model per symbol so several pairs can be screened at once."""
    results: list[dict[str, Any]] = []
    for symbol in req.symbols:
        key = store.make_key(req.exchange, symbol, req.timeframe)
        try:
            candles = await manager.fetch_ohlcv(
                symbol, req.exchange, req.timeframe, req.history
            )
            model = await asyncio.to_thread(
                store.train, candles, key, req.horizon, req.threshold
            )
            record_training_run(symbol, req.exchange, req.timeframe, model.result)
            bt = model.result.backtest or {}
            results.append(
                {
                    "symbol": symbol,
                    "key": key,
                    "ok": True,
                    "candles_fetched": len(candles),
                    "accuracy": model.result.accuracy,
                    "macro_f1": model.result.macro_f1,
                    "weighted_f1": model.result.weighted_f1,
                    "n_train": model.result.n_train,
                    "n_test": model.result.n_test,
                    "win_rate": bt.get("win_rate"),
                    "n_trades": bt.get("n_trades"),
                    "profit_factor": bt.get("profit_factor"),
                    "expectancy_pct": bt.get("expectancy_pct"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"symbol": symbol, "key": key, "ok": False, "error": str(exc)})
    return {
        "exchange": req.exchange,
        "timeframe": req.timeframe,
        "history": req.history,
        "trained": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "results": results,
    }


@router.post("/signal")
async def signal(req: SignalRequest) -> dict[str, Any]:
    """Combine order-book density + ML prediction into an actionable trade plan."""
    try:
        ob = await manager.fetch_order_book(req.symbol, req.exchange, settings.orderbook_limit)
        candles = await manager.fetch_ohlcv(req.symbol, req.exchange, req.timeframe, 300)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"{req.exchange}: {exc}") from exc

    analysis = analyze_order_book(ob)

    # Real per-coin leverage from exchange metadata (cached ~1h, never blocks the
    # signal: fall back to None if the venues expose no perpetual market).
    try:
        leverage_info = await manager.fetch_leverage_info(req.symbol)
    except Exception:  # noqa: BLE001
        leverage_info = None

    prediction: dict[str, Any] | None = None
    key = store.make_key(req.exchange, req.symbol, req.timeframe)
    model = store.get(key)
    if model is not None:
        try:
            prediction = store.predict_latest(model, candles)
        except Exception:  # noqa: BLE001
            prediction = None

    plan = build_trade_signal(
        analysis,
        prediction,
        candles,
        proximity_pct=req.proximity_pct,
        reward_ratio=req.reward_ratio,
        min_confidence=req.min_confidence,
        leverage_info=leverage_info,
        equity=req.equity,
        risk_per_trade_pct=req.risk_per_trade_pct,
        leverage_override=req.leverage,
    )
    record_signal(req.symbol, req.exchange, req.timeframe, plan, prediction)
    return {
        "symbol": req.symbol,
        "exchange": req.exchange,
        "timeframe": req.timeframe,
        "model_trained": model is not None,
        "model_accuracy": model.result.accuracy if model is not None else None,
        "backtest": (model.result.backtest if model is not None else None),
        "prediction": prediction,
        "signal": plan,
    }


@router.get("/leverage")
async def leverage(symbol: str = settings.default_symbol) -> dict[str, Any]:
    """Real max leverage per coin, aggregated across the enabled exchanges."""
    try:
        return await manager.fetch_leverage_info(symbol)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/predict")
async def predict(req: PredictRequest) -> dict[str, Any]:
    key = store.make_key(req.exchange, req.symbol, req.timeframe)
    model = store.get(key)
    if model is None:
        raise HTTPException(
            status_code=404,
            detail="No trained model for this symbol/exchange/timeframe. Train one first.",
        )
    try:
        candles = await manager.fetch_ohlcv(req.symbol, req.exchange, req.timeframe, 300)
        prediction = store.predict_latest(model, candles)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    prediction["key"] = key
    prediction["accuracy"] = model.result.accuracy
    prediction["trained_at"] = model.result.trained_at
    return prediction


@router.get("/status")
async def status(
    symbol: str, exchange: str = settings.default_exchange, timeframe: str | None = None
) -> dict[str, Any]:
    timeframe = timeframe or settings.timeframe
    key = store.make_key(exchange, symbol, timeframe)
    model = store.get(key)
    if model is None:
        return {"key": key, "trained": False}
    return {
        "key": key,
        "trained": True,
        "result": _result_payload(model.result),
    }
