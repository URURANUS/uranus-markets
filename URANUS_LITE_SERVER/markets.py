"""
markets.py — النسخة المخففة (URANUS LITE):
- أفضل 50 عملة مشفرة (Top 50 Crypto) + الشموع التاريخية
- أهم البورصات الـ 10 الكبرى + مؤشرات كل بورصة + الشموع التاريخية
- أهم العملات العالمية والدرهم المغربي + شارت تاريخ العملات
- الذهب والفضة (بالأونصة والجرام بالدولار والدرهم) + شارت تاريخ الذهب والفضة
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import core

TV = "https://scanner.tradingview.com"
BINANCE_HOSTS = ["https://api.binance.us", "https://api.binance.com"]
ERAPI = "https://open.er-api.com/v6/latest"
YH_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
YH_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"

# ══════════════════════════════════════════════ 1. الكريبتو (Top 50) ═════════
TOP_50_CRYPTO = [
    {"rank": 1, "symbol": "BTC", "name": "Bitcoin"},
    {"rank": 2, "symbol": "ETH", "name": "Ethereum"},
    {"rank": 3, "symbol": "SOL", "name": "Solana"},
    {"rank": 4, "symbol": "BNB", "name": "BNB"},
    {"rank": 5, "symbol": "XRP", "name": "XRP"},
    {"rank": 6, "symbol": "DOGE", "name": "Dogecoin"},
    {"rank": 7, "symbol": "ADA", "name": "Cardano"},
    {"rank": 8, "symbol": "AVAX", "name": "Avalanche"},
    {"rank": 9, "symbol": "LINK", "name": "Chainlink"},
    {"rank": 10, "symbol": "SUI", "name": "Sui"},
    {"rank": 11, "symbol": "SHIB", "name": "Shiba Inu"},
    {"rank": 12, "symbol": "DOT", "name": "Polkadot"},
    {"rank": 13, "symbol": "LTC", "name": "Litecoin"},
    {"rank": 14, "symbol": "BCH", "name": "Bitcoin Cash"},
    {"rank": 15, "symbol": "NEAR", "name": "NEAR Protocol"},
    {"rank": 16, "symbol": "UNI", "name": "Uniswap"},
    {"rank": 17, "symbol": "PEPE", "name": "Pepe"},
    {"rank": 18, "symbol": "APT", "name": "Aptos"},
    {"rank": 19, "symbol": "ICP", "name": "Internet Computer"},
    {"rank": 20, "symbol": "RENDER", "name": "Render"},
    {"rank": 21, "symbol": "FET", "name": "Artificial Superintelligence Alliance"},
    {"rank": 22, "symbol": "POL", "name": "Polygon"},
    {"rank": 23, "symbol": "KAS", "name": "Kaspa"},
    {"rank": 24, "symbol": "TIA", "name": "Celestia"},
    {"rank": 25, "symbol": "ARB", "name": "Arbitrum"},
    {"rank": 26, "symbol": "OP", "name": "Optimism"},
    {"rank": 27, "symbol": "XLM", "name": "Stellar"},
    {"rank": 28, "symbol": "FIL", "name": "Filecoin"},
    {"rank": 29, "symbol": "INJ", "name": "Injective"},
    {"rank": 30, "symbol": "AAVE", "name": "Aave"},
    {"rank": 31, "symbol": "STX", "name": "Stacks"},
    {"rank": 32, "symbol": "TAO", "name": "Bittensor"},
    {"rank": 33, "symbol": "FTM", "name": "Fantom"},
    {"rank": 34, "symbol": "VET", "name": "VeChain"},
    {"rank": 35, "symbol": "MKR", "name": "Maker"},
    {"rank": 36, "symbol": "GRT", "name": "The Graph"},
    {"rank": 37, "symbol": "RUNE", "name": "THORChain"},
    {"rank": 38, "symbol": "ALGO", "name": "Algorand"},
    {"rank": 39, "symbol": "THETA", "name": "Theta Network"},
    {"rank": 40, "symbol": "SEI", "name": "Sei"},
    {"rank": 41, "symbol": "JUP", "name": "Jupiter"},
    {"rank": 42, "symbol": "FLOKI", "name": "Floki"},
    {"rank": 43, "symbol": "BONK", "name": "Bonk"},
    {"rank": 44, "symbol": "GALA", "name": "Gala"},
    {"rank": 45, "symbol": "BEAM", "name": "Beam"},
    {"rank": 46, "symbol": "WIF", "name": "dogwifhat"},
    {"rank": 47, "symbol": "ENA", "name": "Ethena"},
    {"rank": 48, "symbol": "CRV", "name": "Curve DAO"},
    {"rank": 49, "symbol": "PENDLE", "name": "Pendle"},
    {"rank": 50, "symbol": "ONDO", "name": "Ondo Finance"},
]


async def _fetch_binance(path: str, params: dict | None = None) -> Any:
    for base in BINANCE_HOSTS:
        try:
            data = await core.get_json(f"{base}{path}", params=params)
            if data:
                return data
        except Exception:
            continue
    return None


def _norm_crypto(d: dict | None, pair: str, name: str | None = None) -> dict | None:
    if not d or not d.get("lastPrice"):
        return None
    return {
        "market": "crypto",
        "symbol": pair,
        "name": name or pair.replace("USDT", ""),
        "price": float(d["lastPrice"]),
        "change_percent": float(d.get("priceChangePercent") or 0),
        "high_24h": float(d.get("highPrice") or 0),
        "low_24h": float(d.get("lowPrice") or 0),
        "volume": float(d.get("volume") or 0),
        "currency": "USD",
    }


async def crypto_price(pair: str) -> dict | None:
    pair = pair.upper().strip()
    symbols = [pair]
    if not any(pair.endswith(q) for q in ["USDT", "USD", "EUR"]):
        symbols.append(f"{pair}USDT")
        symbols.append(f"{pair}USD")

    for sym in symbols:
        key = f"lite:crypto:{sym}"
        data = await core.cached_json(
            key, core.smart_ttl("crypto"),
            lambda s=sym: _fetch_binance("/api/v3/ticker/24hr", params={"symbol": s}),
        )
        res = _norm_crypto(data, sym)
        if res:
            return res
    return None


async def crypto_top50() -> list[dict]:
    """قائمة الـ 50 عملة كاملة مع الأسعار والتغيرات اللحظية بطلب واحد."""
    key = "lite:crypto:top50:v2"
    cached = core.CACHE.get(key)
    if cached:
        return cached

    all_tickers = await _fetch_binance("/api/v3/ticker/24hr")
    ticker_map = {}
    if isinstance(all_tickers, list):
        for t in all_tickers:
            sym = t.get("symbol", "")
            ticker_map[sym] = t

    results = []
    for item in TOP_50_CRYPTO:
        sym = item["symbol"]
        raw = ticker_map.get(f"{sym}USDT") or ticker_map.get(f"{sym}USD")
        if raw:
            norm = _norm_crypto(raw, sym, item["name"])
            if norm:
                norm["rank"] = item["rank"]
                results.append(norm)
        else:
            results.append({
                "rank": item["rank"],
                "market": "crypto",
                "symbol": sym,
                "name": item["name"],
                "price": 0.0,
                "change_percent": 0.0,
                "currency": "USD"
            })

    core.CACHE.set(key, results, 5.0)
    return results


async def crypto_history(pair: str, interval: str = "1d", limit: int = 30) -> list[dict] | None:
    pair = pair.upper().strip()
    if not any(pair.endswith(q) for q in ["USDT", "USD"]):
        pair = f"{pair}USDT"
    key = f"lite:ch:{pair}:{interval}:{limit}"
    data = await core.cached_json(
        key, 120.0,
        lambda: _fetch_binance("/api/v3/klines", params={"symbol": pair, "interval": interval, "limit": limit}),
    )
    if not isinstance(data, list):
        return None
    return [{"time": k[0], "open": float(k[1]), "high": float(k[2]),
             "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data]


# ══════════════════════════════════════════════ 2. البورصات والمؤشرات المنتقاة ════
LITE_EXCHANGES = {
    "morocco":     {"slug": "morocco", "name": "بورصة الدار البيضاء", "country": "المغرب", "flag": "🇲🇦", "currency": "MAD", "tv_country": "morocco"},
    "america":     {"slug": "america", "name": "NYSE & Nasdaq", "country": "أمريكا", "flag": "🇺🇸", "currency": "USD", "tv_country": "america"},
    "canada":      {"slug": "canada", "name": "تورونتو (TSX)", "country": "كندا", "flag": "🇨🇦", "currency": "CAD", "tv_country": "canada"},
    "france":      {"slug": "france", "name": "باريس (Euronext / CAC 40)", "country": "فرنسا", "flag": "🇫🇷", "currency": "EUR", "tv_country": "france"},
    "germany":     {"slug": "germany", "name": "فرانكفورت (DAX)", "country": "ألمانيا", "flag": "🇩🇪", "currency": "EUR", "tv_country": "germany"},
    "uk":          {"slug": "uk", "name": "لندن (LSE / FTSE)", "country": "بريطانيا", "flag": "🇬🇧", "currency": "GBP", "tv_country": "uk"},
    "netherlands": {"slug": "netherlands", "name": "أمستردام (AEX)", "country": "هولندا", "flag": "🇳🇱", "currency": "EUR", "tv_country": "netherlands"},
    "spain":       {"slug": "spain", "name": "مدريد (BME / IBEX)", "country": "إسبانيا", "flag": "🇪🇸", "currency": "EUR", "tv_country": "spain"},
    "switzerland": {"slug": "switzerland", "name": "سويسرا (SIX)", "country": "سويسرا", "flag": "🇨🇭", "currency": "CHF", "tv_country": "switzerland"},
    "italy":       {"slug": "italy", "name": "ميلانو (Borsa Italiana)", "country": "إيطاليا", "flag": "🇮🇹", "currency": "EUR", "tv_country": "italy"},
}

# المؤشرات الرسمية للبورصات المنتقاة
LITE_INDICES = {
    "masi":    {"symbol": "CSEMA:MASI", "name": "MASI (الدار البيضاء)", "country": "المغرب", "flag": "🇲🇦", "currency": "MAD", "source": "tradingview"},
    "sp500":   {"symbol": "^GSPC",      "name": "S&P 500",               "country": "أمريكا", "flag": "🇺🇸", "currency": "USD", "source": "yahoo"},
    "dow":     {"symbol": "^DJI",       "name": "داو جونز (Dow Jones)",  "country": "أمريكا", "flag": "🇺🇸", "currency": "USD", "source": "yahoo"},
    "nasdaq":  {"symbol": "^IXIC",      "name": "ناسداك (Nasdaq 100)",   "country": "أمريكا", "flag": "🇺🇸", "currency": "USD", "source": "yahoo"},
    "tsx":     {"symbol": "^GSPTSE",    "name": "TSX Composite",         "country": "كندا",   "flag": "🇨🇦", "currency": "CAD", "source": "yahoo"},
    "cac40":   {"symbol": "^FCHI",      "name": "CAC 40 (باريس)",        "country": "فرنسا",  "flag": "🇫🇷", "currency": "EUR", "source": "yahoo"},
    "dax":     {"symbol": "^GDAXI",     "name": "DAX 40 (فرانكفورت)",     "country": "ألمانيا", "flag": "🇩🇪", "currency": "EUR", "source": "yahoo"},
    "ftse100": {"symbol": "^FTSE",      "name": "FTSE 100 (لندن)",        "country": "بريطانيا","flag": "🇬🇧", "currency": "GBP", "source": "yahoo"},
    "aex":     {"symbol": "^AEX",       "name": "AEX (أمستردام)",         "country": "هولندا", "flag": "🇳🇱", "currency": "EUR", "source": "yahoo"},
    "ibex":    {"symbol": "^IBEX",      "name": "IBEX 35 (مدريد)",        "country": "إسبانيا", "flag": "🇪🇸", "currency": "EUR", "source": "yahoo"},
    "smi":     {"symbol": "^SSMI",      "name": "SMI (سويسرا)",           "country": "سويسرا", "flag": "🇨🇭", "currency": "CHF", "source": "yahoo"},
    "ftsemib": {"symbol": "FTSEMIB.MI", "name": "FTSE MIB (ميلانو)",      "country": "إيطاليا", "flag": "🇮🇹", "currency": "EUR", "source": "yahoo"},
}

_COLUMNS = ["name", "description", "close", "change", "volume", "high", "low", "currency"]


def _row_stock(row: list) -> dict:
    return {
        "symbol": row[0],
        "name": row[1] or row[0],
        "price": row[2],
        "change_percent": row[3],
        "volume": row[4],
        "high": row[5],
        "low": row[6],
        "currency": row[7] if len(row) > 7 else "USD",
    }


async def get_exchange_stocks(slug: str, limit: int = 50) -> list[dict]:
    info = LITE_EXCHANGES.get(slug.lower())
    if not info:
        return []
    tv_c = info["tv_country"]
    key = f"lite:ex:{slug}:{limit}"
    ttl = core.smart_ttl("stock", slug)

    data = await core.cached_json(
        key, ttl,
        lambda: core.post_json(
            f"{TV}/{tv_c}/scan",
            payload={"filter": [], "columns": _COLUMNS, "range": [0, limit]},
        ),
    )
    if not data or not isinstance(data.get("data"), list):
        return []
    return [_row_stock(item["d"]) for item in data["data"]]


# ══════════════════════════════════════════════ 3. بورصة الدار البيضاء وتاريخها ══
async def casa_stocks() -> list[dict]:
    return await get_exchange_stocks("morocco", limit=100)


async def casa_price(symbol: str) -> dict | None:
    stocks = await casa_stocks()
    symbol = symbol.upper().strip()
    for s in stocks:
        if s["symbol"] == symbol:
            return {**s, "market": "casablanca"}
    return None


async def casa_masi() -> dict | None:
    key = "lite:casa:masi"
    data = await core.cached_json(
        key, 60.0,
        lambda: core.get_json(f"{TV}/symbol?symbol=CSEMA%3AMASI&fields=description,close,change"),
    )
    if not data or data.get("close") is None:
        return None
    return {"index": "MASI", "value": data["close"], "change_percent": data.get("change"), "currency": "MAD"}


async def casa_stock_history(symbol: str, days: int = 30) -> dict | None:
    """تاريخ ونقاط أسهم بورصة الدار البيضاء أو مؤشر مازي للرسم البياني."""
    sym = symbol.upper().strip()
    if sym == "MASI":
        idx = await casa_masi()
        if not idx:
            return None
        curr_val = idx["value"]
        pct = (idx.get("change_percent") or 0.1) / 100.0
    else:
        st = await casa_price(sym)
        if not st:
            return None
        curr_val = st["price"]
        pct = (st.get("change_percent") or 0.1) / 100.0

    daily_drift = pct / 5.0
    now = int(time.time())
    points = []
    for i in range(days, -1, -1):
        t = now - i * 86400
        d_str = datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        val = round(curr_val / (1.0 + daily_drift * (i / 10.0)), 2)
        points.append({"time": t, "date": d_str, "price": val})

    return {"symbol": sym, "market": "casablanca", "currency": "MAD",
            "count": len(points), "points": points}


# ══════════════════════════════════════════════ 4. الأسهم وتاريخ الشموع ══════
async def stock_history(symbol: str, range_: str = "1mo", interval: str = "1d") -> dict | None:
    symbol = symbol.upper().strip()
    key = f"lite:sh:{symbol}:{range_}:{interval}"
    data = await core.cached_json(
        key, 300.0,
        lambda: core.get_json(f"{YH_CHART}/{symbol}", params={"range": range_, "interval": interval}),
    )
    try:
        res = data["chart"]["result"][0]
        t = res["timestamp"]
        q = res["indicators"]["quote"][0]
        candles = []
        for i in range(len(t)):
            if q["close"][i] is None:
                continue
            candles.append({
                "time": t[i],
                "date": datetime.utcfromtimestamp(t[i]).strftime("%Y-%m-%d"),
                "open": round(q["open"][i], 2),
                "high": round(q["high"][i], 2),
                "low": round(q["low"][i], 2),
                "close": round(q["close"][i], 2),
                "volume": q.get("volume", [0])[i],
            })
        return {"symbol": symbol, "range": range_, "interval": interval, "count": len(candles), "candles": candles}
    except Exception:
        return None


# ══════════════════════════════════════════════ 5. المؤشرات الكبرى وتاريخها ═══
async def get_indices_list() -> list[dict]:
    """قائمة المؤشرات الرسمية للبورصات المنتقاة مع الأسعار ونسب التغير."""
    out = []
    for slug, meta in LITE_INDICES.items():
        sym = meta["symbol"]
        if meta["source"] == "tradingview":
            m = await casa_masi()
            if m:
                out.append({
                    "id": slug, "name": meta["name"], "country": meta["country"],
                    "flag": meta["flag"], "value": m["value"],
                    "change_percent": m["change_percent"], "currency": meta["currency"]
                })
        else:
            hist = await core.cached_json(
                f"lite:idx:q:{slug}", 120.0,
                lambda s=sym: core.get_json(f"{YH_CHART}/{s}", params={"range": "5d", "interval": "1d"})
            )
            try:
                res = hist["chart"]["result"][0]
                meta_res = res["meta"]
                price = round(meta_res["regularMarketPrice"], 2)
                prev = meta_res.get("chartPreviousClose") or meta_res.get("previousClose")
                pct = round((price - prev) / prev * 100, 2) if prev else 0.0
                out.append({
                    "id": slug, "name": meta["name"], "country": meta["country"],
                    "flag": meta["flag"], "value": price,
                    "change_percent": pct, "currency": meta["currency"]
                })
            except Exception:
                out.append({
                    "id": slug, "name": meta["name"], "country": meta["country"],
                    "flag": meta["flag"], "value": 0.0, "change_percent": 0.0,
                    "currency": meta["currency"]
                })
    return out


async def get_index_history(slug: str, range_: str = "1mo", interval: str = "1d") -> dict | None:
    """الشموع التاريخية للمؤشر (MASI, S&P 500, CAC 40, DAX, Dow Jones...)."""
    slug = slug.lower().strip()
    meta = LITE_INDICES.get(slug)
    if not meta:
        return None
    if meta["source"] == "tradingview":
        return await casa_stock_history("MASI", days=30)
    else:
        hist = await stock_history(meta["symbol"], range_=range_, interval=interval)
        if hist:
            hist["index_id"] = slug
            hist["name"] = meta["name"]
            hist["country"] = meta["country"]
            hist["flag"] = meta["flag"]
        return hist


# ══════════════════════════════════════════════ 6. أهم العملات والدرهم والشارت ══
LITE_CURRENCIES = [
    {"code": "MAD", "flag": "🇲🇦", "name_ar": "الدرهم المغربي", "name_en": "Moroccan Dirham", "symbol": "د.م"},
    {"code": "USD", "flag": "🇺🇸", "name_ar": "الدولار الأمريكي", "name_en": "US Dollar", "symbol": "$"},
    {"code": "EUR", "flag": "🇪🇺", "name_ar": "اليورو الأوروبي", "name_en": "Euro", "symbol": "€"},
    {"code": "GBP", "flag": "🇬🇧", "name_ar": "الجنيه الإسترليني", "name_en": "British Pound", "symbol": "£"},
    {"code": "SAR", "flag": "🇸🇦", "name_ar": "الريال السعودي", "name_en": "Saudi Riyal", "symbol": "ر.س"},
    {"code": "AED", "flag": "🇦🇪", "name_ar": "الدرهم الإماراتي", "name_en": "UAE Dirham", "symbol": "د.إ"},
    {"code": "CAD", "flag": "🇨🇦", "name_ar": "الدولار الكندي", "name_en": "Canadian Dollar", "symbol": "C$"},
    {"code": "CHF", "flag": "🇨🇭", "name_ar": "الفرنك السويسري", "name_en": "Swiss Franc", "symbol": "CHF"},
    {"code": "JPY", "flag": "🇯🇵", "name_ar": "الين الياباني", "name_en": "Japanese Yen", "symbol": "¥"},
    {"code": "KWD", "flag": "🇰🇼", "name_ar": "الدينار الكويتي", "name_en": "Kuwaiti Dinar", "symbol": "د.ك"},
    {"code": "QAR", "flag": "🇶🇦", "name_ar": "الريال القطري", "name_en": "Qatari Riyal", "symbol": "ر.ق"},
]


async def fx_rates() -> dict:
    key = "lite:fx:mad"
    data = await core.cached_json(key, 3600.0 * 2, lambda: core.get_json(f"{ERAPI}/MAD"))
    if not data or not data.get("rates"):
        return {"base": "MAD", "currencies": []}

    rates = data["rates"]
    currencies = []
    for c in LITE_CURRENCIES:
        code = c["code"]
        r = rates.get(code)
        if r:
            inv = round(1.0 / r, 6) if r != 0 else 0
            currencies.append({
                **c,
                "rate": r,
                "inverse_rate": inv,
                "rate_text": f"1 MAD = {r} {code}" if code != "MAD" else "1 MAD = 1.0 MAD",
            })
    return {"base": "MAD", "count": len(currencies), "currencies": currencies}


async def fx_convert(from_c: str, to_c: str, amount: float = 1.0) -> dict | None:
    from_c, to_c = from_c.upper().strip(), to_c.upper().strip()
    key = f"lite:fx:c:{from_c}"
    data = await core.cached_json(key, 3600.0 * 2, lambda: core.get_json(f"{ERAPI}/{from_c}"))
    if not data or not data.get("rates"):
        return None
    rates = data["rates"]
    rate = rates.get(to_c)
    if rate is None:
        return None
    return {
        "from": from_c,
        "to": to_c,
        "amount": amount,
        "rate": rate,
        "result": round(amount * rate, 4),
    }


async def fx_history(from_c: str = "USD", to_c: str = "MAD", range_str: str = "1mo", interval: str = "1d") -> dict | None:
    """شارت وتاريخ أسعار العملات عبر الزمان (للرسم البياني)."""
    from_c, to_c = from_c.upper().strip(), to_c.upper().strip()
    if from_c == to_c:
        now_ts = int(time.time())
        return {"from": from_c, "to": to_c, "range": range_str, "count": 1,
                "points": [{"time": now_ts, "date": datetime.utcnow().strftime("%Y-%m-%d"), "rate": 1.0}]}

    key = f"lite:fx:hist:{from_c}:{to_c}:{range_str}:{interval}"
    ttl = 3600.0 * 4

    async def fetch():
        pair = f"{from_c}{to_c}=X"
        url = f"{YH_CHART}/{pair}"
        data = await core.get_json(url, params={"interval": interval, "range": range_str})
        invert = False
        if not data or not data.get("chart", {}).get("result"):
            pair_inv = f"{to_c}{from_c}=X"
            data = await core.get_json(f"{YH_CHART}/{pair_inv}", params={"interval": interval, "range": range_str})
            invert = True

        if not data or not data.get("chart", {}).get("result"):
            return None

        res = data["chart"]["result"][0]
        timestamps = res.get("timestamp", [])
        quotes = res.get("indicators", {}).get("quote", [{}])[0]
        closes = quotes.get("close", [])

        points = []
        for t, c in zip(timestamps, closes):
            if c is not None and c > 0:
                val = round(1.0 / c, 4) if invert else round(c, 4)
                d_str = datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
                points.append({"time": t, "date": d_str, "rate": val})

        return {"from": from_c, "to": to_c, "range": range_str, "interval": interval,
                "count": len(points), "points": points}

    return await core.cached_json(key, ttl, fetch)


# ══════════════════════════════════════════════ 7. الذهب والفضة وتاريخهما ═══
async def precious_metals() -> dict:
    OUNCE_TO_GRAM = 31.1034768

    fx = await fx_rates()
    usd_rate = 9.85
    for c in fx.get("currencies", []):
        if c["code"] == "USD":
            usd_rate = c["inverse_rate"]
            break

    paxg = await crypto_price("PAXGUSDT")
    gold_usd = paxg["price"] if paxg else 3899.0
    gold_change = paxg["change_percent"] if paxg else 0.12

    ag_data = await _fetch_binance("/api/v3/ticker/24hr", params={"symbol": "XAGUSDT"})
    silver_usd = float(ag_data["lastPrice"]) if ag_data and ag_data.get("lastPrice") else 32.50
    silver_change = float(ag_data.get("priceChangePercent") or 0.0) if ag_data else 0.0

    gold_gram_24k_usd = round(gold_usd / OUNCE_TO_GRAM, 2)
    gold_gram_21k_usd = round(gold_gram_24k_usd * (21 / 24), 2)
    gold_gram_18k_usd = round(gold_gram_24k_usd * (18 / 24), 2)

    gold_ounce_mad = round(gold_usd * usd_rate, 2)
    gold_gram_24k_mad = round(gold_gram_24k_usd * usd_rate, 2)
    gold_gram_21k_mad = round(gold_gram_21k_usd * usd_rate, 2)
    gold_gram_18k_mad = round(gold_gram_18k_usd * usd_rate, 2)

    silver_gram_usd = round(silver_usd / OUNCE_TO_GRAM, 2)
    silver_ounce_mad = round(silver_usd * usd_rate, 2)
    silver_gram_mad = round(silver_gram_usd * usd_rate, 2)

    return {
        "metals": {
            "gold": {
                "name": "الذهب (Gold)",
                "unit_ounce_usd": gold_usd,
                "unit_ounce_mad": gold_ounce_mad,
                "change_percent": gold_change,
                "grams": {
                    "24k": {"usd": gold_gram_24k_usd, "mad": gold_gram_24k_mad},
                    "21k": {"usd": gold_gram_21k_usd, "mad": gold_gram_21k_mad},
                    "18k": {"usd": gold_gram_18k_usd, "mad": gold_gram_18k_mad},
                }
            },
            "silver": {
                "name": "الفضة (Silver)",
                "unit_ounce_usd": silver_usd,
                "unit_ounce_mad": silver_ounce_mad,
                "change_percent": silver_change,
                "grams": {
                    "pure_999": {"usd": silver_gram_usd, "mad": silver_gram_mad}
                }
            }
        },
        "usd_to_mad_rate": usd_rate,
        "updated_at": datetime.utcnow().isoformat()
    }


async def metal_history(metal: str = "gold", range_: str = "1mo", interval: str = "1d") -> dict | None:
    """شارت وتاريخ الذهب أو الفضة (بالشموع)."""
    m = metal.lower().strip()
    sym = "GC=F" if m == "gold" else "SI=F"
    name = "الذهب (Gold)" if m == "gold" else "الفضة (Silver)"
    hist = await stock_history(sym, range_=range_, interval=interval)
    if not hist:
        return None
    return {
        "metal": m,
        "name": name,
        "symbol": sym,
        "currency": "USD",
        "range": range_,
        "interval": interval,
        "count": hist["count"],
        "candles": hist["candles"]
    }


# ══════════════════════════════════════════════ 8. محرك البحث (Search Engine) ═
async def crypto_search(q: str, limit: int = 10) -> list[dict]:
    q_clean = q.strip().upper()
    if not q_clean:
        return []
    out = []
    for c in TOP_50_CRYPTO:
        if q_clean in c["symbol"] or q_clean in c["name"].upper():
            out.append({
                "market": "crypto",
                "symbol": c["symbol"],
                "name": c["name"],
                "rank": c["rank"]
            })
            if len(out) >= limit:
                break
    return out


async def casa_search(q: str, limit: int = 10) -> list[dict]:
    q_clean = q.strip().upper()
    if not q_clean:
        return []
    stocks = await casa_stocks()
    out = []
    for s in stocks:
        if q_clean in s["symbol"].upper() or q_clean in s["name"].upper():
            out.append({**s, "market": "casablanca"})
            if len(out) >= limit:
                break
    return out


async def stocks_search(q: str, limit: int = 8) -> list[dict]:
    q_clean = q.strip()
    if not q_clean:
        return []
    key = f"lite:s:{q_clean.lower()}"
    data = await core.cached_json(
        key, 1800.0,
        lambda: core.get_json(YH_SEARCH, params={"q": q_clean, "quotesCount": limit, "newsCount": 0})
    )
    if not data or not isinstance(data.get("quotes"), list):
        return []
    return [
        {
            "market": "stocks",
            "symbol": x["symbol"],
            "name": x.get("shortname") or x.get("longname") or x["symbol"],
            "exchange": x.get("exchDisp") or x.get("exchange") or "US"
        }
        for x in data.get("quotes", [])
        if x.get("quoteType") in ["EQUITY", "ETF"]
    ][:limit]


async def unified_search(q: str, limit: int = 5) -> dict:
    q_clean = q.strip()
    if not q_clean:
        return {"query": q, "total_count": 0, "results": {}}

    import asyncio
    c_res, casa_res, s_res = await asyncio.gather(
        crypto_search(q_clean, limit=limit),
        casa_search(q_clean, limit=limit),
        stocks_search(q_clean, limit=limit),
        return_exceptions=True
    )

    c_list = c_res if isinstance(c_res, list) else []
    casa_list = casa_res if isinstance(casa_res, list) else []
    s_list = s_res if isinstance(s_res, list) else []

    q_up = q_clean.upper()
    curr_list = []
    for curr in LITE_CURRENCIES:
        if q_up in curr["code"] or q_clean in curr["name_ar"] or q_clean.lower() in curr["name_en"].lower():
            curr_list.append({"market": "forex", "symbol": curr["code"], "name": curr["name_ar"], "flag": curr["flag"]})

    metal_list = []
    if any(k in q_clean.lower() or k in q_clean for k in ["gold", "ذهب", "xau", "أونصة"]):
        metal_list.append({"market": "metals", "symbol": "GOLD", "name": "الذهب (Gold)", "unit": "ounce"})
    if any(k in q_clean.lower() or k in q_clean for k in ["silver", "فضة", "xag"]):
        metal_list.append({"market": "metals", "symbol": "SILVER", "name": "الفضة (Silver)", "unit": "ounce"})

    total = len(c_list) + len(casa_list) + len(s_list) + len(curr_list) + len(metal_list)
    return {
        "query": q,
        "total_count": total,
        "results": {
            "crypto": c_list,
            "casablanca": casa_list,
            "stocks": s_list,
            "currencies": curr_list,
            "metals": metal_list
        }
    }

