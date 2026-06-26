import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import PriceChart from "./components/PriceChart.jsx";
import DensityPanel from "./components/DensityPanel.jsx";
import ComparePanel from "./components/ComparePanel.jsx";
import MLPanel from "./components/MLPanel.jsx";
import SignalPanel from "./components/SignalPanel.jsx";
import ScreenerPanel from "./components/ScreenerPanel.jsx";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"];
const SYMBOLS = [
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
];

export default function App() {
  const [cfg, setCfg] = useState(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [exchange, setExchange] = useState("okx");
  const [timeframe, setTimeframe] = useState("5m");

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

  // Reload everything when the instrument changes.
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

  // Live polling of order book + comparison + trade signal.
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
        history: cfg?.history_candles || 16000,
        horizon,
        threshold,
      });
      setStatus({ trained: true, result: d.result, key: d.key });
      // Immediately produce a prediction with the fresh model.
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
        symbols: SYMBOLS,
        exchange,
        timeframe,
        history: cfg?.history_candles || 16000,
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
    <div className="app">
      <div className="topbar">
        <div className="logo">
          <span className="dot" /> CRYPTO SCREENER
        </div>
        <div className="controls">
          <div className="field">
            <label>Symbol</label>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {SYMBOLS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Exchange</label>
            <select value={exchange} onChange={(e) => setExchange(e.target.value)}>
              {(cfg?.exchanges || ["okx"]).map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Timeframe</label>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {TIMEFRAMES.map((t) => (
                <option key={t}>{t}</option>
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
              {live ? "● LIVE" : "○ PAUSED"}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="error">⚠ {error}</div>}

      <div className="panel">
        <h3>
          <span>Multi-pair screener</span>
          <span className="muted">train &amp; rank all pairs</span>
        </h3>
        <ScreenerPanel
          symbols={SYMBOLS}
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
              <span className="muted">{candles.length} candles</span>
            </h3>
            <PriceChart
              candles={candles}
              walls={ob ? [...(ob.bid_walls || []), ...(ob.ask_walls || [])] : []}
              support={ob?.support}
              resistance={ob?.resistance}
            />
          </div>

          <div className="panel">
            <h3>Machine-learning signal & training</h3>
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
              <span>Trade signal</span>
              <span className="muted">entry · stop · target</span>
            </h3>
            <SignalPanel data={signal} loading={signalLoading} />
          </div>

          <div className="panel">
            <h3>
              <span>Order-book density</span>
              <span className="muted">live walls & heatmap</span>
            </h3>
            <DensityPanel ob={ob} />
          </div>

          <div className="panel">
            <h3>
              <span>Cross-exchange comparison</span>
            </h3>
            <ComparePanel data={compare} />
          </div>
        </div>
      </div>

      <div className="footer">
        Data via public CCXT endpoints. Walls = order-book levels whose notional size is a
        statistical outlier (z-score). ML predicts the next {status?.result?.horizon ?? 12}-candle
        move (down / flat / up). Not financial advice.
      </div>
    </div>
  );
}
