"""Multi-exchange data access layer built on CCXT (public endpoints only)."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import ccxt.async_support as ccxt

from .config import settings


def _maintenance_margin_rate(market: dict[str, Any]) -> float | None:
    """Best-effort maintenance-margin rate from CCXT market metadata.

    CCXT does not expose a unified field, so we probe the common locations
    (unified key, then a few raw `info` keys used by major venues). Returns a
    fraction (e.g. 0.005 = 0.5%) or None when the venue doesn't advertise it.
    """
    candidates = [
        market.get("maintenanceMarginRate"),
        (market.get("info") or {}).get("maintenanceMarginRate"),
        (market.get("info") or {}).get("mmr"),
        (market.get("info") or {}).get("maintMarginPercent"),
    ]
    for c in candidates:
        try:
            if c is None:
                continue
            v = float(c)
            # Some venues report percent (0.5) rather than a fraction (0.005).
            if v > 1:
                v /= 100.0
            if 0 < v < 1:
                return v
        except (TypeError, ValueError):
            continue
    return None


class _TTLCache:
    """Tiny async-safe TTL cache keyed by arbitrary hashable keys."""

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._store: dict[Any, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: Any) -> Any | None:
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            ts, value = item
            if time.monotonic() - ts > self._ttl:
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: Any, value: Any) -> None:
        async with self._lock:
            self._store[key] = (time.monotonic(), value)


class ExchangeManager:
    """Lazily instantiates ccxt exchange clients and exposes cached public data."""

    def __init__(self) -> None:
        self._clients: dict[str, ccxt.Exchange] = {}
        self._markets_loaded: set[str] = set()
        self._ob_cache = _TTLCache(settings.cache_ttl_seconds)
        self._ohlcv_cache = _TTLCache(max(settings.cache_ttl_seconds, 30.0))
        self._ticker_cache = _TTLCache(settings.cache_ttl_seconds)
        # Leverage / contract metadata changes rarely — cache it for an hour.
        self._leverage_cache = _TTLCache(3600.0)
        self._init_lock = asyncio.Lock()

    async def _client(self, exchange_id: str) -> ccxt.Exchange:
        if exchange_id not in self._clients:
            async with self._init_lock:
                if exchange_id not in self._clients:
                    if not hasattr(ccxt, exchange_id):
                        raise ValueError(f"Unknown exchange id: {exchange_id}")
                    klass = getattr(ccxt, exchange_id)
                    self._clients[exchange_id] = klass({"enableRateLimit": True})
        return self._clients[exchange_id]

    async def _ensure_markets(self, client: ccxt.Exchange) -> None:
        if client.id not in self._markets_loaded:
            await client.load_markets()
            self._markets_loaded.add(client.id)

    def supports(self, exchange_id: str, capability: str) -> bool:
        if not hasattr(ccxt, exchange_id):
            return False
        try:
            client = self._clients.get(exchange_id)
            if client is None:
                klass = getattr(ccxt, exchange_id)
                client = klass()
            return bool(client.has.get(capability, False))
        except Exception:
            return False

    async def fetch_order_book(
        self, symbol: str, exchange_id: str, limit: int | None = None
    ) -> dict[str, Any]:
        limit = limit or settings.orderbook_limit
        key = ("ob", exchange_id, symbol, limit)
        cached = await self._ob_cache.get(key)
        if cached is not None:
            return cached
        client = await self._client(exchange_id)
        await self._ensure_markets(client)
        ob = await client.fetch_order_book(symbol, limit=limit)
        await self._ob_cache.set(key, ob)
        return ob

    async def fetch_ohlcv(
        self,
        symbol: str,
        exchange_id: str,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        timeframe = timeframe or settings.timeframe
        limit = limit or settings.history_candles
        key = ("ohlcv", exchange_id, symbol, timeframe, limit)
        cached = await self._ohlcv_cache.get(key)
        if cached is not None:
            return cached
        client = await self._client(exchange_id)
        await self._ensure_markets(client)
        candles = await self._paginated_ohlcv(client, symbol, timeframe, limit)
        await self._ohlcv_cache.set(key, candles)
        return candles

    async def _paginated_ohlcv(
        self, client: ccxt.Exchange, symbol: str, timeframe: str, limit: int
    ) -> list[list[float]]:
        """Fetch up to `limit` candles, paginating forward from `now - limit*tf`.

        Exchanges cap the page size well below what we ask for (e.g. OKX returns at
        most 300 rows), so we must keep advancing `since` until we either collect
        enough candles or reach the present — we cannot infer completion from a
        short batch.
        """
        per_call = min(limit, 1000)
        tf_ms = client.parse_timeframe(timeframe) * 1000
        now = client.milliseconds()
        since = now - limit * tf_ms
        all_candles: list[list[float]] = []
        guard = 0
        max_iters = limit // 50 + 10
        while len(all_candles) < limit and guard < max_iters:
            guard += 1
            batch = await client.fetch_ohlcv(symbol, timeframe, since=since, limit=per_call)
            if not batch:
                break
            all_candles.extend(batch)
            next_since = batch[-1][0] + tf_ms
            if next_since <= since:  # no forward progress
                break
            since = next_since
            if since >= now:  # reached the present
                break
        # Deduplicate by timestamp and sort ascending.
        dedup: dict[int, list[float]] = {int(c[0]): c for c in all_candles}
        return [dedup[k] for k in sorted(dedup)][-limit:]

    async def fetch_ticker(self, symbol: str, exchange_id: str) -> dict[str, Any]:
        key = ("ticker", exchange_id, symbol)
        cached = await self._ticker_cache.get(key)
        if cached is not None:
            return cached
        client = await self._client(exchange_id)
        await self._ensure_markets(client)
        ticker = await client.fetch_ticker(symbol)
        await self._ticker_cache.set(key, ticker)
        return ticker

    @staticmethod
    def _find_linear_swap(client: ccxt.Exchange, base: str, quote: str = "USDT") -> str | None:
        """Locate the linear perpetual-swap market for base/quote on a client."""
        # Prefer the canonical unified symbol when present.
        canonical = f"{base}/{quote}:{quote}"
        if canonical in client.markets:
            return canonical
        for sym, m in client.markets.items():
            if (
                m.get("base") == base
                and m.get("quote") == quote
                and m.get("swap")
                and m.get("linear")
                and m.get("active", True)
            ):
                return sym
        return None

    async def _exchange_leverage(self, exchange_id: str, base: str) -> dict[str, Any]:
        """Max leverage for `base`'s linear perpetual swap on one exchange (real data)."""
        client = await self._client(exchange_id)
        await self._ensure_markets(client)
        sym = self._find_linear_swap(client, base)
        if sym is None:
            return {"exchange": exchange_id, "available": False, "max_leverage": None}
        market = client.markets[sym]
        lev = ((market.get("limits") or {}).get("leverage") or {}).get("max")
        max_lev = float(lev) if lev else None
        return {
            "exchange": exchange_id,
            "available": max_lev is not None,
            "symbol": sym,
            "max_leverage": max_lev,
            "contract_size": market.get("contractSize"),
            "maintenance_margin_rate": _maintenance_margin_rate(market),
        }

    async def fetch_leverage_info(
        self, symbol: str, exchange_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """Aggregate real per-exchange max leverage for a coin's perpetual swaps.

        Returns the per-exchange breakdown plus a `max_leverage` (highest offered
        anywhere) and a `typical_leverage` (median of available venues), all taken
        from live CCXT market metadata — no API keys required.
        """
        exchange_ids = exchange_ids or settings.exchanges
        base = symbol.split("/")[0]
        key = ("lev", base, tuple(exchange_ids))
        cached = await self._leverage_cache.get(key)
        if cached is not None:
            return cached

        async def _safe(ex_id: str) -> dict[str, Any]:
            try:
                return await self._exchange_leverage(ex_id, base)
            except Exception as exc:  # noqa: BLE001
                return {"exchange": ex_id, "available": False, "error": str(exc)[:120]}

        per_exchange = await asyncio.gather(*(_safe(e) for e in exchange_ids))
        offered = [
            e["max_leverage"] for e in per_exchange if e.get("available") and e.get("max_leverage")
        ]
        max_lev = max(offered) if offered else None
        typical = None
        if offered:
            s = sorted(offered)
            mid = len(s) // 2
            typical = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
        # Maintenance margin from the venue offering the highest leverage (the one
        # a trader would most likely use), else any reported rate.
        mmr = None
        for e in per_exchange:
            if e.get("max_leverage") == max_lev and e.get("maintenance_margin_rate"):
                mmr = e["maintenance_margin_rate"]
                break
        if mmr is None:
            rates = [e.get("maintenance_margin_rate") for e in per_exchange]
            rates = [r for r in rates if r]
            mmr = min(rates) if rates else None
        info = {
            "base": base,
            "per_exchange": per_exchange,
            "venues_with_leverage": len(offered),
            "max_leverage": max_lev,
            "typical_leverage": typical,
            "maintenance_margin_rate": mmr,
        }
        await self._leverage_cache.set(key, info)
        return info

    async def has_symbol(self, symbol: str, exchange_id: str) -> bool:
        try:
            client = await self._client(exchange_id)
            await self._ensure_markets(client)
            return symbol in client.markets
        except Exception:
            return False

    async def close(self) -> None:
        await asyncio.gather(
            *(c.close() for c in self._clients.values()), return_exceptions=True
        )


manager = ExchangeManager()
