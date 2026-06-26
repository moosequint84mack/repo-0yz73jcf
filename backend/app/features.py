"""Feature engineering from OHLCV candles for the pattern/movement classifier."""
from __future__ import annotations

import numpy as np
import pandas as pd


def candles_to_df(candles: list[list[float]]) -> pd.DataFrame:
    """Convert ccxt OHLCV rows [ts, o, h, l, c, v] to a typed DataFrame."""
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)
    return df


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _stoch(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """Stochastic %K (0-100) over `period`."""
    ll = low.rolling(period).min()
    hh = high.rolling(period).max()
    return 100 * (close - ll) / (hh - ll).replace(0, np.nan)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """True-range based ATR series."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean()


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer a feature matrix describing recent price/volume behaviour."""
    f = pd.DataFrame(index=df.index)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    open_ = df["open"]
    vol = df["volume"]

    # Returns over multiple lookbacks.
    for n in (1, 2, 3, 6, 12, 24, 48, 96):
        f[f"ret_{n}"] = close.pct_change(n)

    # Rolling volatility + volatility-of-volatility regime.
    ret1 = close.pct_change()
    for n in (6, 12, 24, 48, 96):
        f[f"vol_{n}"] = ret1.rolling(n).std()
    f["vol_regime"] = f["vol_12"] / f["vol_96"].replace(0, np.nan)
    # Normalised return (z-score of the last return vs recent distribution).
    f["ret_z_24"] = ret1 / ret1.rolling(24).std().replace(0, np.nan)

    # Moving-average ratios (trend) and their slopes (trend acceleration).
    for n in (7, 21, 50, 100, 200):
        ma = close.rolling(n).mean()
        f[f"ma_ratio_{n}"] = close / ma - 1
        f[f"ma_slope_{n}"] = ma.pct_change(3)
    # Fast/slow MA cross strength.
    ma_fast = close.rolling(7).mean()
    ma_slow = close.rolling(50).mean()
    f["ma_cross"] = ma_fast / ma_slow.replace(0, np.nan) - 1

    # Momentum / oscillators.
    f["rsi_7"] = _rsi(close, 7)
    f["rsi_14"] = _rsi(close, 14)
    f["rsi_28"] = _rsi(close, 28)
    f["stoch_k"] = _stoch(high, low, close, 14)
    f["stoch_d"] = f["stoch_k"].rolling(3).mean()
    f["williams_r"] = f["stoch_k"] - 100  # Williams %R is stoch shifted to [-100,0]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    f["macd"] = macd / close  # normalise by price so it is comparable across coins
    f["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / close

    # Candle anatomy (body vs wicks) — captures rejection / absorption behaviour.
    rng = (high - low).replace(0, np.nan)
    f["body_ratio"] = (close - open_) / rng
    f["upper_wick"] = (high - close.where(close > open_, open_)) / rng
    f["lower_wick"] = (close.where(close < open_, open_) - low) / rng
    f["body_mean_6"] = f["body_ratio"].rolling(6).mean()

    # Volume behaviour.
    vol_ma = vol.rolling(24).mean()
    f["vol_ratio"] = vol / vol_ma.replace(0, np.nan)
    f["vol_chg"] = vol.pct_change()
    f["vol_z_48"] = (vol - vol.rolling(48).mean()) / vol.rolling(48).std().replace(0, np.nan)
    # Signed volume pressure (up-bars vs down-bars).
    f["vol_pressure_12"] = (np.sign(ret1) * vol).rolling(12).sum() / vol.rolling(
        12
    ).sum().replace(0, np.nan)

    # Volatility (ATR) normalised by price.
    atr = _atr(high, low, close, 14)
    f["atr_pct"] = atr / close

    # Donchian channel position — where price sits in its recent range.
    for n in (24, 96):
        hh = high.rolling(n).max()
        ll = low.rolling(n).min()
        f[f"donchian_pos_{n}"] = (close - ll) / (hh - ll).replace(0, np.nan)

    # Range expansion / Bollinger-style position + bandwidth.
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    f["bb_pos"] = (close - ma20) / (2 * std20).replace(0, np.nan)
    f["bb_width"] = (4 * std20) / ma20.replace(0, np.nan)

    f = f.replace([np.inf, -np.inf], np.nan)
    return f


def make_labels(
    df: pd.DataFrame, horizon: int = 12, threshold: float = 0.004
) -> pd.Series:
    """Label each candle by the forward return over `horizon` candles.

    0 = down (< -threshold), 1 = flat, 2 = up (> +threshold).
    """
    future = df["close"].shift(-horizon)
    fwd_ret = future / df["close"] - 1
    labels = pd.Series(1, index=df.index, dtype="int64")
    labels[fwd_ret > threshold] = 2
    labels[fwd_ret < -threshold] = 0
    labels[fwd_ret.isna()] = -1  # not enough future data
    return labels


FEATURE_COLUMNS_CACHE: list[str] | None = None


def build_dataset(
    candles: list[list[float]], horizon: int = 12, threshold: float = 0.004
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Return (features, labels, full_df) aligned and cleaned for training."""
    df = candles_to_df(candles)
    feats = compute_features(df)
    labels = make_labels(df, horizon=horizon, threshold=threshold)
    mask = labels >= 0
    feats_valid = feats[mask].dropna()
    labels_valid = labels.loc[feats_valid.index]
    return feats_valid, labels_valid, df
