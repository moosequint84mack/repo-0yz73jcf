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


def _regime(candles: list[list[float]]) -> int:
    """Trend regime from EMA20/EMA50 separation scaled by ATR.

    Returns 1 (up-trend), -1 (down-trend) or 0 (range), mirroring the backtest
    filter so the live signal won't fight a strong opposing trend.
    """
    if len(candles) < 60:
        return 0
    arr = np.array(candles, dtype=float)
    close = arr[:, 4]
    ema_fast = _ema(close, 20)
    ema_slow = _ema(close, 50)
    atr = _atr(candles)
    if atr <= 0:
        return 0
    sep = (ema_fast - ema_slow) / atr
    if sep > 0.5:
        return 1
    if sep < -0.5:
        return -1
    return 0


def _ema(values: np.ndarray, span: int) -> float:
    """Last value of an exponential moving average."""
    alpha = 2.0 / (span + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return float(ema)


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

    # Real maintenance-margin rate (MMR): a position is liquidated once losses
    # consume the initial margin *minus* the exchange's maintenance margin, so the
    # liquidation sits closer to entry than the naive entry·(1∓1/L). Use the
    # exchange-reported rate when available, else a typical 0.5% tier.
    mmr = float((leverage_info or {}).get("maintenance_margin_rate") or 0.005)
    liq_distance_frac = max(1e-6, 1.0 / leverage - mmr)
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
        "maintenance_margin_rate": mmr,
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
    regime = _regime(candles)

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

    raw_near_support = sup_dist is not None and 0 <= sup_dist <= proximity_pct
    raw_near_resistance = res_dist is not None and 0 <= res_dist <= proximity_pct

    # Deterministic density edge: when price is sandwiched between a bid and an ask
    # wall, the *nearer* wall is the one price is actually leaning on, so only it
    # casts a directional vote. Naively counting both walls makes their votes
    # cancel and the signal collapses to flat even on a clean bounce setup.
    near_support = raw_near_support
    near_resistance = raw_near_resistance
    if raw_near_support and raw_near_resistance:
        if sup_dist <= res_dist:
            near_resistance = False
        else:
            near_support = False

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

    # A clean bounce off a density wall (score ±1.0) is itself a deterministic,
    # verifiable edge — it no longer needs the ML model to agree before firing, so
    # the screener actually surfaces LONG/SHORT setups instead of staying flat.
    if score >= 1.0:
        action = "long"
    elif score <= -1.0:
        action = "short"

    # ---- Market-regime filter ------------------------------------------
    # Don't fight a strong opposing trend (long in a down-trend / vice versa).
    regime_label = {1: "up-trend", -1: "down-trend", 0: "range"}[regime]
    vetoed_by_regime = False
    if action == "long" and regime == -1:
        vetoed_by_regime = True
    elif action == "short" and regime == 1:
        vetoed_by_regime = True
    if vetoed_by_regime:
        rationale.append(
            f"Regime filter: market is in a {regime_label}; vetoing counter-trend "
            f"{action} → flat."
        )
        action = "flat"

    # ---- Build the trade plan ------------------------------------------
    plan: dict[str, Any] = {
        "action": action,
        "confluence": round(float(score), 3),
        "mid": mid,
        "imbalance": imbalance,
        "atr": atr,
        "regime": regime,
        "regime_label": regime_label,
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

    risk_pct = float(abs(entry - stop) / entry * 100)
    reward_pct = float(reward / entry * 100)
    plan.update(
        {
            "entry": float(entry),
            "stop": float(stop),
            "target": float(target),
            "risk_pct": risk_pct,
            "reward_pct": reward_pct,
            # Plain-language, unambiguous restatement of the plan for the UI.
            "direction": action,  # "long" | "short"
            "expected_profit_pct": reward_pct,  # if the target is reached
            "expected_loss_pct": risk_pct,  # if the stop is hit
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
