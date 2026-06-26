"""Cross-exchange price comparison and divergence/arbitrage detection."""
from __future__ import annotations

import asyncio
from typing import Any

from .exchanges import manager


async def _one_exchange_snapshot(symbol: str, exchange_id: str) -> dict[str, Any] | None:
    try:
        if not await manager.has_symbol(symbol, exchange_id):
            return None
        ticker = await manager.fetch_ticker(symbol, exchange_id)
        last = ticker.get("last") or ticker.get("close")
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        if last is None and bid is not None and ask is not None:
            last = (bid + ask) / 2
        if last is None:
            return None
        return {
            "exchange": exchange_id,
            "last": float(last),
            "bid": float(bid) if bid is not None else None,
            "ask": float(ask) if ask is not None else None,
            "base_volume": float(ticker.get("baseVolume") or 0.0),
            "quote_volume": float(ticker.get("quoteVolume") or 0.0),
        }
    except Exception as exc:  # noqa: BLE001 - one bad exchange must not kill the comparison
        return {"exchange": exchange_id, "error": str(exc)}


async def compare_exchanges(symbol: str, exchange_ids: list[str]) -> dict[str, Any]:
    """Fetch the same symbol across exchanges and quantify price divergence."""
    snapshots = await asyncio.gather(
        *(_one_exchange_snapshot(symbol, ex) for ex in exchange_ids)
    )
    valid = [s for s in snapshots if s and "last" in s]
    errors = [s for s in snapshots if s and "error" in s]

    result: dict[str, Any] = {
        "symbol": symbol,
        "exchanges": valid,
        "unavailable": [e["exchange"] for e in errors],
    }
    if len(valid) < 2:
        result["divergence"] = None
        return result

    prices = [s["last"] for s in valid]
    cheapest = min(valid, key=lambda s: s["last"])
    priciest = max(valid, key=lambda s: s["last"])
    avg = sum(prices) / len(prices)
    spread_abs = priciest["last"] - cheapest["last"]
    spread_pct = (spread_abs / cheapest["last"] * 100) if cheapest["last"] else 0.0

    # Per-exchange deviation from the cross-exchange average.
    for s in valid:
        s["deviation_pct"] = (s["last"] - avg) / avg * 100 if avg else 0.0

    result["divergence"] = {
        "average": avg,
        "min": cheapest["last"],
        "max": priciest["last"],
        "spread_abs": spread_abs,
        "spread_pct": spread_pct,
        "cheapest_exchange": cheapest["exchange"],
        "priciest_exchange": priciest["exchange"],
        # Naive arbitrage hint: buy on cheapest ask, sell on priciest bid.
        "arb_buy": cheapest["exchange"],
        "arb_sell": priciest["exchange"],
    }
    return result
