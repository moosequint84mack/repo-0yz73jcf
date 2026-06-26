# Crypto Market Screener

A crypto market screener that detects **order-book density (liquidity walls)**,
**compares prices across exchanges**, and **learns to predict the next price move**
from ~1 month of candle history using a self-training ML classifier — all behind a
modern web dashboard.

Data is pulled from public exchange APIs via [CCXT](https://github.com/ccxt/ccxt)
(no API keys required).

## Features

- **Order-book density / liquidity walls** — detects levels whose notional size is a
  statistical outlier (z-score) and renders a bid/ask density heatmap.
- **Cross-exchange comparison** — fetches the same symbol on 5+ exchanges
  (OKX, Kraken, KuCoin, Coinbase, MEXC) and quantifies divergence + a naive arbitrage hint.
- **Self-learning ML** — a LightGBM classifier learns patterns from engineered candle
  features (returns, volatility, RSI, MACD, Bollinger position, candle anatomy, volume) and
  predicts the next *N*-candle move (down / flat / up). Retrain on demand from the UI.
- **Modern dashboard** — TradingView-style candlestick chart with wall overlays, live
  heatmap, cross-exchange table, prediction signal, confusion matrix, learning curve and
  feature importances.

## Architecture

```
backend/   FastAPI + CCXT + LightGBM
  app/
    exchanges.py    multi-exchange data layer (TTL cache, paginated OHLCV)
    density.py      liquidity-wall detection + heatmap
    comparison.py   cross-exchange price divergence
    features.py     technical-indicator feature engineering
    ml/model.py     LightGBM training / prediction / persistence
    routers/        /api/candles, /api/orderbook, /api/compare, /api/ml/*
frontend/  React + Vite + lightweight-charts
```

## Running locally

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api -> :8000)
```

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/config` | defaults (exchanges, symbol, timeframe) |
| GET | `/api/candles` | OHLCV candles |
| GET | `/api/orderbook` | order-book density analysis (walls + heatmap) |
| GET | `/api/compare` | cross-exchange price comparison |
| POST | `/api/ml/train` | train/retrain a model for a symbol/exchange/timeframe |
| POST | `/api/ml/predict` | predict the next move |
| GET | `/api/ml/status` | model status + metrics |

> Not financial advice. Predictive accuracy on noisy crypto microstructure is modest by
> nature; treat signals as one input among many.
