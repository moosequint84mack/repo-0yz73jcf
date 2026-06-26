import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useT } from "../i18n.jsx";
import PriceChart from "../components/PriceChart.jsx";
import DensityPanel from "../components/DensityPanel.jsx";
import ComparePanel from "../components/ComparePanel.jsx";
import MLPanel from "../components/MLPanel.jsx";
import SignalPanel from "../components/SignalPanel.jsx";
import ScreenerPanel from "../components/ScreenerPanel.jsx";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"];
// Fallback list used until /api/config returns the authoritative set of pairs.
export const SYMBOLS = [
  "BTC/USDT",
  "ETH/USDT",
  "SOL/USDT",
  "XRP/USDT",
  "BNB/USDT",
  "DOGE/USDT",
  "ADA/USDT",
  "AVAX/USDT",
  "LINK/USDT",
  "DOT/USDT",
  "LTC/USDT",
  "TRX/USDT",
  "BCH/USDT",
  "ATOM/USDT",
  "UNI/USDT",
  "ETC/USDT",
  "NEAR/USDT",
  "FIL/USDT",
  "APT/USDT",
  "ARB/USDT",
  "OP/USDT",
  "INJ/USDT",
  "SUI/USDT",
  "AAVE/USDT",
];

const WATCHLIST_KEY = "screener_watchlist";
const MAX_WATCH = 10;

