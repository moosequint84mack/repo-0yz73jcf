# Crypto Screener — Trade Signals, Multi-Pair & Backtest Test Report

**Build:** branch `devin/crypto-screener-mvp` (PR #7) · backend FastAPI `:8000` · frontend Vite `:5173`
**Data:** live public CCXT endpoints (okx/kraken/kucoin/coinbase/mexc) · history window **16,000** 5m candles (~2 months)
**Scope of this iteration:** +6 pairs (→12), trade-signal engine (entry/stop/target), out-of-sample backtest, batch training, live signal polling.

---

## Summary — all golden-path tests passed

| # | Test | Result |
|---|------|--------|
| 1 | Train all 12 pairs and rank by accuracy + backtest quality | **PASS** |
| 2 | Emit a live LONG/SHORT trade plan (entry/stop/target, R:R) | **PASS** |
| 3 | Report out-of-sample backtest metrics per pair | **PASS** |
| 4 | Live order-book density heatmap + 5-exchange spread | **PASS** |

No escalations. A full annotated screen recording of the run is attached to the Devin session message.

---

## Training & backtest analytics (all 12 pairs, 16k-candle history)

Each pair = one LightGBM 3-class model (down/flat/up), time-ordered 80/20 split (~12.7k train / 3.2k test rows). Backtest = test-set predictions replayed as bracket trades (stop behind protective wall, target = 1.5× risk).

| Pair | Accuracy | Trades | Win-rate | Profit factor | Expectancy | Max DD |
|------|----------|--------|----------|---------------|------------|--------|
| **XRP/USDT** | 43.6% | 208 | **54.3%** | **1.79** | **+0.132%** | -5.2% |
| **LINK/USDT** | 41.3% | 269 | 51.7% | 1.47 | +0.084% | — |
| **TRX/USDT** | 92.6%* | 99 | 57.6% | 2.29 | +0.061% | — |
| BNB/USDT | 61.5% | 663 | 47.7% | 1.11 | +0.018% | — |
| LTC/USDT | 40.4% | 188 | 43.1% | 1.09 | +0.020% | — |
| DOT/USDT | 45.3% | 249 | 41.4% | 1.03 | +0.007% | — |
| ETH/USDT | 41.4% | 282 | 45.7% | 1.02 | +0.004% | — |
| DOGE/USDT | 51.3% | 493 | 42.6% | 1.00 | -0.000% | — |
| BTC/USDT | 44.4% | 462 | 39.6% | 0.83 | -0.035% | -25.6% |
| SOL/USDT | 33.4% | 0 | — | — | — | — |
| ADA/USDT | 36.0% | 0 | — | — | — | — |
| AVAX/USDT | 33.2% | 0 | — | — | — | — |

\* TRX's 92.6% reflects a very flat-dominated label distribution (most moves stay inside the ±0.4% band), so the classifier scores high by predicting "flat"; its **99 trades / PF 2.29** is the more meaningful quality signal.

**How accurate are the trades?** Profit factor (gross win $ / gross loss $) is the headline metric:
- **Profitable (PF > 1):** XRP (1.79), LINK (1.47), TRX (2.29), BNB (1.11), LTC (1.09), DOT (1.03), ETH (1.02) — 7 of 9 trading pairs.
- **Breakeven:** DOGE (1.00).
- **Unprofitable (PF < 1):** BTC (0.83) — high-trade-count, low-edge regime in this window.
- **0-trade pairs (SOL/ADA/AVAX):** the engine found **no** test-set bounce that aligned with ML bias, so it correctly stayed FLAT — by design, not a failure.

---

## Test 1 — Multi-pair screener (rank 12 pairs)

`Train all 12 pairs` trained one model per symbol (~210s) and populated the ranking table with accuracy, trade count, win-rate, profit factor and expectancy. Clicking a row loads that pair's chart/signal/backtest.

![Screener table — 12 pairs ranked](https://app.devin.ai/attachments/5c940c6f-c6a5-47ff-b383-1853685aec95/ss_77a76463.png)

---

## Test 2 — Live trade plan (entry / stop / target)

The signal engine fuses **bounce-off-density + ML bias + book imbalance** into a confluence score (LONG ≥ 1.5, SHORT ≤ -1.5, else FLAT). The "WHY (confluence)" block shows exactly why a plan was or wasn't issued. Below, BTC sits on a bid wall (z=4.5) but ML leans DOWN (46%) → the two disagree, so the engine correctly returns **NO TRADE** with the full rationale. (A live BTC **SHORT** plan — entry 60,181 / stop 60,275 / target 60,040, R:R 1:1.5 — was captured in the recording.)

![BTC confluence rationale](https://app.devin.ai/attachments/5beb8367-519c-4513-9edc-ab2a72f7476d/ss_dd9c9798.png)

---

## Test 3 — Out-of-sample backtest per pair

Selecting XRP (best out-of-sample pair) shows its backtest block: **208 trades, 54.3% win-rate, 1.79 profit factor, +0.132% expectancy, -5.2% max drawdown, 0.28 sharpe-like**, alongside the confusion matrix and learning curve.

![XRP backtest metrics + density heatmap](https://app.devin.ai/attachments/6409d22b-b1b7-4425-883d-661e00e9ba54/ss_27c5adc6.png)

---

## Test 4 — Live density heatmap + cross-exchange spread

The order-book panel renders bid/ask walls as a live heatmap (red asks / green bids) with mid, spread, imbalance and wall counts refreshing every ~4s. The cross-exchange table compares the same symbol across all 5 venues and flags cheapest→priciest for a naive arbitrage hint (see screenshot above; e.g. BTC `coinbase → okx`, 0.10% spread).

---

## Notes / known behaviour (not defects)

- **Binance/Bybit excluded** — returned HTTP 451 (geo-block) from this environment; the 5 working public venues are used instead.
- **0-trade pairs** are expected when density and ML never align on the test set — staying flat is the correct, conservative outcome.
- **Accuracy ~33–62% (TRX aside)** is normal for next-move classification on noisy 5m microstructure; the backtest profit-factor/expectancy are the trade-quality metrics that matter, and 7/9 trading pairs are profitable.
- Signals are analytical only — **no orders are placed. Not financial advice.**
</content>
