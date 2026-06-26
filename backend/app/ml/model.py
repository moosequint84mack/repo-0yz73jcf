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
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from ..backtest import run_backtest
from ..config import settings
from ..features import build_dataset, candles_to_df, compute_features

CLASS_NAMES = {0: "down", 1: "flat", 2: "up"}


@dataclass
class TrainResult:
    accuracy: float
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


@dataclass
class TrainedModel:
    clf: LGBMClassifier
    feature_columns: list[str]
    result: TrainResult
    key: str


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
    ) -> TrainedModel:
        feats, labels, df = build_dataset(candles, horizon=horizon, threshold=threshold)
        if len(feats) < 200:
            raise ValueError(
                f"Not enough usable candles to train ({len(feats)} rows after cleaning). "
                "Increase history or lower the timeframe."
            )

        feature_columns = list(feats.columns)
        X = feats.to_numpy()
        y = labels.to_numpy()

        # Time-ordered split — never shuffle financial time series.
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        classes = sorted(np.unique(y).tolist())
        # Balance classes (flat usually dominates).
        counts = {int(c): int((y_train == c).sum()) for c in classes}
        total = sum(counts.values())
        class_weight = {c: total / (len(counts) * n) for c, n in counts.items() if n > 0}

        clf = LGBMClassifier(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=-1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            class_weight=class_weight,
            random_state=42,
            verbose=-1,
        )
        eval_result: dict[str, Any] = {}
        clf.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            eval_metric="multi_logloss",
            callbacks=[
                early_stopping(stopping_rounds=40, verbose=False),
                log_evaluation(period=0),
                _record_eval(eval_result),
            ],
        )

        y_pred = clf.predict(X_test)
        acc = float(accuracy_score(y_test, y_pred))

        # Out-of-sample trade backtest: replay test-set predictions as bracket trades.
        test_positions = feats.index.to_numpy()[split:]
        proba_test = clf.predict_proba(X_test)
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
        curve = [
            {"iteration": i, "val_logloss": float(v)}
            for i, v in enumerate(eval_result.get("multi_logloss", []))
        ]
        label_dist = {CLASS_NAMES[int(c)]: int((y == c).sum()) for c in classes}

        result = TrainResult(
            accuracy=acc,
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
        )
        model = TrainedModel(
            clf=clf, feature_columns=feature_columns, result=result, key=key
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
        proba = model.clf.predict_proba(row)[0]
        classes = list(model.clf.classes_)
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


def _record_eval(store: dict[str, Any]):
    """LightGBM callback that captures the validation-metric curve for the UI."""

    def _cb(env: Any) -> None:
        for _, metric, value, _ in env.evaluation_result_list:
            store.setdefault(metric, []).append(value)

    _cb.order = 10  # type: ignore[attr-defined]
    return _cb


store = ModelStore()
