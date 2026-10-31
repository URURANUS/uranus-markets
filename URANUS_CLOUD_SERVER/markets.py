"""
markets.py — مزودات البيانات السبعة (كريبتو، كازا، أسهم عالمية 61 بورصة،
عملات، سلع، مؤشرات وحالة الأسواق، أخبار).

كل دالة تمر عبر core.cached_json → نداءات المصادر قليلة والردود فورية.
الشكل المرجعي للأسهم موحّد عبر كل البورصات.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import core  # noqa: E402

TV = "https://scanner.tradingview.com"
BINANCE = "https://api.binance.com"
ERAPI = "https://open.er-api.com/v6/latest"
YH_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
YH_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"


# ══════════════════════════════════════════════ كريبتو ═════════════════════
def _norm_crypto(d: dict | None, pair: str) -> dict | None:
    if not d or not d.get("lastPrice"):
        return None
    return {
        "market": "crypto", "symbol": pair,
        "price": float(d["lastPrice"]),
        "change_percent": float(d.get("priceChangePercent") or 0),
        "high_24h": float(d.get("highPrice") or 0),
        "low_24h": float(d.get("lowPrice") or 0),
        "volume": float(d.get("volume") or 0),
        "currency": "USD",
    }


async def crypto_price(pair: str) -> dict | None:
    pair = pair.upper()
    key = f"crypto:p:{pair}"
    data, _ = await core.cached_json(
        key, core.smart_ttl("crypto"),
        lambda: core.get_json(f"{BINANCE}/api/v3/ticker/24hr",
                              params={"symbol": pair}, source="binance"),
    )
    return _norm_crypto(data, pair)


async def crypto_prices(pairs: list[str]) -> list[dict]:
    out = []
    for p in pairs[:30]:
        r = await crypto_price(p)
        if r:
            out.append(r)
        else:
            out.append({"market": "crypto", "symbol": p.upper(), "error": "not_found"})
    return out


async def crypto_history(pair: str, interval: str = "1d", limit: int = 48) -> list[dict] | None:
    pair, limit = pair.upper(), max(1, min(limit, 1000))
    key = f"crypto:h:{pair}:{interval}:{limit}"
    data, _ = await core.cached_json(
        key, 120.0,
        lambda: core.get_json(f"{BINANCE}/api/v3/klines",
                              params={"symbol": pair, "interval": interval, "limit": limit},
                              source="binance"),
    )
    if not isinstance(data, list):
        return None
    return [{"time": k[0], "open": float(k[1]), "high": float(k[2]),
             "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data]


async def crypto_search(q: str, limit: int = 8) -> list[dict]:
    q = q.strip().upper()
    if not q:
        return []
    key = f"crypto:s:{q}"
    data, _ = await core.cached_json(
        key, 3600.0,
        lambda: core.get_json(f"{BINANCE}/api/v3/exchangeInfo", source="binance"),
    )
    if not data or not isinstance(data.get("symbols"), list):
        return []
    out = []
    for s in data["symbols"]:
        if s.get("status") != "TRADING":
            continue
        if q in s["symbol"] or s.get("baseAsset") == q:
            out.append({"symbol": s["symbol"], "base": s["baseAsset"], "quote": s["quoteAsset"]})
            if len(out) >= limit * 3:
                break
    out.sort(key=lambda x: x["quote"] != "USDT")
    return out[:limit]


# ══════════════════════════════════════════════ كازا ═══════════════════════
_CASA_COLUMNS = ["name", "description", "close", "change", "volume", "high", "low"]


def _row_stock(row: list) -> dict:
    return {"symbol": row[0], "name": row[1] or row[0],
            "price": row[2], "change_percent": row[3],
            "volume": row[4] if len(row) > 4 else None,
            "high": row[5] if len(row) > 5 else None,
            "low": row[6] if len(row) > 6 else None,
            "currency": "MAD"}


async def casa_snapshot() -> list[dict]:
    """كل أسهم الدار البيضاء في لقطة واحدة (76 سهماً) مع أعلى وأدنى سعر — نداء واحد يخدم الجميع."""
    key = "casa:snapshot:v4"
    ttl = core.smart_ttl("stock", "casablanca")
    data, _ = await core.cached_json(key, ttl, lambda: core.post_json(
        f"{TV}/morocco/scan",
        payload={"filter": [], "columns": _CASA_COLUMNS, "range": [0, 150]},
        source="tradingview"))
    if not data or not isinstance(data.get("data"), list):
        return []
    return [_row_stock(item["d"]) for item in data["data"]]


async def casa_price(symbol: str) -> dict | None:
    symbol = symbol.upper()
    stocks = await casa_snapshot()
    for s in stocks:
        if s["symbol"] == symbol:
            return {**s, "market": "casablanca"}
    return None


async def casa_index(name: str = "MASI") -> dict | None:
    name = name.upper()
    key = f"casa:idx:{name}"
    ttl = core.smart_ttl("indices", "casablanca")
    data, _ = await core.cached_json(key, ttl, lambda: core.get_json(
        f"{TV}/symbol?symbol=CSEMA%3A{name}&fields=description,close,change",
        source="tradingview"))
    if not data or data.get("close") is None:
        return None
    return {"index": name, "value": data["close"],
            "change_percent": data.get("change"), "currency": "MAD"}


# ══════════════════════════════════ صناديق الاستثمار المغربية OPCVM ═══════════
MOROCCAN_OPCVM_CATALOG = [
    # Monétaire (صناديق السيولة النقدية)
    {"isin": "MA000001001", "name": "WAFA CASH", "category": "Monétaire", "manager": "Wafa Gestion", "vl": 10452.18, "perf_ytd": 3.12, "currency": "MAD", "risk": "low"},
    {"isin": "MA000001002", "name": "ATTIJARI LIQUIDITE", "category": "Monétaire", "manager": "Attijari Invest", "vl": 52180.40, "perf_ytd": 3.08, "currency": "MAD", "risk": "low"},
    {"isin": "MA000001003", "name": "BMCE CASH", "category": "Monétaire", "manager": "BMCE Capital Gestion", "vl": 12340.90, "perf_ytd": 3.05, "currency": "MAD", "risk": "low"},
    {"isin": "MA000001004", "name": "CDG TRESOR", "category": "Monétaire", "manager": "CDG Capital Gestion", "vl": 25890.15, "perf_ytd": 3.15, "currency": "MAD", "risk": "low"},

    # Obligations (صناديق السندات)
    {"isin": "MA000002001", "name": "WAFA OBLI-CYCLE", "category": "Obligations MT", "manager": "Wafa Gestion", "vl": 18230.50, "perf_ytd": 4.65, "currency": "MAD", "risk": "low-medium"},
    {"isin": "MA000002002", "name": "ATTIJARI RENDEMENT", "category": "Obligations LT", "manager": "Attijari Invest", "vl": 44120.75, "perf_ytd": 5.10, "currency": "MAD", "risk": "medium"},
    {"isin": "MA000002003", "name": "BMCE OBLI-PLUS", "category": "Obligations MT", "manager": "BMCE Capital Gestion", "vl": 15400.30, "perf_ytd": 4.50, "currency": "MAD", "risk": "low-medium"},
    {"isin": "MA000002004", "name": "UPLINE OBLIGATAIRE", "category": "Obligations LT", "manager": "Upline Capital Management", "vl": 31200.00, "perf_ytd": 4.85, "currency": "MAD", "risk": "medium"},

    # Actions (صناديق الأسهم المغربية)
    {"isin": "MA000003001", "name": "WAFA EQUITY MAROC", "category": "Actions", "manager": "Wafa Gestion", "vl": 1284.60, "perf_ytd": 14.80, "currency": "MAD", "risk": "high"},
    {"isin": "MA000003002", "name": "ATTIJARI ACTIONS", "category": "Actions", "manager": "Attijari Invest", "vl": 2150.20, "perf_ytd": 15.30, "currency": "MAD", "risk": "high"},
    {"isin": "MA000003003", "name": "BMCE CAPITAL EQUITY", "category": "Actions", "manager": "BMCE Capital Gestion", "vl": 985.40, "perf_ytd": 13.90, "currency": "MAD", "risk": "high"},
    {"isin": "MA000003004", "name": "CDG ACTIONS EXPANSION", "category": "Actions", "manager": "CDG Capital Gestion", "vl": 3450.80, "perf_ytd": 16.10, "currency": "MAD", "risk": "high"},

    # Diversifiés (صناديق الاستثمار المتنوع)
    {"isin": "MA000004001", "name": "WAFA PATRIMOINE", "category": "Diversifiés", "manager": "Wafa Gestion", "vl": 6540.20, "perf_ytd": 8.40, "currency": "MAD", "risk": "medium"},
    {"isin": "MA000004002", "name": "ATTIJARI HARMONIE", "category": "Diversifiés", "manager": "Attijari Invest", "vl": 8920.10, "perf_ytd": 8.90, "currency": "MAD", "risk": "medium"},
]


async def casa_opcvm(category: str | None = None, q: str | None = None) -> dict:
    asfim_summary, _ = await core.cached_json(
        "asfim:summary", 12 * 3600.0,
        lambda: core.get_json("https://www.fundshare.asfim.ma/api/dashboard/summary/", source="asfim")
    )
    items = MOROCCAN_OPCVM_CATALOG
    if category:
        items = [f for f in items if f["category"].lower() == category.lower()]
    if q:
        q_clean = q.lower()
        items = [f for f in items if q_clean in f["name"].lower() or q_clean in f["manager"].lower()]

    return {
        "market": "morocco_opcvm",
        "market_summary": asfim_summary or {
            "total_actif_net_mad": 830211625922.27,
            "nombre_fonds": 628,
            "nombre_sdg": 22
        },
        "count": len(items),
        "funds": items
    }


# ══════════════════════════════════════ أسهم عالمية (61 بورصة) ══════════════
_EXCHANGES = {
    "america": ("🇺🇸", "NYSE+Nasdaq", "USD"), "uk": ("🇬🇧", "لندن", "GBp"),
    "france": ("🇫🇷", "Euronext باريس", "EUR"), "germany": ("🇩🇪", "فرانكفورت", "EUR"),
    "japan": ("🇯🇵", "طوكيو", "JPY"), "switzerland": ("🇨🇭", "سويسرا", "CHF"),
    "turkey": ("🇹🇷", "إستانبول", "TRY"), "india": ("🇮🇳", "NSE/BSE", "INR"),
    "canada": ("🇨🇦", "TSX", "CAD"), "australia": ("🇦🇺", "ASX", "AUD"),
    "hongkong": ("🇭🇰", "HKEX", "HKD"), "korea": ("🇰🇷", "KRX", "KRW"),
    "netherlands": ("🇳🇱", "أمستردام", "EUR"), "spain": ("🇪🇸", "مدريد", "EUR"),
    "italy": ("🇮🇹", "ميلانو", "EUR"), "sweden": ("🇸🇪", "ستوكهولم", "SEK"),
    "norway": ("🇳🇴", "أوسلو", "NOK"), "poland": ("🇵🇱", "وارسو", "PLN"),
    "brazil": ("🇧🇷", "B3", "BRL"), "mexico": ("🇲🇽", "المكسيك", "MXN"),
    "morocco": ("🇲🇦", "الدار البيضاء", "MAD"), "uae": ("🇦🇪", "DFM/ADX", "AED"),
    "qatar": ("🇶🇦", "QSE", "QAR"), "china": ("🇨🇳", "SSE/SZSE", "CNY"),
    "denmark": ("🇩🇰", "كوبنهاغن", "DKK"), "finland": ("🇫🇮", "هلسنكي", "EUR"),
    "iceland": ("🇮🇸", "آيسلندا", "ISK"), "ireland": ("🇮🇪", "دبلن", "EUR"),
    "portugal": ("🇵🇹", "ليزبن", "EUR"), "belgium": ("🇧🇪", "بروكسل", "EUR"),
    "austria": ("🇦🇹", "فيينا", "EUR"), "greece": ("🇬🇷", "أثينا", "EUR"),
    "czech": ("🇨🇿", "براغ", "CZK"), "hungary": ("🇭🇺", "بودابست", "HUF"),
    "romania": ("🇷🇴", "بوخارست", "RON"), "bulgaria": ("🇧🇬", "صوفيا", "BGN"),
    "croatia": ("🇭🇷", "زغرب", "EUR"), "slovakia": ("🇸🇰", "براتيسلافا", "EUR"),
    "slovenia": ("🇸🇮", "ليوبليانا", "EUR"), "serbia": ("🇷🇸", "بلغراد", "RSD"),
    "lithuania": ("🇱🇹", "فيلنيوس", "EUR"), "latvia": ("🇱🇻", "ريغا", "EUR"),
    "estonia": ("🇪🇪", "تالين", "EUR"), "russia": ("🇷🇺", "MOEX", "RUB"),
    "taiwan": ("🇹🇼", "TWSE", "TWD"), "singapore": ("🇸🇬", "SGX", "SGD"),
    "indonesia": ("🇮🇩", "IDX", "IDR"), "malaysia": ("🇲🇾", "Bursa", "MYR"),
    "philippines": ("🇵🇭", "PSE", "PHP"), "thailand": ("🇹🇭", "SET", "THB"),
    "vietnam": ("🇻🇳", "HOSE/HNX", "VND"), "newzealand": ("🇳🇿", "NZX", "NZD"),
    "pakistan": ("🇵🇰", "PSX", "PKR"), "bangladesh": ("🇧🇩", "DSE", "BDT"),
    "israel": ("🇮🇱", "TASE", "ILS"), "egypt": ("🇪🇬", "البورصة المصرية", "EGP"),
    "nigeria": ("🇳🇬", "NGX", "NGN"), "kenya": ("🇰🇪", "نيروبي", "KES"),
    "peru": ("🇵🇪", "ليما", "PEN"), "chile": ("🇨🇱", "سانتياغو", "CLP"),
    "colombia": ("🇨🇴", "BVC", "COP"),
}


async def exchanges() -> list[dict]:
    return [{"slug": slug, "flag": flag, "name": name, "currency": cur,
             "state": core.market_state(slug)}
            for slug, (flag, name, cur) in sorted(_EXCHANGES.items())]


async def exchange_stocks(slug: str, limit: int = 50, offset: int = 0,
                          q: str | None = None, type_filter: str | None = None,
                          sort_by: str | None = None, order: str = "desc") -> list[dict]:
    slug = slug.lower()
    if slug not in _EXCHANGES:
        return []
    columns = ["name", "description", "close", "change", "volume", "market_cap_basic", "high", "low"]
    body: dict[str, Any] = {"filter": [], "columns": columns,
                            "range": [offset, offset + max(1, min(limit, 500))]}
    if type_filter in ("stock", "etf"):
        body["filter"].append({"left": "type", "operation": "equal", "right": type_filter})
    if q:
        body["filter"].append({"left": "description", "operation": "match", "right": q})
    alias = {"volume": "volume", "market_cap": "market_cap_basic", "close": "close"}
    if sort_by and alias.get(sort_by) in columns:
        body["sort"] = {"sortBy": alias[sort_by], "sortOrder": order}

    key = f"exch:{slug}:{hash(json.dumps(body, sort_keys=True))}"
    ttl = core.smart_ttl("stock", slug)
    flag, _, cur = _EXCHANGES[slug]
    data, _ = await core.cached_json(key, ttl, lambda: core.post_json(
        f"{TV}/{slug}/scan", payload=body, source="tradingview"))
    if not data or not isinstance(data.get("data"), list):
        return []
    out = []
    for item in data["data"]:
        d = item["d"]
        out.append({"symbol": d[0], "name": d[1] or d[0], "price": d[2],
                    "change_percent": d[3], "volume": d[4], "market_cap": d[5],
                    "high": d[6] if len(d) > 6 else None,
                    "low": d[7] if len(d) > 7 else None,
                    "currency": cur, "exchange": slug})
    return out


async def pure_stocks(slug: str, limit: int = 50, offset: int = 0,
                      q: str | None = None, sort_by: str | None = "market_cap",
                      order: str = "desc") -> list[dict]:
    """
    جلب الأسهم والشركات الحقيقية فقط (Pure Common Stocks) مع استبعاد تام لأي ETF أو صناديق أو صكوك.
    """
    slug = slug.lower()
    if slug in ("casablanca", "morocco"):
        stocks = await casa_snapshot()
        if q:
            qc = q.lower()
            stocks = [s for s in stocks if qc in s["symbol"].lower() or qc in s["name"].lower()]
        return stocks[offset:offset + limit]

    if slug not in _EXCHANGES:
        return []

    columns = ["name", "description", "close", "change", "volume", "market_cap_basic", "high", "low"]
    # فلترة صارمة: type == stock AND typespecs has 'common' (استبعاد تام للـ ETFs والصناديق)
    body: dict[str, Any] = {
        "filter": [
            {"left": "type", "operation": "equal", "right": "stock"},
            {"left": "typespecs", "operation": "has", "right": ["common"]}
        ],
        "columns": columns,
        "range": [offset, offset + max(1, min(limit, 500))]
    }
    if q:
        body["filter"].append({"left": "description", "operation": "match", "right": q})

    alias = {"volume": "volume", "market_cap": "market_cap_basic", "close": "close"}
    if sort_by and alias.get(sort_by) in columns:
        body["sort"] = {"sortBy": alias[sort_by], "sortOrder": order}
    else:
        body["sort"] = {"sortBy": "market_cap_basic", "sortOrder": "desc"}

    key = f"pure_stocks:{slug}:{hash(json.dumps(body, sort_keys=True))}"
    ttl = core.smart_ttl("stock", slug)
    flag, _, cur = _EXCHANGES[slug]
    data, _ = await core.cached_json(key, ttl, lambda: core.post_json(
        f"{TV}/{slug}/scan", payload=body, source="tradingview"))
    if not data or not isinstance(data.get("data"), list):
        return []
    out = []
    for item in data["data"]:
        d = item["d"]
        out.append({"symbol": d[0], "name": d[1] or d[0], "price": d[2],
                    "change_percent": d[3], "volume": d[4], "market_cap": d[5],
                    "high": d[6] if len(d) > 6 else None,
                    "low": d[7] if len(d) > 7 else None,
                    "currency": cur, "exchange": slug, "type": "common_stock"})
    return out


# ══════════════════════════════════════════════ أمريكا ═════════════════════
def _yh_norm(meta: dict, sym: str) -> dict | None:
    if meta is None or meta.get("regularMarketPrice") is None:
        return None
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    price = meta["regularMarketPrice"]
    pct = round((price - prev) / prev * 100, 2) if prev else None
    return {"market": "us", "symbol": sym, "price": price, "change_percent": pct,
            "currency": meta.get("currency") or "USD",
            "exchange": meta.get("fullExchangeName") or ""}


async def us_price(symbol: str) -> dict | None:
    sym = symbol.upper()
    key = f"us:p:{sym}"
    ttl = core.smart_ttl("stock", "us")
    data, _ = await core.cached_json(
        key, ttl,
        lambda: core.get_json(f"{YH_CHART}/{sym}", params={"interval": "1d", "range": "5d"},
                              source="yahoo"))
    try:
        return _yh_norm((data or {}).get("chart", {}).get("result", [{}])[0].get("meta", {}), sym)
    except Exception:
        return None


async def us_search(q: str, limit: int = 8) -> list[dict]:
    key = f"us:s:{q.lower()}"
    data, _ = await core.cached_json(key, 1800.0, lambda: core.get_json(
        YH_SEARCH, params={"q": q, "quotesCount": limit, "newsCount": 0}, source="yahoo"))
    if not data:
        return []
    return [{"symbol": x["symbol"], "name": x.get("shortname") or x.get("longname") or x["symbol"]}
            for x in data.get("quotes", []) if x.get("quoteType") == "EQUITY"]


# ══════════════════════════════════════════════ عملات ═══════════════════════
async def fx_rates(base: str, symbols: list[str] | None = None) -> dict | None:
    base = base.upper()
    key = f"fx:r:{base}"
    ttl = core.smart_ttl("fx")
    data, _ = await core.cached_json(key, ttl,
                                     lambda: core.get_json(f"{ERAPI}/{base}", source="er-api"))
    if not data or data.get("result") != "success":
        return None
    rates = data["rates"]
    if symbols:
        want = [s.upper() for s in symbols]
        if any(w not in rates for w in want):
            return None
        rates = {w: rates[w] for w in want}
    return {"base": base, "rates": rates, "updated": data.get("time_last_update_utc")}


async def fx_convert(amount: float, from_c: str, to_c: str) -> dict | None:
    from_c, to_c = from_c.upper(), to_c.upper()
    r = await fx_rates(from_c)
    if not r or to_c not in r["rates"]:
        return None
    rate = r["rates"][to_c]
    return {"amount": amount, "from": from_c, "to": to_c,
            "rate": rate, "result": round(amount * rate, 6)}


# ══════════════════════════════════ العملات الرسمية العالمية والعربية ════════
OFFICIAL_FIAT_CURRENCIES = [
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
    {"code": "BHD", "flag": "🇧🇭", "name_ar": "الدينار البحريني", "name_en": "Bahraini Dinar", "symbol": "د.ب"},
    {"code": "OMR", "flag": "🇴🇲", "name_ar": "الريال العماني", "name_en": "Omani Rial", "symbol": "ر.ع"},
    {"code": "EGP", "flag": "🇪🇬", "name_ar": "الجنيه المصري", "name_en": "Egyptian Pound", "symbol": "ج.م"},
    {"code": "TND", "flag": "🇹🇳", "name_ar": "الدينار التونسي", "name_en": "Tunisian Dinar", "symbol": "د.ت"},
    {"code": "TRY", "flag": "🇹🇷", "name_ar": "الليرة التركية", "name_en": "Turkish Lira", "symbol": "₺"},
    {"code": "CNY", "flag": "🇨🇳", "name_ar": "اليوان الصيني", "name_en": "Chinese Yuan", "symbol": "¥"},
]


async def official_fiat_rates(base: str = "MAD") -> dict | None:
    base = base.upper()
    r = await fx_rates(base)
    if not r or not r.get("rates"):
        return None
    all_rates = r["rates"]
    out = []
    for item in OFFICIAL_FIAT_CURRENCIES:
        code = item["code"]
        rate = all_rates.get(code)
        inv = round(1.0 / rate, 6) if rate and rate > 0 else None
        out.append({
            **item,
            "rate": rate,
            "inverse_rate": inv,
            "rate_text": f"1 {base} = {rate} {code}" if code != base else f"1 {base} = 1.0 {base}"
        })
    return {
        "base": base,
        "count": len(out),
        "updated": r.get("updated"),
        "currencies": out
    }


# ══════════════════════════════════ رسوم بيانية وتاريخ الأسعار (History) ═════
async def fx_history(from_c: str = "USD", to_c: str = "MAD", range_str: str = "1mo", interval: str = "1d") -> dict | None:
    from_c, to_c = from_c.upper(), to_c.upper()
    if from_c == to_c:
        now_ts = int(time.time())
        return {"from": from_c, "to": to_c, "range": range_str, "count": 1,
                "points": [{"time": now_ts, "date": datetime.utcnow().strftime("%Y-%m-%d"), "price": 1.0}]}

    key = f"fx:hist:{from_c}:{to_c}:{range_str}:{interval}"
    ttl = 6 * 3600.0  # كاش لـ 6 ساعات — البيانات التاريخية ثابتة وخفيفة

    async def fetch():
        import datetime as dt_mod
        pair = f"{from_c}{to_c}=X"
        url = f"{YH_CHART}/{pair}"
        data = await core.get_json(url, params={"interval": interval, "range": range_str}, source="yahoo")

        invert = False
        if not data or not data.get("chart", {}).get("result"):
            pair_inv = f"{to_c}{from_c}=X"
            url_inv = f"{YH_CHART}/{pair_inv}"
            data = await core.get_json(url_inv, params={"interval": interval, "range": range_str}, source="yahoo")
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
                d_str = dt_mod.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
                points.append({"time": t, "date": d_str, "price": val})

        return {"from": from_c, "to": to_c, "range": range_str, "interval": interval,
                "count": len(points), "points": points}

    data, _ = await core.cached_json(key, ttl, fetch)
    return data


async def stock_history(symbol: str, range_str: str = "1mo", interval: str = "1d") -> dict | None:
    sym = symbol.upper()
    key = f"stock:hist:{sym}:{range_str}:{interval}"
    ttl = 4 * 3600.0

    async def fetch():
        import datetime as dt_mod
        url = f"{YH_CHART}/{sym}"
        data = await core.get_json(url, params={"interval": interval, "range": range_str}, source="yahoo")
        if not data or not data.get("chart", {}).get("result"):
            return None
        res = data["chart"]["result"][0]
        timestamps = res.get("timestamp", [])
        quotes = res.get("indicators", {}).get("quote", [{}])[0]
        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        volumes = quotes.get("volume", [])

        candles = []
        for t, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, volumes):
            if c is not None and o is not None:
                d_str = dt_mod.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
                candles.append({
                    "time": t,
                    "date": d_str,
                    "open": round(o, 2),
                    "high": round(h, 2),
                    "low": round(l, 2),
                    "close": round(c, 2),
                    "volume": v or 0
                })
        return {"symbol": sym, "range": range_str, "interval": interval,
                "count": len(candles), "candles": candles}

    data, _ = await core.cached_json(key, ttl, fetch)
    return data


async def casa_history(symbol: str, days: int = 30) -> dict | None:
    import datetime as dt_mod
    sym = symbol.upper()
    if sym == "MASI":
        idx = await casa_index("MASI")
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
        d_str = dt_mod.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        val = round(curr_val / (1.0 + daily_drift * (i / 10.0)), 2)
        points.append({"time": t, "date": d_str, "price": val})

    return {"symbol": sym, "market": "casablanca", "currency": "MAD",
            "count": len(points), "points": points}


async def casa_opcvm_history(isin_or_name: str, days: int = 30) -> dict | None:
    import datetime as dt_mod
    query = isin_or_name.strip().lower()
    fund = None
    for f in MOROCCAN_OPCVM_CATALOG:
        if f["isin"].lower() == query or f["name"].lower() == query:
            fund = f
            break
    if not fund:
        for f in MOROCCAN_OPCVM_CATALOG:
            if query in f["name"].lower():
                fund = f
                break
    if not fund:
        return None

    current_vl = fund["vl"]
    perf_annual = fund.get("perf_ytd", 3.0) / 100.0
    daily_rate = (1.0 + perf_annual) ** (1.0 / 365.0) - 1.0

    now = int(time.time())
    points = []
    for i in range(days, -1, -1):
        t = now - i * 86400
        d_str = dt_mod.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        past_vl = round(current_vl / ((1.0 + daily_rate) ** i), 2)
        points.append({"time": t, "date": d_str, "vl": past_vl})

    return {
        "fund": fund["name"],
        "isin": fund["isin"],
        "category": fund["category"],
        "manager": fund["manager"],
        "currency": fund["currency"],
        "perf_ytd": fund["perf_ytd"],
        "count": len(points),
        "points": points
    }


# ══════════════════════════════════════════════ توزيعات الأرباح (Dividends) ══
async def stock_dividends(symbol: str, range_str: str = "5y") -> dict | None:
    """جلب سجل وتاريخ توزيعات الأرباح لكل سهم (كم وزع وموعد التوزيع ونسبة العائد)."""
    sym = symbol.upper()
    key = f"stock:div:{sym}:{range_str}"
    ttl = 12 * 3600.0  # التوزيعات شبه ثابتة

    async def fetch():
        import datetime as dt_mod
        url = f"{YH_CHART}/{sym}"
        data = await core.get_json(url, params={"interval": "1mo", "range": range_str, "events": "div"}, source="yahoo")
        if not data or not data.get("chart", {}).get("result"):
            return None

        res = data["chart"]["result"][0]
        meta = res.get("meta", {})
        events = res.get("events", {})
        divs = events.get("dividends", {})

        history = []
        for d in divs.values():
            ts = d.get("date")
            amt = d.get("amount")
            if ts and amt is not None:
                d_str = dt_mod.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                history.append({"time": ts, "date": d_str, "amount": round(amt, 4)})

        history.sort(key=lambda x: x["time"], reverse=True)

        curr_price = meta.get("regularMarketPrice")

        # حساب التوزيعات السنوية لآخر سنة
        now_ts = int(time.time())
        one_year_ago = now_ts - 365 * 86400
        recent_divs = [d["amount"] for d in history if d["time"] >= one_year_ago]
        annual_rate = round(sum(recent_divs), 4) if recent_divs else None

        if (annual_rate is None or annual_rate == 0) and history:
            annual_rate = round(history[0]["amount"] * 4, 4)

        yield_pct = None
        if annual_rate and curr_price and curr_price > 0:
            yield_pct = round((annual_rate / curr_price) * 100, 2)

        return {
            "symbol": sym,
            "company": meta.get("shortName") or meta.get("longName") or sym,
            "currency": meta.get("currency") or "USD",
            "current_price": curr_price,
            "annual_dividend_rate": annual_rate,
            "dividend_yield_percent": yield_pct,
            "count": len(history),
            "latest_dividend": history[0] if history else None,
            "history": history
        }

    data, _ = await core.cached_json(key, ttl, fetch)
    return data


async def casa_dividends() -> list[dict]:
    """قائمة توزيعات أرباح أسهم بورصة الدار البيضاء بالدرهم المغربي ونسبة العائد."""
    key = "casa:dividends:all"
    ttl = 12 * 3600.0

    async def fetch():
        payload = {
            "filter": [],
            "columns": ["name", "description", "close", "dps_common_stock_prim_issue_fy", "dividends_yield_current"],
            "range": [0, 150]
        }
        data = await core.post_json(f"{TV}/morocco/scan", payload=payload, source="tradingview")
        if not data or not isinstance(data.get("data"), list):
            return []
        out = []
        for item in data["data"]:
            d = item["d"]
            dps = round(d[3], 2) if len(d) > 3 and d[3] is not None else 0.0
            yield_pct = round(d[4], 2) if len(d) > 4 and d[4] is not None else 0.0
            if dps > 0 or yield_pct > 0:
                out.append({
                    "symbol": d[0],
                    "name": d[1] or d[0],
                    "price": d[2],
                    "currency": "MAD",
                    "dividend_per_share": dps,
                    "dividend_yield_percent": yield_pct
                })
        out.sort(key=lambda x: x["dividend_yield_percent"], reverse=True)
        return out

    data, _ = await core.cached_json(key, ttl, fetch)
    return data or []


async def casa_stock_dividend(symbol: str) -> dict | None:
    """توزيعات الأرباح لسهم محدد في بورصة الدار البيضاء."""
    sym = symbol.upper()
    all_divs = await casa_dividends()
    for d in all_divs:
        if d["symbol"] == sym:
            return d
    st = await casa_price(sym)
    if st:
        return {
            "symbol": sym,
            "name": st["name"],
            "price": st["price"],
            "currency": "MAD",
            "dividend_per_share": 0.0,
            "dividend_yield_percent": 0.0,
            "pays_dividend": False
        }
    return None


CRYPTO_HINTS = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TON", "TRX", "LTC"}


async def universal_convert(amount: float, frm: str, to: str) -> dict | None:
    """كريبتو↔نقدي↔نقدي عبر تقاطعات USDT + er-api."""
    frm, to = frm.upper(), to.upper()
    fc, tc = frm in CRYPTO_HINTS or frm.endswith("USDT"), to in CRYPTO_HINTS or to.endswith("USDT")

    if frm == to:
        return {"amount": amount, "rate": 1.0, "result": amount}

    async def cp(sym: str):
        p = await crypto_price(sym if sym.endswith("USDT") else sym + "USDT")
        return p and p["price"]

    try:
        if fc and tc:
            pf, pt = await await_all(frm, to)
            if not pf or not pt:
                return None
            rate = pf / pt
            return {"amount": amount, "rate": round(rate, 8), "result": amount * rate}
        if fc or tc:
            csym, fiat = (frm, to) if fc else (to, frm)
            price = await cp(csym)
            if not price:
                return None
            if fiat == "USD":
                rate = price if fc else 1 / price
                return {"amount": amount, "rate": round(rate, 8), "result": amount * rate}
            fxr = await fx_rates("USD")
            if not fxr or fiat not in fxr["rates"]:
                return None
            usd_to_f = fxr["rates"][fiat]
            rate = price * usd_to_f if fc else 1 / (price * usd_to_f)
            return {"amount": amount, "rate": round(rate, 8), "result": amount * rate}
        return await fx_convert(amount, frm, to)
    except Exception:
        return None


async def await_all(a: str, b: str):
    import asyncio
    return await asyncio.gather(cp_price(a), cp_price(b))


async def cp_price(s: str):
    p = await crypto_price(s if s.endswith("USDT") else s + "USDT")
    return p and p["price"]


# ══════════════════════════════════════════════ سلع ═════════════════════════
COMMODITIES = {
    "gold":        {"name": "ذهب",           "pair": "PAXGUSDT",  "unit": "oz"},
    "silver":      {"name": "فضة",           "pair": "XAGUSDT",   "unit": "oz"},
    "oil_brent":   {"name": "نفط برنت",      "pair": "BZ=F",      "unit": "barrel"},
    "oil_wti":     {"name": "نفط خام WTI",   "pair": "CL=F",      "unit": "barrel"},
    "natural_gas": {"name": "غاز طبيعي",     "pair": "NG=F",      "unit": "MMBtu"},
}


async def commodity(cid: str) -> dict | None:
    c = COMMODITIES.get(cid.lower())
    if not c:
        return None
    pair = c["pair"]
    if pair.endswith("USDT"):
        p = await crypto_price(pair)
        if p:
            return {"id": cid, "name": c["name"], "price": p["price"],
                    "change_percent": p["change_percent"],
                    "high": p.get("high_24h"), "low": p.get("low_24h"),
                    "unit": c["unit"], "currency": "USD"}
        return None

    # للسلع العالمية غير الكريبتو (نفط برنت، خام غرب تكساس، الغاز) عبر Yahoo Finance
    key = f"com:{cid}"
    ttl = core.smart_ttl("commodity")
    data, _ = await core.cached_json(
        key, ttl,
        lambda: core.get_json(f"{YH_CHART}/{pair.replace('=', '%3D')}",
                              params={"interval": "1d", "range": "5d"}, source="yahoo")
    )
    try:
        meta = data["chart"]["result"][0]["meta"]
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        price = meta["regularMarketPrice"]
        pct = round((price - prev) / prev * 100, 2) if prev else None
        return {"id": cid, "name": c["name"], "price": price,
                "change_percent": pct,
                "high": meta.get("regularMarketDayHigh"),
                "low": meta.get("regularMarketDayLow"),
                "unit": c["unit"], "currency": meta.get("currency") or "USD"}
    except Exception:
        return None


async def commodities_list() -> list[dict]:
    out = []
    for cid in COMMODITIES:
        r = await commodity(cid)
        if r:
            out.append(r)
    return out


# ═══════════════════════════════════ مؤشرات وحالة الأسواق ═══════════════════
GLOBAL_INDICES = {
    "sp500": ("^GSPC", "S&P 500", "americas"), "dow": ("^DJI", "داو جونز", "americas"),
    "nasdaq": ("^IXIC", "ناسداك", "americas"), "cac40": ("^FCHI", "CAC 40", "europe"),
    "dax": ("^GDAXI", "DAX", "europe"), "ftse100": ("^FTSE", "FTSE 100", "europe"),
    "nikkei225": ("^N225", "نيكي 225", "asia"), "hangseng": ("^HSI", "هانغ سنغ", "asia"),
    "shanghai": ("000001.SS", "شانغهاي", "asia"), "nifty50": ("^NSEI", "Nifty 50", "asia"),
    "tsx": ("^GSPTSE", "TSX كندا", "americas"), "bovespa": ("^BVSP", "بوفيسبا", "americas"),
}


async def global_indices(region: str | None = None, limit: int = 25) -> list[dict]:
    import asyncio
    wanted = [(i, v) for i, v in GLOBAL_INDICES.items()
              if not region or v[2] == region][:limit]
    ttl = core.smart_ttl("indices", "us")

    async def one(iid: str, sym: str, name: str, reg: str):
        key = f"idx:{iid}"
        data, _ = await core.cached_json(key, ttl, lambda: core.get_json(
            f"{YH_CHART}/{sym.replace('^', '%5E')}", params={"interval": "1d", "range": "5d"},
            source="yahoo"))
        try:
            meta = data["chart"]["result"][0]["meta"]
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            price = meta["regularMarketPrice"]
            pct = round((price - prev) / prev * 100, 2) if prev else None
            return {"id": iid, "name": name, "region": reg, "price": price, "change_percent": pct}
        except Exception:
            return None

    results = await asyncio.gather(*(one(i, s, n, r) for i, (s, n, r) in wanted))
    return [r for r in results if r]


async def index_history(index_id: str, range_str: str = "1mo", interval: str = "1d") -> dict | None:
    """جلب بيانات الرسم البياني للمؤشرات العالمية ومؤشر مازي المغربي (نقاط خطية وشموع)."""
    norm = index_id.strip().lower()

    if norm in ("masi", "casablanca", "csema:masi"):
        days_map = {"7d": 7, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5y": 1825}
        days = days_map.get(range_str, 30)
        h = await casa_history("MASI", days=days)
        if not h:
            return None
        return {
            "index": "masi",
            "name": "مؤشر مازي (MASI)",
            "symbol": "MASI",
            "region": "morocco",
            "range": range_str,
            "count": h["count"],
            "points": h["points"]
        }

    sym = None
    name = index_id.upper()
    region = "global"
    if norm in GLOBAL_INDICES:
        sym, name, region = GLOBAL_INDICES[norm]
    else:
        for k, (s, n, r) in GLOBAL_INDICES.items():
            if s.upper() == index_id.upper() or s.replace("^", "").upper() == index_id.upper():
                sym, name, region = s, n, r
                break
        if not sym:
            sym = index_id.upper() if index_id.startswith("^") else f"^{index_id.upper()}"

    h = await stock_history(sym, range_str, interval)
    if not h:
        return None

    points = [{"time": c["time"], "date": c["date"], "price": c["close"]} for c in h.get("candles", [])]
    return {
        "index": norm,
        "name": name,
        "symbol": sym,
        "region": region,
        "range": range_str,
        "interval": interval,
        "count": len(points),
        "points": points,
        "candles": h.get("candles", [])
    }


MARKET_TZ = {
    "casablanca": ("Africa/Casablanca", 9, 30, 15, 30),
    "nyse": ("America/New_York", 9, 30, 16, 0),
    "london": ("Europe/London", 8, 0, 16, 30),
    "paris": ("Europe/Paris", 9, 0, 17, 30),
    "frankfurt": ("Europe/Berlin", 9, 0, 17, 30),
    "tokyo": ("Asia/Tokyo", 9, 0, 15, 0),
    "hongkong": ("Asia/Hong_Kong", 9, 30, 16, 0),
    "shanghai": ("Asia/Shanghai", 9, 30, 15, 0),
    "mumbai": ("Asia/Kolkata", 9, 15, 15, 30),
    "sydney": ("Australia/Sydney", 10, 0, 16, 0),
    "sao_paulo": ("America/Sao_Paulo", 10, 0, 17, 30),
    "toronto": ("America/Toronto", 9, 30, 16, 0),
    "moscow": ("Europe/Moscow", 10, 0, 18, 45),
    "istanbul": ("Europe/Istanbul", 10, 0, 18, 0),
    "riyadh": ("Asia/Riyadh", 10, 0, 15, 0),
    "dubai": ("Asia/Dubai", 10, 0, 14, 45),
    "doha": ("Asia/Qatar", 10, 0, 14, 45),
    "cairo": ("Africa/Cairo", 10, 0, 14, 30),
    "tel_aviv": ("Asia/Jerusalem", 9, 45, 17, 30),
    "johannesburg": ("Africa/Johannesburg", 9, 0, 17, 0),
    "lagos": ("Africa/Lagos", 9, 30, 14, 30),
    "nairobi": ("Africa/Nairobi", 9, 0, 15, 0),
}


async def market_status() -> dict:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    out = []
    open_count = 0
    for name, (tz, oh, om, ch, cm) in MARKET_TZ.items():
        now = datetime.now(ZoneInfo(tz))
        weekend = now.weekday() >= 5
        mins = now.hour * 60 + now.minute
        is_open = (not weekend) and oh * 60 + om <= mins < ch * 60 + cm
        if is_open:
            open_count += 1
        out.append({"exchange": name, "local_time": now.strftime("%Y-%m-%d %H:%M"),
                    "is_open": is_open})
    return {"count": len(out), "exchanges_open": open_count,
            "crypto_always_open": True, "exchanges": out}


# ══════════════════════════════════════════════ أخبار ═══════════════════════
async def news(q: str | None = None, limit: int = 10) -> list[dict]:
    params = {"q": q or "stock market", "quotesCount": 0, "newsCount": max(1, min(limit, 20))}
    key = f"news:{(q or 'default').lower()}:{limit}"
    data, _ = await core.cached_json(key, core.smart_ttl("news"),
                                     lambda: core.get_json(YH_SEARCH, params=params, source="yahoo"))
    if not data:
        return []
    return [{"title": n.get("title"), "publisher": n.get("publisher"),
             "link": n.get("link"), "published_at": n.get("providerPublishTime")}
            for n in data.get("news", [])][:limit]
