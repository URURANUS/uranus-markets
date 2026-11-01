"""
core.py — نواة السيرفر لايت: كاش ذكي، قفل تزامن، عميل HTTP موحد.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_client: httpx.AsyncClient | None = None


async def startup() -> None:
    global _client
    _client = httpx.AsyncClient(timeout=httpx.Timeout(15.0), headers=UA, follow_redirects=True)


async def shutdown() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(15.0), headers=UA, follow_redirects=True)
    return _client


# ══════════════════════════════════════════ الكاش الذكي ═════════════════════
class TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        item = self._data.get(key)
        if not item:
            return None
        expires, value = item
        if time.time() > expires:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value, ttl: float) -> None:
        self._data[key] = (time.time() + max(1.0, ttl), value)


CACHE = TTLCache()

# ══════════════════════════════════════════ ساعات التداول ══════════════════
EXCHANGE_HOURS = {
    "casablanca": ("Africa/Casablanca", 9, 30, 15, 40),
    "us":         ("America/New_York", 9, 30, 16, 0),
    "canada":     ("America/Toronto", 9, 30, 16, 0),
    "uk":         ("Europe/London", 8, 0, 16, 30),
    "france":     ("Europe/Paris", 9, 0, 17, 30),
    "germany":    ("Europe/Berlin", 9, 0, 17, 30),
    "netherlands":("Europe/Amsterdam", 9, 0, 17, 30),
    "spain":      ("Europe/Madrid", 9, 0, 17, 30),
    "switzerland":("Europe/Zurich", 9, 0, 17, 30),
    "italy":      ("Europe/Rome", 9, 0, 17, 30),
}


def market_state(market: str) -> str:
    hours = EXCHANGE_HOURS.get((market or "").lower())
    if hours is None:
        return "open"  # crypto
    tz, oh, om, ch, cm = hours
    now = datetime.now(ZoneInfo(tz))
    if now.weekday() >= 5:
        return "weekend"
    minutes = now.hour * 60 + now.minute
    if oh * 60 + om <= minutes < ch * 60 + cm:
        return "open"
    return "closed"


def smart_ttl(kind: str, market: str | None = None) -> float:
    kind = kind.lower()
    if kind == "crypto":
        return 5.0
    if kind == "fx":
        return 3600.0 * 2
    if kind == "gold_silver":
        return 60.0 if market_state("us") == "open" else 300.0
    state = market_state(market or kind)
    if state == "open":
        return 15.0
    return 3600.0


# ══════════════════════════════════════════ Single-Flight Locking ═══════════
_inflight_locks: dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()


async def _get_key_lock(key: str) -> asyncio.Lock:
    async with _global_lock:
        if key not in _inflight_locks:
            _inflight_locks[key] = asyncio.Lock()
        return _inflight_locks[key]


async def cached_json(key: str, ttl: float, fetch):
    hit = CACHE.get(key)
    if hit is not None:
        return hit
    lock = await _get_key_lock(key)
    async with lock:
        hit = CACHE.get(key)
        if hit is not None:
            return hit
        data = await fetch()
        if data is not None:
            CACHE.set(key, data, ttl)
        return data


async def get_json(url: str, *, params: dict | None = None, headers: dict | None = None):
    try:
        r = await client().get(url, params=params, headers=headers)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


async def post_json(url: str, payload: dict, *, headers: dict | None = None):
    import json
    try:
        hdrs = {"Content-Type": "text/plain"}
        if headers:
            hdrs.update(headers)
        r = await client().post(url, content=json.dumps(payload), headers=hdrs)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None
