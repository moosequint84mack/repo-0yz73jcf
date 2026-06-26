// Thin API client for the screener backend.
const BASE = import.meta.env.VITE_API_BASE || "";

async function req(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  config: () => req("/api/config"),
  candles: (symbol, exchange, timeframe, limit = 500) =>
    req(
      `/api/candles?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}&timeframe=${timeframe}&limit=${limit}`
    ),
  orderbook: (symbol, exchange, limit = 100, zscore) =>
    req(
      `/api/orderbook?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}&limit=${limit}` +
        (zscore != null ? `&zscore=${zscore}` : "")
    ),
  compare: (symbol, exchanges) =>
    req(
      `/api/compare?symbol=${encodeURIComponent(symbol)}` +
        (exchanges ? `&exchanges=${exchanges.join(",")}` : "")
    ),
  train: (body) =>
    req("/api/ml/train", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  predict: (body) =>
    req("/api/ml/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  trainAll: (body) =>
    req("/api/ml/train-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  signal: (body) =>
    req("/api/ml/signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  status: (symbol, exchange, timeframe) =>
    req(
      `/api/ml/status?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}&timeframe=${timeframe}`
    ),
};
