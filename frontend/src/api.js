// Thin API client for the screener backend (JWT-authenticated).
const BASE = import.meta.env.VITE_API_BASE || "";
const TOKEN_KEY = "screener_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    setToken("");
    window.dispatchEvent(new Event("auth:logout"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

const jsonPost = (path, body, method = "POST") =>
  req(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const api = {
  // --- auth ---
  login: (email, password) => jsonPost("/api/auth/login", { email, password }),
  register: (body) => jsonPost("/api/auth/register", body),
  me: () => req("/api/auth/me"),

  // --- market / ml ---
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
  train: (body) => jsonPost("/api/ml/train", body),
  predict: (body) => jsonPost("/api/ml/predict", body),
  trainAll: (body) => jsonPost("/api/ml/train-all", body),
  signal: (body) => jsonPost("/api/ml/signal", body),
  status: (symbol, exchange, timeframe) =>
    req(
      `/api/ml/status?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}&timeframe=${timeframe}`
    ),

  // --- cabinet metrics ---
  metricsOverview: () => req("/api/metrics/overview"),
  metricsHistory: (symbol, limit = 50) =>
    req(`/api/metrics/history?symbol=${encodeURIComponent(symbol)}&limit=${limit}`),
  metricsSignals: (limit = 100) => req(`/api/metrics/signals?limit=${limit}`),

  // --- admin ---
  adminUsers: () => req("/api/admin/users"),
  adminCreateUser: (body) => jsonPost("/api/admin/users", body),
  adminUpdateUser: (id, body) => jsonPost(`/api/admin/users/${id}`, body, "PATCH"),
  adminDeleteUser: (id) => req(`/api/admin/users/${id}`, { method: "DELETE" }),

  // --- chat ---
  chatContacts: () => req("/api/chat/contacts"),
  chatHistory: (otherId) => req(`/api/chat/messages/${otherId}`),
  chatSend: (recipientId, body) =>
    jsonPost("/api/chat/messages", { recipient_id: recipientId, body }),
};

export function chatSocket() {
  const token = getToken();
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = BASE ? BASE.replace(/^https?:\/\//, "") : window.location.host;
  return new WebSocket(`${proto}://${host}/api/chat/ws?token=${encodeURIComponent(token)}`);
}
