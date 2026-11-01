"""
core.py — الطبقة المشتركة: عميل HTTP، كاش ذكي واعٍ بساعات التداول، عدّاد المصادر.

هذه هي القلب الذي يجعل 10,000 مستخدم متزامن يستهلكون بضع مئات نداءات يومياً
على المصادر الخارجية فقط.
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_client: httpx.AsyncClient | None = None


async def startup() -> None:
    global _client
    _client = httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers=UA, follow_redirects=True)


async def shutdown() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers=UA, follow_redirects=True)
    return _client


# ══════════════════════════════════════════ الكاش الذكي ═════════════════════
class TTLCache:
    """كاش بسيط بمهلة انتهاء لكل مفتاح."""

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

    def purge(self) -> int:
        now = time.time()
        stale = [k for k, (exp, _) in self._data.items() if now > exp]
        for k in stale:
            self._data.pop(k, None)
        return len(stale)


CACHE = TTLCache()

# ══════════════════════════════════════ ساعات التداول العالمية ══════════════
# (tz, open_h, open_m, close_h, close_m) — أيام العمل الاثنين–الجمعة
EXCHANGE_HOURS: dict[str, tuple[str, int, int, int, int]] = {
    "casablanca": ("Africa/Casablanca", 9, 30, 15, 30),
    "us":         ("America/New_York", 9, 30, 16, 0),
    "uk":         ("Europe/London", 8, 0, 16, 30),
    "france":     ("Europe/Paris", 9, 0, 17, 30),
    "germany":    ("Europe/Berlin", 9, 0, 17, 30),
    "japan":      ("Asia/Tokyo", 9, 0, 15, 0),
    "china":      ("Asia/Shanghai", 9, 30, 15, 0),
    "india":      ("Asia/Kolkata", 9, 15, 15, 30),
    "uae":        ("Asia/Dubai", 10, 0, 14, 45),
    "qatar":      ("Asia/Qatar", 10, 0, 14, 45),
    "egypt":      ("Africa/Cairo", 10, 0, 14, 30),
    "saudi":      ("Asia/Riyadh", 10, 0, 15, 0),
    "turkey":     ("Europe/Istanbul", 10, 0, 18, 0),
    "brazil":     ("America/Sao_Paulo", 10, 0, 17, 30),
}

MARKET_ALIAS = {
    "crypto": None,
    "casablanca": "casablanca",
    "casa": "casablanca",
    "us": "us",
    "usa": "us",
}


def market_state(market: str) -> str:
    """'open' أو 'closed' أو 'weekend'."""
    key = MARKET_ALIAS.get((market or "").lower(), (market or "").lower())
    hours = EXCHANGE_HOURS.get(key)
    if hours is None:
        return "unknown"
    tz, oh, om, ch, cm = hours
    now = datetime.now(ZoneInfo(tz))
    if now.weekday() >= 5:
        return "weekend"
    minutes = now.hour * 60 + now.minute
    if oh * 60 + om <= minutes < ch * 60 + cm:
        return "open"
    return "closed"


def smart_ttl(kind: str, market: str | None = None) -> float:
    """
    المهلة بالثواني حسب نوع البيانات وحالة السوق — هذا ما يحول
    ملايين الطلبات المحتملة إلى بضع مئات نداءات يومية على المصادر.
    """
    kind = kind.lower()
    if kind == "crypto":
        return 5.0
    if kind == "fx":
        return 6 * 3600.0          # أسعار الصرف تتحدث يومياً
    if kind == "commodity":
        return 120.0 if market_state("us") == "open" else 1800.0
    if kind == "indices":
        return 60.0 if market_state("us") == "open" else 900.0
    if kind == "news":
        return 600.0

    # أسهم: حسب حالة السوق الخاص بها
    state = market_state(market or "")
    if state == "open":
        return 60.0                 # أثناء التداول: دقيقة كافية للأسهم
    if state == "weekend":
        return 48 * 3600.0          # العطلة: يومان
    return 6 * 3600.0               # مغلق: حتى الجلسة القادمة


# ══════════════════════════════════════════ عدّاد المصادر ═══════════════════
_source_stats: dict[str, dict] = defaultdict(lambda: {"calls_today": 0, "total_calls": 0})
_stats_date = {"day": datetime.utcnow().date().isoformat()}


def record_source(name: str) -> None:
    today = datetime.utcnow().date().isoformat()
    if _stats_date["day"] != today:            # تصفير يومي تلقائي
        _stats_date["day"] = today
        for s in _source_stats.values():
            s["calls_today"] = 0
    stat = _source_stats[name]
    stat["calls_today"] += 1
    stat["total_calls"] += 1
    stat["last_call"] = datetime.utcnow().isoformat(timespec="seconds")


def source_stats() -> dict:
    return {"day": _stats_date["day"], "sources": dict(_source_stats)}


# ══════════════════════════════════════════ جلب موحّد مع كاش وقفل التزامن ════════
import asyncio
_inflight_locks: dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()


async def _get_key_lock(key: str) -> asyncio.Lock:
    async with _global_lock:
        if key not in _inflight_locks:
            _inflight_locks[key] = asyncio.Lock()
        return _inflight_locks[key]


async def cached_json(key: str, ttl: float, fetch):
    """
    يرجع من الكاش إن وجد، ومع حماية قفل التزامن (Single-Flight Lock)
    حتى لو وصل 1,000 طلب في نفس الجزء من الثانية، يتم تنفيذ نداء خارجي واحد فقط.
    """
    hit = CACHE.get(key)
    if hit is not None:
        return hit, True
    lock = await _get_key_lock(key)
    async with lock:
        # فحص مضاعف بعد الحصول على القفل (Double-checked locking)
        hit = CACHE.get(key)
        if hit is not None:
            return hit, True
        data = await fetch()
        if data is not None:
            CACHE.set(key, data, ttl)
        return data, False


async def get_json(url: str, *, params: dict | None = None, headers: dict | None = None,
                   source: str = "other"):
    record_source(source)
    try:
        r = await client().get(url, params=params, headers=headers)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


async def post_json(url: str, payload: dict, *, source: str = "other"):
    """POST مع Content-Type: text/plain — يتجاوز CORS preflight الذي يرفضه TradingView."""
    record_source(source)
    try:
        r = await client().post(url, content=_json_dumps(payload),
                                headers={"Content-Type": "text/plain"})
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _json_dumps(payload: dict) -> str:
    import json
    return json.dumps(payload)
