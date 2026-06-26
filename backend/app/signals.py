"""Trade-signal engine: turn density + ML prediction into actionable entries.

Combines three independent pieces of evidence into a single long / short / flat
trade plan with concrete entry, stop and take-profit levels:

1. Order-book density — the nearest liquidity walls act as support (bid wall
   below price) and resistance (ask wall above price).
2. Bounce-off-density — when price sits right on top of a wall, that wall tends
   to reject price; a bounce off support is a long setup, a rejection at
   resistance is a short setup.
3. ML prediction — the trained classifier's directional bias (up/down) and
   confidence either confirm or veto the order-book setup.

Stops are placed just beyond the protecting wall; targets are taken at the
opposing wall (or an ATR-based projection when no opposing wall exists).
"""
from __future__ import annotations

from typing import Any

import numpy as np


def _atr(candles: list[list[float]], period: int = 14) -> float:
    """Average true range from ccxt OHLCV rows [ts, o, h, l, c, v]."""
    if len(candles) < period + 1:
        return 0.0
    arr = np.array(candles, dtype=float)
    high, low, close = arr[:, 2], arr[:, 3], arr[:, 4]
    prev_close = close[:-1]
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)),
    )
    return float(tr[-period:].mean())


def compute_leveraged_trade(
    action: str,
    entry: float,
    stop: float,
    target: float,
    leverage_info: dict[str, Any] | None,
    equity: float,
    risk_per_trade_pct: float,
    leverage_override: float | None = None,
) -> dict[str, Any]:
    """Size a leveraged position from real per-coin leverage and account risk.

    Position sizing is risk-based: notional is chosen so that hitting the stop
    loses exactly `risk_per_trade_pct` of equity. Leverage then determines the
    margin posted and the return-on-margin (ROE), and sets the liquidation price
    (isolated-margin approximation: liq ≈ entry·(1 ∓ 1/L), before fees and the
    exchange's maintenance margin, so the real liquidation sits slightly closer).
    """
    stop_frac = abs(entry - stop) / entry
    reward_frac = abs(target - entry) / entry
    if stop_frac <= 0:
        return {"applicable": False, "reason": "Degenerate stop distance."}

    max_available = (leverage_info or {}).get("max_leverage")
    # Recommended leverage keeps liquidation at least 2x beyond the stop.
    safety_capped = max(1.0, 1.0 / (2.0 * stop_frac))
    if leverage_override is not None and leverage_override > 0:
        leverage = leverage_override
    else:
        leverage = safety_capped
    # Never exceed what exchanges actually offer; otherwise apply a sane hard cap.
    hard_cap = max_available if max_available else 20.0
    leverage = float(max(1.0, min(leverage, hard_cap)))

    risk_amount = equity * (risk_per_trade_pct / 100.0)
    notional = risk_amount / stop_frac
    base_qty = notional / entry
    margin_required = notional / leverage
    profit_usd = notional * reward_frac
    loss_usd = notional * stop_frac  # equals risk_amount by construction

    liq_distance_frac = 1.0 / leverage
    if action == "long":
        liq_price = entry * (1.0 - liq_distance_frac)
        stop_before_liq = stop > liq_price
    else:
        liq_price = entry * (1.0 + liq_distance_frac)
        stop_before_liq = stop < liq_price

    return {
        "applicable": True,
        "leverage": round(leverage, 2),
        "max_leverage_available": max_available,
        "recommended_leverage": round(float(max(1.0, min(safety_capped, hard_cap))), 2),
        "equity": equity,
        "risk_per_trade_pct": risk_per_trade_pct,
        "risk_amount": round(risk_amount, 2),
        "notional": round(notional, 2),
        "position_size_base": base_qty,
        "margin_required": round(margin_required, 2),
        "profit_usd": round(profit_usd, 2),
        "loss_usd": round(loss_usd, 2),
        "roe_target_pct": round(reward_frac * leverage * 100, 2),
        "roe_stop_pct": round(-stop_frac * leverage * 100, 2),
        "liquidation_price": float(liq_price),
        "liquidation_distance_pct": round(liq_distance_frac * 100, 3),
        "stop_before_liquidation": bool(stop_before_liq),
    }


