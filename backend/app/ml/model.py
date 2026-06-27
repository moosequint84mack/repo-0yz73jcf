"""Trainable pattern / movement classifier with on-disk persistence.

The model learns to classify the *next move* (down / flat / up) from engineered
features of the last ~month of candles. It can be retrained on demand, which is
the basis of the "self-learning" behaviour exposed in the UI.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from ..backtest import run_backtest
from ..config import settings
from ..features import build_dataset, candles_to_df, compute_features

CLASS_NAMES = {0: "down", 1: "flat", 2: "up"}


@dataclass
class TrainResult:
    accuracy: float
    macro_f1: float
    weighted_f1: float
    classes: list[int]
    report: dict[str, Any]
    confusion: list[list[int]]
    feature_importances: dict[str, float]
    learning_curve: list[dict[str, float]]
    n_train: int
    n_test: int
    horizon: int
    threshold: float
    trained_at: float = field(default_factory=time.time)
    label_distribution: dict[str, int] = field(default_factory=dict)
    backtest: dict[str, Any] = field(default_factory=dict)
    walk_forward: dict[str, Any] = field(default_factory=dict)
    calibrated: bool = False
    label_mode: str = "triple_barrier"


@dataclass
class TrainedModel:
    clf: LGBMClassifier
    feature_columns: list[str]
    result: TrainResult
    key: str
    # Calibrated probability estimator (CalibratedClassifierCV) used for
    # predict_proba; falls back to the raw clf when calibration is unavailable.
    predictor: Any = None


class ModelStore:
    """In-memory + on-disk registry of trained models keyed by exchange/symbol/timeframe."""

    def __init__(self) -> None:
        self._models: dict[str, TrainedModel] = {}
        self._lock = threading.Lock()
        os.makedirs(settings.model_dir, exist_ok=True)

    @staticmethod
    def make_key(exchange: str, symbol: str, timeframe: str) -> str:
        return f"{exchange}__{symbol.replace('/', '-')}__{timeframe}"

    def _path(self, key: str) -> str:
        return os.path.join(settings.model_dir, f"{key}.joblib")

    def get(self, key: str) -> TrainedModel | None:
        with self._lock:
            if key in self._models:
                return self._models[key]
        path = self._path(key)
        if os.path.exists(path):
            model = joblib.load(path)
            with self._lock:
                self._models[key] = model
            return model
        return None

    def _persist(self, model: TrainedModel) -> None:
        joblib.dump(model, self._path(model.key))

    def train(
        self,
        candles: list[list[float]],
        key: str,
        horizon: int = 12,
        threshold: float = 0.004,
        label_mode: str = "triple_barrier",
    ) -> TrainedModel:
        feats, labels, df = build_dataset(
            candles, horizon=horizon, threshold=threshold, label_mode=label_mode
        )
        if len(feats) < 200:
            raise ValueError(
                f"Not enough usable candles to train ({len(feats)} rows after cleaning). "
                "Increase history or lower the timeframe."
            )

        feature_columns = list(feats.columns)
        X = feats.to_numpy()
        y = labels.to_numpy()

        # Time-ordered split — never shuffle financial time series.
        # train (fit) -> calib (early-stopping + probability calibration) -> test.
        fit_end = int(len(X) * 0.70)
        calib_end = int(len(X) * 0.85)
        X_train, X_calib, X_test = X[:fit_end], X[fit_end:calib_end], X[calib_end:]
        y_train, y_calib, y_test = y[:fit_end], y[fit_end:calib_end], y[calib_end:]

        classes = sorted(np.unique(y).tolist())
        # Balance classes (flat usually dominates).
        counts = {int(c): int((y_train == c).sum()) for c in classes}
        total = sum(counts.values())
        class_weight = {c: total / (len(counts) * n) for c, n in counts.items() if n > 0}

        clf = LGBMClassifier(
            n_estimators=900,
            learning_rate=0.03,
            num_leaves=48,
            max_depth=-1,
            min_child_samples=60,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.7,
            reg_alpha=0.2,
            reg_lambda=1.5,
            min_split_gain=0.0,
            class_weight=class_weight,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        eval_result: dict[str, Any] = {}
        # Early stopping uses the calibration slice, NOT the test set (no leakage).
        clf.fit(
            X_train,
            y_train,
            eval_set=[(X_calib, y_calib)],
            eval_metric="multi_logloss",
            callbacks=[
                early_stopping(stopping_rounds=60, verbose=False),
                log_evaluation(period=0),
                _record_eval(eval_result),
            ],
        )

        # Probability calibration (isotonic, falling back to sigmoid) on the held-out
        # calibration slice so confidence thresholds are meaningful.
        predictor: Any = clf
        calibrated = False
        for method in ("isotonic", "sigmoid"):
            try:
                cal = CalibratedClassifierCV(clf, method=method, cv="prefit")
                cal.fit(X_calib, y_calib)
                predictor = cal
                calibrated = True
                break
            except Exception:
                continue

        y_pred = predictor.predict(X_test)
        acc = float(accuracy_score(y_test, y_pred))

        # Walk-forward (expanding-window) out-of-sample validation across folds.
        walk_forward = _walk_forward(X, y, classes, class_weight)

        # Out-of-sample trade backtest: replay test-set predictions as bracket trades.
        test_positions = feats.index.to_numpy()[calib_end:]
        proba_test = predictor.predict_proba(X_test)
        backtest = run_backtest(
            df,
            test_positions,
            proba_test,
            classes,
            horizon=horizon,
            threshold=threshold,
        )
        report = classification_report(
            y_test,
            y_pred,
            labels=classes,
            target_names=[CLASS_NAMES[c] for c in classes],
            output_dict=True,
            zero_division=0,
        )
        conf = confusion_matrix(y_test, y_pred, labels=classes).tolist()
        importances = dict(
            sorted(
                zip(feature_columns, clf.feature_importances_.astype(float), strict=True),
                key=lambda kv: kv[1],
                reverse=True,
            )
        )
        # `clf` keeps full-tree count; record how many trees survived early stopping.
        _ = getattr(clf, "best_iteration_", None)
        curve = [
            {"iteration": i, "val_logloss": float(v)}
            for i, v in enumerate(eval_result.get("multi_logloss", []))
        ]
        label_dist = {CLASS_NAMES[int(c)]: int((y == c).sum()) for c in classes}

        macro_f1 = float(report.get("macro avg", {}).get("f1-score", 0.0))
        weighted_f1 = float(report.get("weighted avg", {}).get("f1-score", 0.0))

        result = TrainResult(
            accuracy=acc,
            macro_f1=macro_f1,
            weighted_f1=weighted_f1,
            classes=classes,
            report=report,
            confusion=conf,
            feature_importances=importances,
            learning_curve=curve,
            n_train=len(X_train),
            n_test=len(X_test),
            horizon=horizon,
            threshold=threshold,
            label_distribution=label_dist,
            backtest=backtest,
            walk_forward=walk_forward,
            calibrated=calibrated,
            label_mode=label_mode,
        )
        model = TrainedModel(
            clf=clf,
            feature_columns=feature_columns,
            result=result,
            key=key,
            predictor=predictor,
        )
        with self._lock:
            self._models[key] = model
        self._persist(model)
        return model

    def predict_latest(self, model: TrainedModel, candles: list[list[float]]) -> dict[str, Any]:
        df = candles_to_df(candles)
        feats = compute_features(df)
        latest = feats[model.feature_columns].dropna()
        if latest.empty:
            raise ValueError("Could not build features from the supplied candles.")
        row = latest.iloc[[-1]].to_numpy()
        predictor = getattr(model, "predictor", None) or model.clf
        proba = predictor.predict_proba(row)[0]
        classes = list(predictor.classes_)
        probs = {CLASS_NAMES[int(c)]: float(p) for c, p in zip(classes, proba, strict=True)}
        pred_class = int(classes[int(np.argmax(proba))])
        return {
            "prediction": CLASS_NAMES[pred_class],
            "prediction_code": pred_class,
            "confidence": float(np.max(proba)),
            "probabilities": probs,
            "as_of": df["dt"].iloc[-1].isoformat(),
            "last_close": float(df["close"].iloc[-1]),
            "horizon": model.result.horizon,
            "threshold": model.result.threshold,
        }


def _walk_forward(
    X: np.ndarray,
    y: np.ndarray,
    classes: list[int],
    class_weight: dict[int, float],
    n_splits: int = 4,
) -> dict[str, Any]:
    """Expanding-window walk-forward validation.

    Splits the series into ``n_splits + 1`` contiguous blocks; fold *k* trains on
    blocks ``0..k`` and tests on block ``k+1`` (always forward in time), so every
    score is genuinely out-of-sample. A lighter LightGBM is used for speed. The
    mean accuracy / macro-F1 across folds is a far more honest estimate of live
    performance than a single train/test split.
    """
    n = len(X)
    block = n // (n_splits + 1)
    if block < 80:
        return {"folds": [], "note": "series too short for walk-forward"}

    folds: list[dict[str, float]] = []
    for k in range(1, n_splits + 1):
        tr_end = block * k
        te_end = block * (k + 1) if k < n_splits else n
        X_tr, y_tr = X[:tr_end], y[:tr_end]
        X_te, y_te = X[tr_end:te_end], y[tr_end:te_end]
        present = set(np.unique(y_tr).tolist())
        if len(X_te) < 20 or len(present) < 2:
            continue
        fold_weight = {c: w for c, w in class_weight.items() if c in present}
        clf = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=32,
            min_child_samples=60,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.7,
            reg_alpha=0.2,
            reg_lambda=1.5,
            class_weight=fold_weight,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        clf.fit(X_tr, y_tr)
        pred = clf.predict(X_te)
        folds.append(
            {
                "fold": k,
                "n_train": int(len(X_tr)),
                "n_test": int(len(X_te)),
                "accuracy": float(accuracy_score(y_te, pred)),
                "macro_f1": float(
                    f1_score(y_te, pred, labels=classes, average="macro", zero_division=0)
                ),
            }
        )

    if not folds:
        return {"folds": []}
    return {
        "folds": folds,
        "mean_accuracy": float(np.mean([f["accuracy"] for f in folds])),
        "std_accuracy": float(np.std([f["accuracy"] for f in folds])),
        "mean_macro_f1": float(np.mean([f["macro_f1"] for f in folds])),
    }


def _record_eval(store: dict[str, Any]):
    """LightGBM callback that captures the validation-metric curve for the UI."""

    def _cb(env: Any) -> None:
        for _, metric, value, _ in env.evaluation_result_list:
            store.setdefault(metric, []).append(value)

    _cb.order = 10  # type: ignore[attr-defined]
    return _cb


store = ModelStore()
