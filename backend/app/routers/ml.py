"""ML endpoints: train the pattern classifier and predict the next move."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..exchanges import manager
from ..ml.model import store

router = APIRouter(prefix="/api/ml", tags=["ml"])


class TrainRequest(BaseModel):
    symbol: str = Field(default=settings.default_symbol)
    exchange: str = Field(default=settings.default_exchange)
    timeframe: str = Field(default=settings.timeframe)
    history: int = Field(default=settings.history_candles, ge=300, le=20000)
    horizon: int = Field(default=12, ge=1, le=200)
    threshold: float = Field(default=0.004, gt=0, le=0.2)


class PredictRequest(BaseModel):
    symbol: str = Field(default=settings.default_symbol)
    exchange: str = Field(default=settings.default_exchange)
    timeframe: str = Field(default=settings.timeframe)


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

    return {
        "key": key,
        "symbol": req.symbol,
        "exchange": req.exchange,
        "timeframe": req.timeframe,
        "candles_fetched": len(candles),
        "result": _result_payload(model.result),
    }


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