def build_trade_signal(
    analysis: dict[str, Any],
    prediction: dict[str, Any] | None,
    candles: list[list[float]],
    proximity_pct: float = 0.6,
    reward_ratio: float = 1.5,
    min_confidence: float = 0.40,
    leverage_info: dict[str, Any] | None = None,
    equity: float = 1000.0,
    risk_per_trade_pct: float = 1.0,
    leverage_override: float | None = None,
) -> dict[str, Any]:
    """Produce a trade plan from order-book analysis + an optional ML prediction."""
    metrics = analysis.get("metrics", {})
    mid = analysis.get("mid") or metrics.get("mid")
    imbalance = float(metrics.get("imbalance") or 0.0)
    atr = _atr(candles)

    rationale: list[str] = []

    if mid is None:
        return {
            "action": "flat",
            "reason": "No order-book mid price available.",
            "rationale": [],
        }

    # Nearest wall on each side (closest level that price could bounce off),
    # falling back to the strongest wall when nothing is nearby.
    bid_walls = [w for w in analysis.get("bid_walls", []) if w["price"] < mid]
    ask_walls = [w for w in analysis.get("ask_walls", []) if w["price"] > mid]
    support = max(bid_walls, key=lambda w: w["price"]) if bid_walls else analysis.get("support")
    resistance = (
        min(ask_walls, key=lambda w: w["price"]) if ask_walls else analysis.get("resistance")
    )

    # Distance to the nearest protecting walls, as a percentage of price.
    sup_dist = ((mid - support["price"]) / mid * 100) if support else None
    res_dist = ((resistance["price"] - mid) / mid * 100) if resistance else None

    near_support = sup_dist is not None and 0 <= sup_dist <= proximity_pct
    near_resistance = res_dist is not None and 0 <= res_dist <= proximity_pct

    # ML directional bias.
    ml_dir = prediction.get("prediction") if prediction else None
    ml_conf = float(prediction.get("confidence", 0.0)) if prediction else 0.0
    probs = prediction.get("probabilities", {}) if prediction else {}
    p_up = float(probs.get("up", 0.0))
    p_down = float(probs.get("down", 0.0))

    bounce = {
        "detected": bool(near_support or near_resistance),
        "side": "support" if near_support else ("resistance" if near_resistance else None),
        "wall": support if near_support else (resistance if near_resistance else None),
        "distance_pct": sup_dist if near_support else (res_dist if near_resistance else None),
    }

    # ---- Decision logic -------------------------------------------------
    action = "flat"
    score = 0.0  # signed conviction, + = long, - = short

    if near_support:
        score += 1.0
        rationale.append(
            f"Price sits {sup_dist:.2f}% above a bid wall at {support['price']:.2f} "
            f"(z={support['zscore']:.1f}) → potential bounce up."
        )
    if near_resistance:
        score -= 1.0
        rationale.append(
            f"Price sits {res_dist:.2f}% below an ask wall at {resistance['price']:.2f} "
            f"(z={resistance['zscore']:.1f}) → potential rejection down."
        )

    if ml_dir == "up" and ml_conf >= min_confidence:
        score += 1.0
        rationale.append(f"ML predicts UP ({p_up * 100:.0f}% conf) over the horizon.")
    elif ml_dir == "down" and ml_conf >= min_confidence:
        score -= 1.0
        rationale.append(f"ML predicts DOWN ({p_down * 100:.0f}% conf) over the horizon.")

    if imbalance >= 0.15:
        score += 0.5
        rationale.append(f"Order-book imbalance +{imbalance * 100:.0f}% favours bids.")
    elif imbalance <= -0.15:
        score -= 0.5
        rationale.append(f"Order-book imbalance {imbalance * 100:.0f}% favours asks.")

    if score >= 1.5:
        action = "long"
    elif score <= -1.5:
        action = "short"

    # ---- Build the trade plan ------------------------------------------
    plan: dict[str, Any] = {
        "action": action,
        "mid": mid,
        "imbalance": imbalance,
        "atr": atr,
        "ml_direction": ml_dir,
        "ml_confidence": ml_conf,
        "bounce": bounce,
        "rationale": rationale,
        "reward_ratio": reward_ratio,
        "leverage_info": leverage_info,
    }

    if action == "flat":
        plan["reason"] = (
            "No confluence between order-book density and ML bias; staying flat."
        )
        return plan

    # Stop distance: just beyond the protecting wall, else an ATR fallback.
    atr_stop = atr if atr > 0 else mid * 0.004
    if action == "long":
        entry = mid
        wall_stop = support["price"] * (1 - 0.001) if support else entry - atr_stop
        stop = min(wall_stop, entry - atr_stop * 0.5)
        risk = entry - stop
        # Target: opposing wall if it offers room, else risk * reward_ratio.
        tp_wall = resistance["price"] if resistance and resistance["price"] > entry else None
        tp_rr = entry + risk * reward_ratio
        target = max(tp_rr, tp_wall) if tp_wall else tp_rr
    else:  # short
        entry = mid
        wall_stop = resistance["price"] * (1 + 0.001) if resistance else entry + atr_stop
        stop = max(wall_stop, entry + atr_stop * 0.5)
        risk = stop - entry
        tp_wall = support["price"] if support and support["price"] < entry else None
        tp_rr = entry - risk * reward_ratio
        target = min(tp_rr, tp_wall) if tp_wall else tp_rr

    reward = abs(target - entry)
    rr = (reward / risk) if risk > 0 else None
    # Conviction-weighted confidence: blend ML confidence and density score.
    conviction = min(1.0, abs(score) / 3.0)
    confidence = round(0.5 * ml_conf + 0.5 * conviction, 4)

    plan.update(
        {
            "entry": float(entry),
            "stop": float(stop),
            "target": float(target),
            "risk_pct": float(abs(entry - stop) / entry * 100),
            "reward_pct": float(reward / entry * 100),
            "risk_reward": float(rr) if rr is not None else None,
            "confidence": confidence,
            "support": support,
            "resistance": resistance,
        }
    )

    # Leveraged position sizing from real per-coin exchange leverage.
    plan["leverage"] = compute_leveraged_trade(
        action=action,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        leverage_info=leverage_info,
        equity=equity,
        risk_per_trade_pct=risk_per_trade_pct,
        leverage_override=leverage_override,
    )
    return plan