export default function Dashboard() {
  const { t } = useT();
  const [cfg, setCfg] = useState(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [exchange, setExchange] = useState("okx");
  const [timeframe, setTimeframe] = useState("1h");

  const [candles, setCandles] = useState([]);
  const [ob, setOb] = useState(null);
  const [compare, setCompare] = useState(null);
  const [status, setStatus] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [signal, setSignal] = useState(null);
  const [signalLoading, setSignalLoading] = useState(false);

  const [trainAll, setTrainAll] = useState({});
  const [trainingAll, setTrainingAll] = useState(false);

  const [training, setTraining] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [error, setError] = useState(null);
  const [live, setLive] = useState(true);

  // Pairs available to view come from the backend config (fallback: SYMBOLS).
  const allSymbols = cfg?.symbols?.length ? cfg.symbols : SYMBOLS;

  // User watchlist: 1–10 pairs the screener focuses on, persisted locally.
  const [watchlist, setWatchlist] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
      return Array.isArray(saved) ? saved.slice(0, MAX_WATCH) : [];
    } catch (_) {
      return [];
    }
  });
  const [watchOpen, setWatchOpen] = useState(false);

  const toggleWatch = (sym) => {
    setWatchlist((prev) => {
      let next;
      if (prev.includes(sym)) next = prev.filter((s) => s !== sym);
      else if (prev.length >= MAX_WATCH) next = prev;
      else next = [...prev, sym];
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
      return next;
    });
  };
  const clearWatch = () => {
    setWatchlist([]);
    localStorage.setItem(WATCHLIST_KEY, "[]");
  };

  // The screener table shows the watchlist if set, otherwise every pair.
  const screenerSymbols = watchlist.length ? watchlist : allSymbols;

  const liveRef = useRef(live);
  liveRef.current = live;

  useEffect(() => {
    api
      .config()
      .then((c) => {
        setCfg(c);
        setExchange(c.default_exchange || c.exchanges[0]);
      })
      .catch((e) => setError(e.message));
  }, []);

  // Hydrate the multi-screener from persisted training runs so it shows last
  // metrics on load (instead of "not trained") without re-running training.
  useEffect(() => {
    api
      .metricsOverview()
      .then((o) => {
        const bySymbol = {};
        for (const p of o.per_pair || []) {
          bySymbol[p.symbol] = {
            symbol: p.symbol,
            ok: true,
            accuracy: p.accuracy,
            win_rate: p.win_rate,
            n_trades: p.trades,
            profit_factor: p.profit_factor,
            expectancy_pct: p.expectancy,
          };
        }
        setTrainAll((prev) => ({ ...bySymbol, ...prev }));
      })
      .catch(() => {});
  }, []);

  const loadCandles = useCallback(async () => {
    try {
      const d = await api.candles(symbol, exchange, timeframe, 600);
      setCandles(d.candles);
    } catch (e) {
      setError(`candles: ${e.message}`);
    }
  }, [symbol, exchange, timeframe]);

  const loadOb = useCallback(async () => {
    try {
      const d = await api.orderbook(symbol, exchange, 100);
      setOb(d);
    } catch (e) {
      setError(`orderbook: ${e.message}`);
    }
  }, [symbol, exchange]);

  const loadCompare = useCallback(async () => {
    try {
      const ex = cfg?.exchanges;
      const d = await api.compare(symbol, ex);
      setCompare(d);
    } catch (e) {
      setError(`compare: ${e.message}`);
    }
  }, [symbol, cfg]);

  const loadStatus = useCallback(async () => {
    try {
      const d = await api.status(symbol, exchange, timeframe);
      setStatus(d.trained ? d : null);
    } catch (_) {
      setStatus(null);
    }
  }, [symbol, exchange, timeframe]);

  const loadSignal = useCallback(async () => {
    try {
      setSignalLoading(true);
      const d = await api.signal({ symbol, exchange, timeframe });
      setSignal(d);
    } catch (e) {
      setError(`signal: ${e.message}`);
    } finally {
      setSignalLoading(false);
    }
  }, [symbol, exchange, timeframe]);

  useEffect(() => {
    setError(null);
    setPrediction(null);
    setSignal(null);
    loadCandles();
    loadOb();
    loadStatus();
    loadSignal();
  }, [loadCandles, loadOb, loadStatus, loadSignal]);

  useEffect(() => {
    if (cfg) loadCompare();
  }, [cfg, loadCompare]);

  useEffect(() => {
    const id = setInterval(() => {
      if (!liveRef.current) return;
      loadOb();
      loadCompare();
      loadSignal();
    }, 4000);
    return () => clearInterval(id);
  }, [loadOb, loadCompare, loadSignal]);

  const onTrain = async ({ horizon, threshold }) => {
    setTraining(true);
    setError(null);
    try {
      const d = await api.train({
        symbol,
        exchange,
        timeframe,
        history: cfg?.history_candles || 4000,
        horizon,
        threshold,
      });
      setStatus({ trained: true, result: d.result, key: d.key });
      await onPredict();
    } catch (e) {
      setError(`train: ${e.message}`);
    } finally {
      setTraining(false);
    }
  };

  const onPredict = async () => {
    setPredicting(true);
    try {
      const d = await api.predict({ symbol, exchange, timeframe });
      setPrediction(d);
      loadSignal();
    } catch (e) {
      setError(`predict: ${e.message}`);
    } finally {
      setPredicting(false);
    }
  };

  const onTrainAll = async () => {
    setTrainingAll(true);
    setError(null);
    try {
      const d = await api.trainAll({
        symbols: screenerSymbols,
        exchange,
        timeframe,
        history: cfg?.history_candles || 4000,
      });
      const bySymbol = {};
      for (const r of d.results) bySymbol[r.symbol] = r;
      setTrainAll(bySymbol);
      loadStatus();
      loadSignal();
    } catch (e) {
      setError(`train-all: ${e.message}`);
    } finally {
      setTrainingAll(false);
    }
  };

  return (
    <>
      <div className="subbar">
        <div className="field">
          <label>{t("field.symbol")}</label>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            {allSymbols.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>{t("field.exchange")}</label>
          <select value={exchange} onChange={(e) => setExchange(e.target.value)}>
            {(cfg?.exchanges || ["okx"]).map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>{t("field.timeframe")}</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
            {TIMEFRAMES.map((tf) => (
              <option key={tf}>{tf}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>&nbsp;</label>
          <button
            className="ghost"
            onClick={() => setLive((v) => !v)}
            style={{ color: live ? "var(--green)" : "var(--muted)" }}
          >
            {live ? t("live.on") : t("live.off")}
          </button>
        </div>
        <div className="field" style={{ position: "relative" }}>
          <label>&nbsp;</label>
          <button className="ghost" onClick={() => setWatchOpen((v) => !v)}>
            {t("watch.button", { n: watchlist.length })}
          </button>
          {watchOpen && (
            <div className="watch-pop">
              <div className="watch-pop-head">
                <span>{t("watch.title", { max: MAX_WATCH })}</span>
                <button className="linkish" onClick={clearWatch}>
                  {t("watch.all")}
                </button>
              </div>
              <div className="watch-list">
                {allSymbols.map((s) => {
                  const on = watchlist.includes(s);
                  const disabled = !on && watchlist.length >= MAX_WATCH;
                  return (
                    <label
                      key={s}
                      className={"watch-item" + (disabled ? " disabled" : "")}
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={disabled}
                        onChange={() => toggleWatch(s)}
                      />
                      {s}
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {error && <div className="error">⚠ {error}</div>}

      <div className="panel">
        <h3>
          <span>{t("screener.title")}</span>
          <span className="muted">{t("screener.subtitle")}</span>
        </h3>
        <ScreenerPanel
          symbols={screenerSymbols}
          results={trainAll}
          running={trainingAll}
          onTrainAll={onTrainAll}
          onSelect={setSymbol}
          current={symbol}
        />
      </div>

      <div className="grid">
        <div className="col">
          <div className="panel">
            <h3>
              <span>
                {symbol} · {exchange} · {timeframe}
              </span>
              <span className="muted">{t("chart.candles", { n: candles.length })}</span>
            </h3>
            <PriceChart
              candles={candles}
              walls={ob ? [...(ob.bid_walls || []), ...(ob.ask_walls || [])] : []}
              support={ob?.support}
              resistance={ob?.resistance}
            />
          </div>

          <div className="panel">
            <h3>{t("ml.title")}</h3>
            <MLPanel
              status={status}
              prediction={prediction}
              training={training}
              predicting={predicting}
              onTrain={onTrain}
              onPredict={onPredict}
            />
          </div>
        </div>

        <div className="col">
          <div className="panel">
            <h3>
              <span>{t("signal.title")}</span>
              <span className="muted">{t("signal.subtitle")}</span>
            </h3>
            <SignalPanel data={signal} loading={signalLoading} />
          </div>

          <div className="panel">
            <h3>
              <span>{t("density.title")}</span>
              <span className="muted">{t("density.subtitle")}</span>
            </h3>
            <DensityPanel ob={ob} />
          </div>

          <div className="panel">
            <h3>
              <span>{t("compare.title")}</span>
            </h3>
            <ComparePanel data={compare} />
          </div>
        </div>
      </div>

      <div className="footer">{t("footer", { h: status?.result?.horizon ?? 12 })}</div>
    </>
  );
}
