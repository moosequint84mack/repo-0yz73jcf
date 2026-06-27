"""Order-book density (liquidity wall) detection and heatmap construction."""
from __future__ import annotations

from typing import Any

import numpy as np

from .config import settings


def _levels_to_arrays(levels: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    if not levels:
        return np.array([]), np.array([])
    arr = np.array(levels, dtype=float)
    prices = arr[:, 0]
    amounts = arr[:, 1]
    return prices, amounts


def detect_walls(
    levels: list[list[float]], side: str, zscore_threshold: float | None = None
) -> list[dict[str, Any]]:
    """Return levels whose notional size is a statistical outlier (a 'wall')."""
    zscore_threshold = (
        zscore_threshold if zscore_threshold is not None else settings.density_zscore_threshold
    )
    prices, amounts = _levels_to_arrays(levels)
    if prices.size == 0:
        return []
    notional = prices * amounts
    mean = notional.mean()
    std = notional.std()
    walls: list[dict[str, Any]] = []
    for price, amount, notv in zip(prices, amounts, notional, strict=True):
        z = (notv - mean) / std if std > 0 else 0.0
        if z >= zscore_threshold:
            walls.append(
                {
                    "price": float(price),
                    "amount": float(amount),
                    "notional": float(notv),
                    "zscore": float(z),
                    "side": side,
                }
            )
    walls.sort(key=lambda w: w["notional"], reverse=True)
    return walls


def build_heatmap(
    bids: list[list[float]], asks: list[list[float]], bins: int = 60
) -> dict[str, Any]:
    """Bucket order-book notional into price bins for a density heatmap."""
    bid_p, bid_a = _levels_to_arrays(bids)
    ask_p, ask_a = _levels_to_arrays(asks)
    if bid_p.size == 0 or ask_p.size == 0:
        return {"bins": [], "max_notional": 0.0}

    lo = float(min(bid_p.min(), ask_p.min()))
    hi = float(max(bid_p.max(), ask_p.max()))
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)

    bid_notional = bid_p * bid_a
    ask_notional = ask_p * ask_a
    bid_hist, _ = np.histogram(bid_p, bins=edges, weights=bid_notional)
    ask_hist, _ = np.histogram(ask_p, bins=edges, weights=ask_notional)

    out_bins: list[dict[str, Any]] = []
    max_notional = float(max(bid_hist.max(initial=0.0), ask_hist.max(initial=0.0)))
    for i in range(bins):
        out_bins.append(
            {
                "price_low": float(edges[i]),
                "price_high": float(edges[i + 1]),
                "price_mid": float((edges[i] + edges[i + 1]) / 2),
                "bid_notional": float(bid_hist[i]),
                "ask_notional": float(ask_hist[i]),
            }
        )
    return {"bins": out_bins, "max_notional": max_notional}


def order_book_metrics(bids: list[list[float]], asks: list[list[float]]) -> dict[str, Any]:
    """Spread, mid price, and bid/ask imbalance from the top of the book."""
    bid_p, bid_a = _levels_to_arrays(bids)
    ask_p, ask_a = _levels_to_arrays(asks)
    if bid_p.size == 0 or ask_p.size == 0:
        return {
            "best_bid": None,
            "best_ask": None,
            "mid": None,
            "spread": None,
            "spread_pct": None,
            "bid_notional": 0.0,
            "ask_notional": 0.0,
            "imbalance": 0.0,
        }
    best_bid = float(bid_p[0])
    best_ask = float(ask_p[0])
    mid = (best_bid + best_ask) / 2
    spread = best_ask - best_bid
    bid_notional = float((bid_p * bid_a).sum())
    ask_notional = float((ask_p * ask_a).sum())
    total = bid_notional + ask_notional
    imbalance = (bid_notional - ask_notional) / total if total > 0 else 0.0
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread": spread,
        "spread_pct": (spread / mid * 100) if mid else None,
        "bid_notional": bid_notional,
        "ask_notional": ask_notional,
        "imbalance": imbalance,
    }


def analyze_order_book(ob: dict[str, Any], zscore_threshold: float | None = None) -> dict[str, Any]:
    """Full density analysis for a single order book."""
    bids = ob.get("bids", []) or []
    asks = ob.get("asks", []) or []
    bid_walls = detect_walls(bids, "bid", zscore_threshold)
    ask_walls = detect_walls(asks, "ask", zscore_threshold)
    metrics = order_book_metrics(bids, asks)
    heatmap = build_heatmap(bids, asks)

    # Nearest significant wall on each side relative to mid.
    mid = metrics.get("mid")
    support = bid_walls[0] if bid_walls else None
    resistance = ask_walls[0] if ask_walls else None
    return {
        "metrics": metrics,
        "bid_walls": bid_walls,
        "ask_walls": ask_walls,
        "support": support,
        "resistance": resistance,
        "heatmap": heatmap,
        "mid": mid,
    }
