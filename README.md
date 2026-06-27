# Crypto Market Screener

A multi-user crypto market screener that detects **order-book density (liquidity walls)**,
**compares prices across exchanges**, **learns to predict the next price move**, and turns
that into **actionable trade signals** (entry / stop / target with real per-coin leverage) —
all behind a modern web dashboard with **user accounts, an admin panel and an internal chat**.

Data is pulled from public exchange APIs via [CCXT](https://github.com/ccxt/ccxt)
(no API keys required).

## Features

- **Order-book density / liquidity walls** — detects levels whose notional size is a
  statistical outlier (z-score) and renders a bid/ask density heatmap.
- **Cross-exchange comparison** — fetches the same symbol on 5+ exchanges
  (OKX, Kraken, KuCoin, Coinbase, MEXC) and quantifies divergence + a naive arbitrage hint.
- **Self-learning ML** — a calibrated LightGBM classifier with triple-barrier labels,
  walk-forward validation, order-book features and a market-regime filter predicts the next
  *N*-candle move (down / flat / up). Retrain on demand from the UI.
- **Trade signals** — confluence of density bounce + ML bias + order-book imbalance →
  LONG / SHORT / FLAT with entry/stop/target, R:R, real per-coin leverage (from exchange
  metadata), position sizing, ROE and liquidation distance. Out-of-sample backtest per pair.
- **Accounts & roles** — email/password login (JWT, bcrypt). New users register *inactive*
  and must be activated by a super-user. Roles: `superuser` (admin) and `user`.
- **Admin panel** — super-users list/create users, activate/deactivate, change roles and delete.
- **Personal cabinet** — per-user analytics: training-run metrics per pair (accuracy, macro F1,
  profit factor, win-rate, expectancy, trades) and a recent-signals feed.
- **Internal chat** — realtime WebSocket chat (user↔user and user↔support/admin) with REST
  history and unread counts.
- **Bilingual UI** — Russian (default) and English, toggleable in the header.

## Architecture

```
backend/   FastAPI + CCXT + LightGBM + SQLAlchemy
  app/
    exchanges.py        multi-exchange data layer (TTL cache, paginated OHLCV, leverage)
    density.py          liquidity-wall detection + heatmap
    comparison.py       cross-exchange price divergence
    features.py         technical-indicator + order-book feature engineering
    signals.py          density+ML+imbalance -> trade plan with leverage
    backtest.py         out-of-sample trade backtest (commissions, ATR stop)
    ml/model.py         LightGBM: triple-barrier labels, calibration, walk-forward
    auth.py             JWT + bcrypt password hashing
    db.py / models_db.py  SQLAlchemy engine, models, seeding, persistence
    routers/            market, ml, metrics, auth_router, admin, chat
frontend/  React + Vite + lightweight-charts
  src/views/   Login, Dashboard (screener), Cabinet, AdminPanel, Chat
```

## Deploy with Docker (recommended for a server)

Requires Docker + Docker Compose.

```bash
cp .env.example .env
# Edit .env: set a strong SCREENER_JWT_SECRET (e.g. `openssl rand -base64 48`).
# Leave SCREENER_ADMIN_PASSWORD empty to auto-generate one (printed in the logs),
# or set your own.

docker compose up -d --build
```

- Web UI: `http://SERVER_IP:8080` (change the published port with `SCREENER_HTTP_PORT`).
- The frontend container (nginx) serves the SPA and reverse-proxies `/api` (REST + the chat
  WebSocket) to the backend container — no CORS or extra config needed.
- Data persists in named volumes: `screener-data` (SQLite DB) and `screener-models`
  (trained models).

**First login.** The super-user is seeded on the first start. If you left
`SCREENER_ADMIN_PASSWORD` empty, grab the generated password from the logs:

```bash
docker compose logs backend | grep -i "generated password"
```

Log in as the super-user, open the **Admin** tab, and activate/create the user accounts you
need. Each new self-registered account stays inactive until you activate it.

**Postgres (optional).** SQLite needs no extra service. To use Postgres, add a `db` service
to `docker-compose.yml` and set `SCREENER_DATABASE_URL=postgresql+psycopg://user:pass@db:5432/screener`.

## Running locally (development)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export SCREENER_JWT_SECRET="dev-secret"
export SCREENER_ADMIN_PASSWORD="change-me"   # else a random one is logged
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api -> :8000)
```

## Configuration

All settings are overridable via `SCREENER_`-prefixed environment variables (see
`backend/app/config.py`). Key ones:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `SCREENER_JWT_SECRET` | *(random per process)* | **Set in production**; signs JWT tokens. |
| `SCREENER_ADMIN_EMAIL` | `admin@screener.io` | First super-user, seeded on a fresh DB. |
| `SCREENER_ADMIN_PASSWORD` | *(generated + logged)* | Super-user password. |
| `SCREENER_DATABASE_URL` | `sqlite:///./screener.db` | SQLAlchemy URL (SQLite/Postgres). |
| `SCREENER_ALLOW_SELF_REGISTRATION` | `true` | Allow self sign-up (created inactive). |

## API

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| POST | `/api/auth/register` | – | Self-register (inactive until activated) |
| POST | `/api/auth/login` | – | Obtain JWT access token |
| GET | `/api/auth/me` | user | Current user |
| GET | `/api/candles` `/api/orderbook` `/api/compare` | – | Market data |
| POST | `/api/ml/train` `/api/ml/train-all` | user | Train model(s) |
| POST | `/api/ml/predict` `/api/ml/signal` | user | Predict / trade signal |
| GET | `/api/metrics/overview` `/api/metrics/signals` | user | Cabinet analytics |
| GET/POST/PATCH/DELETE | `/api/admin/users` | superuser | User management |
| GET/POST | `/api/chat/contacts` `/api/chat/messages` | user | Internal chat |
| WS | `/api/chat/ws?token=...` | user | Realtime chat |

> Not financial advice. Predictive accuracy on noisy crypto microstructure is modest by
> nature; treat signals as one input among many. Binance/Bybit are geo-restricted (HTTP 451)
> from some regions and are omitted from the default exchange set.
