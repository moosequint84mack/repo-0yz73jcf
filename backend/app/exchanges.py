"""Multi-exchange data access layer built on CCXT (public endpoints only)."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import ccxt.async_support as ccxt

from .config import settings


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
