"""Track how long order-book density walls have been standing.

Order books are polled repeatedly, so by remembering the price of each detected
wall between snapshots we can report how long a wall has held its level (its
"time to live"). Walls drift by a few ticks, so a current wall is matched to a
remembered one when their prices are within a small tolerance on the same side.
State is in-process and best-effort: it resets on restart and prunes walls that
have not been seen recently.
"""
from __future__ import annotations

import threading
import time
from typing import Any

# A wall is considered the "same" wall across snapshots if its price stays
# within this fraction of itself (0.05%), absorbing normal tick-level drift.
_MATCH_TOL_PCT = 0.0005
# Drop a tracked wall once it has not reappeared for this many seconds.
_STALE_SECONDS = 45.0

_lock = threading.Lock()
# (symbol, exchange) -> list of {side, price, first_seen, last_seen}
_tracked: dict[tuple[str, str], list[dict[str, float | str]]] = {}


def annotate_wall_ages(
    symbol: str,
    exchange: str,
    walls: list[dict[str, Any]],
    now: float | None = None,
) -> None:
    """Add an ``age_seconds`` field to each wall, in place.

    Matches each current wall to a previously seen wall on the same side within
    a small price tolerance to estimate how long it has been standing.
    """
    now = time.time() if now is None else now
    key = (symbol, exchange)
    with _lock:
        records = [
            r for r in _tracked.get(key, []) if now - float(r["last_seen"]) <= _STALE_SECONDS
        ]
        matched: set[int] = set()
        for wall in walls:
            price = float(wall["price"])
            side = wall.get("side")
            best_idx = -1
            best_diff = _MATCH_TOL_PCT
            for idx, rec in enumerate(records):
                if idx in matched or rec["side"] != side or price <= 0:
                    continue
                diff = abs(float(rec["price"]) - price) / price
                if diff <= best_diff:
                    best_diff = diff
                    best_idx = idx
            if best_idx >= 0:
                rec = records[best_idx]
                rec["price"] = price
                rec["last_seen"] = now
                matched.add(best_idx)
                first_seen = float(rec["first_seen"])
            else:
                records.append(
                    {"side": side, "price": price, "first_seen": now, "last_seen": now}
                )
                first_seen = now
            wall["age_seconds"] = max(0.0, now - first_seen)
        _tracked[key] = records
