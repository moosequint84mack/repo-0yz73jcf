"""Out-of-sample backtest of the model's directional signal.

The classifier predicts the next-`horizon` move (down / flat / up). To answer
"how accurate are the trades?" we replay the model's predictions on the held-out
(test) segment with a simple bracket strategy: each non-flat, high-confidence
prediction opens a position with a fixed risk (the training threshold) and a
take-profit at `risk * reward_ratio`. We then walk the following candles bar by
bar and record whether the stop or the target was hit first (a realistic, if
conservative, fill model). The resulting win-rate / profit-factor / expectancy
are computed purely on data the model never saw during fitting.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .features import _atr, market_regime


def _max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough drop of a cumulative-return equity curve (%)."""
    peak = -1e18
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = min(max_dd, v - peak)
    return float(max_dd)


def run_backtest(
    df: pd.DataFrame,
    test_positions: np.ndarray,
    proba: np.ndarray,
    classes: list[int],
    horizon: int,
    threshold: float,
    confidence: float = 0.45,
    reward_ratio: float = 1.5,
    fee_pct: float = 0.05,
    slippage_pct: float = 0.02,
    atr_stop_mult: float = 1.5,
    use_regime_filter: bool = True,
) -> dict[str, Any]:
    """Replay predictions on the test segment with a bracket (stop/target) exit.

    Args:
        df: full candle DataFrame (columns: open/high/low/close...).
        test_positions: df row indices that make up the test segment.
        proba: predict_proba output aligned 1:1 with ``test_positions``.
        classes: class labels in the column order of ``proba`` (0=down,1=flat,2=up).
        horizon: max bars a trade is held before exiting at market.
        threshold: minimum fractional stop distance (floor for the ATR stop).
        confidence: minimum predicted probability required to take a trade.
        reward_ratio: take-profit distance as a multiple of the stop distance.
        fee_pct: exchange fee per side, in percent (round-trip = 2x).
        slippage_pct: assumed slippage per side, in percent (round-trip = 2x).
        atr_stop_mult: stop distance = max(threshold, atr_stop_mult * ATR%); a
            volatility-adaptive stop instead of a fixed percentage.
        use_regime_filter: skip trades taken *against* a strong opposing trend
            (long in a down-trend / short in an up-trend).
    """
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)
    atr_pct = (_atr(df["high"], df["low"], df["close"], 14) / df["close"]).to_numpy(dtype=float)
    regime = market_regime(df)["regime"].to_numpy(dtype=float)

    # Round-trip cost as a fraction of notional (entry + exit fees + slippage).
    cost_frac = 2.0 * (fee_pct + slippage_pct) / 100.0

    class_idx = {c: i for i, c in enumerate(classes)}
    up_col = class_idx.get(2)
    down_col = class_idx.get(0)

    trades: list[dict[str, Any]] = []
    skipped_regime = 0
    # No pyramiding: once a trade is open, ignore new signals until it exits, so
    # trade counts and the equity curve reflect non-overlapping positions.
    next_allowed_pos = -1
    for k, pos in enumerate(test_positions):
        pos = int(pos)
        if pos < next_allowed_pos:
            continue
        p = proba[k]
        p_up = float(p[up_col]) if up_col is not None else 0.0
        p_down = float(p[down_col]) if down_col is not None else 0.0

        if p_up >= confidence and p_up >= p_down:
            direction = 1  # long
            conf = p_up
        elif p_down >= confidence and p_down > p_up:
            direction = -1  # short
            conf = p_down
        else:
            continue

        # Regime filter: don't fight a strong opposing trend.
        if use_regime_filter and pos < len(regime):
            reg = regime[pos]
            if (direction == 1 and reg == -1) or (direction == -1 and reg == 1):
                skipped_regime += 1
                continue

        entry = close[pos]
        if entry <= 0:
            continue
        # Volatility-adaptive stop (ATR), floored at `threshold`.
        a = atr_pct[pos] if pos < len(atr_pct) and not np.isnan(atr_pct[pos]) else threshold
        stop_frac = max(threshold, atr_stop_mult * a)
        tgt_frac = stop_frac * reward_ratio
        if direction == 1:
            stop = entry * (1 - stop_frac)
            target = entry * (1 + tgt_frac)
        else:
            stop = entry * (1 + stop_frac)
            target = entry * (1 - tgt_frac)

        exit_ret = None
        held = 0
        for j in range(pos + 1, min(pos + horizon + 1, n)):
            held = j - pos
            hi, lo = high[j], low[j]
            if direction == 1:
                # Conservative: if a bar spans both levels, assume stop hit first.
                if lo <= stop:
                    exit_ret = -stop_frac
                    break
                if hi >= target:
                    exit_ret = tgt_frac
                    break
            else:
                if hi >= stop:
                    exit_ret = -stop_frac
                    break
                if lo <= target:
                    exit_ret = tgt_frac
                    break
        if exit_ret is None:
            # Timed out: exit at the close `horizon` bars later.
            exit_pos = min(pos + horizon, n - 1)
            exit_ret = (close[exit_pos] / entry - 1) * direction
            held = exit_pos - pos

        # Block new entries until this position has exited (no pyramiding).
        next_allowed_pos = pos + held + 1

        # Apply round-trip transaction costs.
        exit_ret -= cost_frac

        trades.append(
            {
                "direction": "long" if direction == 1 else "short",
                "pnl_pct": float(exit_ret * 100),
                "confidence": conf,
                "held": held,
                "win": exit_ret > 0,
            }
        )

    summary = _summarize(trades, reward_ratio, confidence)
    summary["skipped_by_regime"] = skipped_regime
    summary["cost_pct_round_trip"] = round(cost_frac * 100, 4)
    summary["atr_stop_mult"] = atr_stop_mult
    return summary


def _summarize(
    trades: list[dict[str, Any]], reward_ratio: float, confidence: float
) -> dict[str, Any]:
    n_trades = len(trades)
    if n_trades == 0:
        return {
            "n_trades": 0,
            "note": "No trades met the confidence filter on the test set.",
            "confidence_filter": confidence,
            "reward_ratio": reward_ratio,
        }

    pnls = np.array([t["pnl_pct"] for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())

    equity: list[float] = []
    cum = 0.0
    for p in pnls:
        cum += p
        equity.append(cum)

    longs = [t for t in trades if t["direction"] == "long"]
    shorts = [t for t in trades if t["direction"] == "short"]

    def _wr(group: list[dict[str, Any]]) -> float:
        return float(np.mean([t["win"] for t in group]) * 100) if group else 0.0

    std = float(pnls.std())
    return {
        "n_trades": n_trades,
        "win_rate": float((pnls > 0).mean() * 100),
        "avg_pnl_pct": float(pnls.mean()),
        "expectancy_pct": float(pnls.mean()),
        "avg_win_pct": float(wins.mean()) if wins.size else 0.0,
        "avg_loss_pct": float(losses.mean()) if losses.size else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None,
        "total_return_pct": float(pnls.sum()),
        "max_drawdown_pct": _max_drawdown(equity),
        "sharpe_like": float(pnls.mean() / std) if std > 0 else 0.0,
        "avg_hold_bars": float(np.mean([t["held"] for t in trades])),
        "long_trades": len(longs),
        "short_trades": len(shorts),
        "long_win_rate": _wr(longs),
        "short_win_rate": _wr(shorts),
        "equity_curve": equity,
        "confidence_filter": confidence,
        "reward_ratio": reward_ratio,
    }
