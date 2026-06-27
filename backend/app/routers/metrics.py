"""User-cabinet analytics: training-run metrics and signal history from the DB."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models_db import SignalLog, TrainingRun

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _run_payload(run: TrainingRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat(),
        "symbol": run.symbol,
        "exchange": run.exchange,
        "timeframe": run.timeframe,
        "accuracy": run.accuracy,
        "macro_f1": run.macro_f1,
        "weighted_f1": run.weighted_f1,
        "n_samples": run.n_samples,
        "profit_factor": run.profit_factor,
        "win_rate": run.win_rate,
        "expectancy": run.expectancy,
        "trades": run.trades,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Aggregate cabinet metrics: latest training run per pair + portfolio summary."""
    runs = list(db.scalars(select(TrainingRun).order_by(TrainingRun.created_at.desc())))
    latest_by_symbol: dict[str, TrainingRun] = {}
    for run in runs:
        if run.symbol not in latest_by_symbol:
            latest_by_symbol[run.symbol] = run

    per_pair = sorted(
        (_run_payload(r) for r in latest_by_symbol.values()),
        key=lambda r: (r["profit_factor"] or 0.0),
        reverse=True,
    )

    profitable = [p for p in per_pair if (p["profit_factor"] or 0) > 1.0]
    accs = [p["accuracy"] for p in per_pair if p["accuracy"] is not None]
    f1s = [p["macro_f1"] for p in per_pair if p["macro_f1"] is not None]

    return {
        "pairs_trained": len(per_pair),
        "pairs_profitable": len(profitable),
        "avg_accuracy": round(sum(accs) / len(accs), 4) if accs else None,
        "avg_macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "total_training_runs": len(runs),
        "per_pair": per_pair,
    }


@router.get("/history")
def history(symbol: str, limit: int = 50, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Training-run history for one pair, oldest→newest, for drift charts."""
    runs = list(
        db.scalars(
            select(TrainingRun)
            .where(TrainingRun.symbol == symbol)
            .order_by(TrainingRun.created_at.desc())
            .limit(limit)
        )
    )
    runs.reverse()
    return {"symbol": symbol, "runs": [_run_payload(r) for r in runs]}


@router.get("/signals")
def signals(limit: int = 100, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Recent persisted signal snapshots for the cabinet activity feed."""
    logs = list(
        db.scalars(select(SignalLog).order_by(SignalLog.created_at.desc()).limit(limit))
    )
    by_action = dict(
        db.execute(
            select(SignalLog.action, func.count(SignalLog.id)).group_by(SignalLog.action)
        ).all()
    )
    return {
        "total": int(sum(by_action.values())),
        "by_action": {k: int(v) for k, v in by_action.items()},
        "recent": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat(),
                "symbol": s.symbol,
                "exchange": s.exchange,
                "timeframe": s.timeframe,
                "action": s.action,
                "confluence": s.confluence,
                "entry": s.entry,
                "stop": s.stop,
                "target": s.target,
                "leverage": s.leverage,
                "ml_confidence": s.ml_confidence,
            }
            for s in logs
        ],
    }
