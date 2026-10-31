"""
MARKETS API v3 — النسخة النظيفة الموحّدة
═══════════════════════════════════════
كريبتو · الدار البيضاء · 61 بورصة عالمية · عملات وتحويل شامل ·
سلع · مؤشرات عالمية · حالة الأسواق · أخبار · حسابات ومتابعة وتنبيهات.

الجديد عن v2: كاش ذكي واعٍ بساعات التداول + عدّاد نداءات المصادر + بنية نظيفة.

التشغيل:
    pip install -r requirements.txt
    python main.py            → http://0.0.0.0:8000  (التوثيق /docs)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager  # noqa: E402
from typing import Any  # noqa: E402

from fastapi import Depends, FastAPI, Header, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

import core  # noqa: E402
import markets as M  # noqa: E402
import store  # noqa: E402


@asynccontextmanager
async def lifespan(_app):
    await core.startup()
    store.init_db()
    yield
    await core.shutdown()


app = FastAPI(
    title="URANUS Markets API",
    version="3.0.0",
    description="API موحّد لكل الأسواق — كاش ذكي يخدم عشرات آلاف المستخدمين بنداءات قليلة.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


def auth(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "مطلوب توكن Bearer")
    payload = store.verify_token(authorization[7:])
    if not payload:
        raise HTTPException(401, "توكن غير صالح أو منتهي")
    return payload


@app.get("/")
async def root():
    return {"name": "URANUS Markets API", "version": "3.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0",
            "cache_entries": len(core.CACHE._data)}


# ══════════════════════════════════════════ كريبتو ══════════════════════════
@app.get("/crypto/price/{pair}")
async def crypto_price(pair: str):
    r = await M.crypto_price(pair)
    return r or JSONResponse({"detail": f"{pair.upper()} غير موجود"}, status_code=404)


@app.post("/crypto/prices")
async def crypto_prices(pairs: list[str]):
    return {"count": len(pairs[:30]), "results": await M.crypto_prices(pairs)}


@app.get("/crypto/history/{pair}")
async def crypto_history(pair: str, interval: str = Query("1d"), limit: int = Query(48, le=1000)):
    candles = await M.crypto_history(pair, interval, limit)
    if candles is None:
        raise HTTPException(400, "رمز أو فترة غير صحيحة")
    return {"symbol": pair.upper(), "interval": interval, "candles": candles}


@app.get("/crypto/search")
async def crypto_search(q: str = Query(min_length=1)):
    return {"query": q, "results": await M.crypto_search(q)}


# ════════════════════════════════════════════ كازا ══════════════════════════
@app.get("/casablanca/stocks")
async def casa_stocks():
    stocks = await M.casa_snapshot()
    return {"market": "casablanca", "currency": "MAD", "count": len(stocks), "stocks": stocks}


@app.get("/casablanca/price/{symbol}")
async def casa_price(symbol: str):
    r = await M.casa_price(symbol)
    return r or JSONResponse({"detail": f"{symbol.upper()} غير موجود"}, status_code=404)


@app.get("/casablanca/index/{name}")
async def casa_index(name: str = "MASI"):
    r = await M.casa_index(name)
    return r or JSONResponse({"detail": f"مؤشر {name.upper()} غير متاح"}, status_code=404)


@app.get("/casablanca/opcvm")
async def casa_opcvm(category: str | None = None, q: str | None = None):
    return await M.casa_opcvm(category, q)


@app.get("/casablanca/history/{symbol}")
async def casa_history_endpoint(symbol: str, days: int = Query(30, le=365)):
    r = await M.casa_history(symbol, days)
    return r or JSONResponse({"detail": f"{symbol.upper()} غير متاح"}, status_code=404)


@app.get("/casablanca/opcvm/history/{isin_or_name}")
async def casa_opcvm_history_endpoint(isin_or_name: str, days: int = Query(30, le=365)):
    r = await M.casa_opcvm_history(isin_or_name, days)
    return r or JSONResponse({"detail": f"صندوق {isin_or_name} غير موجود"}, status_code=404)


@app.get("/casablanca/dividends")
async def casa_dividends_endpoint():
    divs = await M.casa_dividends()
    return {"market": "casablanca", "currency": "MAD", "count": len(divs), "dividends": divs}


@app.get("/casablanca/dividends/{symbol}")
async def casa_stock_dividend_endpoint(symbol: str):
    r = await M.casa_stock_dividend(symbol)
    return r or JSONResponse({"detail": f"سهم {symbol.upper()} غير موجود"}, status_code=404)



# ══════════════════════════════════ أسهم عالمية (61) ════════════════════════
@app.get("/exchanges")
async def exchanges_list():
    return {"count": len(await M.exchanges()), "exchanges": await M.exchanges()}


@app.get("/exchange/{slug}/stocks")
async def exchange_stocks(slug: str,
                          limit: int = Query(50, le=500), offset: int = Query(0, ge=0),
                          q: str | None = None, type: str | None = Query(None),
                          sort_by: str | None = None, order: str = "desc"):
    stocks = await M.exchange_stocks(slug, limit, offset, q, type, sort_by, order)
    if not stocks and slug.lower() not in {e["slug"] for e in await M.exchanges()}:
        raise HTTPException(404, f"بورصة '{slug}' غير مدعومة")
    return {"exchange": slug, "count": len(stocks), "stocks": stocks}


# ══════════════════════════════════ الأسهم النقية فقط (بدون ETFs) ════════════
@app.get("/stocks/pure/{slug}")
async def pure_stocks_endpoint(slug: str,
                               limit: int = Query(50, le=300), offset: int = Query(0, ge=0),
                               q: str | None = None, sort_by: str | None = "market_cap",
                               order: str = "desc"):
    stocks = await M.pure_stocks(slug, limit, offset, q, sort_by, order)
    if not stocks and slug.lower() not in {e["slug"] for e in await M.exchanges()} and slug.lower() != "casablanca":
        raise HTTPException(404, f"بورصة '{slug}' غير مدعومة")
    return {
        "section": "pure_stocks",
        "exchange": slug,
        "count": len(stocks),
        "filter_applied": "common_stocks_only (no ETFs / Funds)",
        "stocks": stocks
    }


# ══════════════════════════════════════════ أمريكا ══════════════════════════
@app.get("/us/price/{symbol}")
async def us_price(symbol: str):
    r = await M.us_price(symbol)
    return r or JSONResponse({"detail": f"{symbol.upper()} غير موجود"}, status_code=404)


@app.post("/us/prices")
async def us_prices(symbols: list[str]):
    import asyncio
    results = await asyncio.gather(*(M.us_price(s) for s in symbols[:25]))
    out = [r if r else {"symbol": s.upper(), "error": "not_found"}
           for s, r in zip(symbols, results)]
    return {"count": len(out), "results": out}


@app.get("/us/search")
async def us_search(q: str = Query(min_length=1)):
    return {"query": q, "results": await M.us_search(q)}


@app.get("/stocks/history/{symbol}")
async def stock_history_endpoint(symbol: str,
                                 range: str = Query("1mo", pattern="^(7d|1mo|3mo|6mo|1y|5y)$"),
                                 interval: str = Query("1d", pattern="^(1d|1wk|1mo)$")):
    r = await M.stock_history(symbol, range, interval)
    return r or JSONResponse({"detail": f"تعذر جلب تاريخ السهم {symbol.upper()}"}, status_code=404)


@app.get("/stocks/dividends/{symbol}")
async def stock_dividends_endpoint(symbol: str,
                                    range: str = Query("5y", pattern="^(1y|2y|5y|10y|max)$")):
    r = await M.stock_dividends(symbol, range)
    return r or JSONResponse({"detail": f"تعذر جلب سجل توزيعات السهم {symbol.upper()}"}, status_code=404)



# ══════════════════════════════════════════ العملات ═════════════════════════
@app.get("/fx/rates/{base}")
async def fx_rates(base: str, symbols: str | None = None):
    syms = [s.strip() for s in symbols.split(",")] if symbols else None
    r = await M.fx_rates(base, syms)
    return r or JSONResponse({"detail": "عملة غير مدعومة"}, status_code=404)


@app.get("/fx/convert")
async def fx_convert(amount: float = Query(gt=0), from_: str = Query(alias="from"),
                     to: str = Query()):
    r = await M.universal_convert(amount, from_, to)
    return r or JSONResponse({"detail": "تعذر التحويل"}, status_code=404)


# ══════════════════════════════════ العملات الرسمية فقط (بدون كريبتو) ════════
@app.get("/fx/official")
async def official_fx_rates(base: str = Query("MAD")):
    r = await M.official_fiat_rates(base)
    return r or JSONResponse({"detail": "تعذر جلب العملات الرسمية"}, status_code=404)


@app.get("/fx/official/convert")
async def official_fx_convert(amount: float = Query(gt=0),
                              from_: str = Query(alias="from"),
                              to: str = Query()):
    supported_codes = {item["code"] for item in M.OFFICIAL_FIAT_CURRENCIES}
    f_up, t_up = from_.upper(), to.upper()
    if f_up not in supported_codes or t_up not in supported_codes:
        raise HTTPException(400, f"هذا المسار مخصص للعملات الرسمية فقط. العملات المدعومة: {', '.join(sorted(supported_codes))}")
    r = await M.fx_convert(amount, f_up, t_up)
    return r or JSONResponse({"detail": "تعذر التحويل بين العملات الرسمية المحددة"}, status_code=404)


@app.get("/fx/history")
async def fx_history_endpoint(from_: str = Query("USD", alias="from"),
                              to: str = Query("MAD"),
                              range: str = Query("1mo", regex="^(7d|1mo|3mo|6mo|1y|5y)$"),
                              interval: str = Query("1d", regex="^(1d|1wk|1mo)$")):
    r = await M.fx_history(from_, to, range, interval)
    return r or JSONResponse({"detail": f"تعذر جلب تاريخ الصرف بين {from_.upper()} و {to.upper()}"}, status_code=404)


# ═══════════════════════════════════════════ السلع ══════════════════════════
@app.get("/commodities")
async def commodities():
    items = await M.commodities_list()
    return {"count": len(items), "commodities": items}


@app.get("/commodities/{cid}")
async def commodity(cid: str):
    r = await M.commodity(cid)
    return r or JSONResponse({"detail": "سلعة غير معروفة"}, status_code=404)


# ═══════════════════════════════ مؤشرات وحالة الأسواق ═══════════════════════
@app.get("/global/indices")
async def global_indices(region: str | None = None, limit: int = Query(25, le=30)):
    items = await M.global_indices(region, limit)
    return {"region": region or "all", "count": len(items), "indices": items}


@app.get("/indices/history/{index_id}")
async def index_history_endpoint(index_id: str,
                                 range: str = Query("1mo", pattern="^(7d|1mo|3mo|6mo|1y|5y)$"),
                                 interval: str = Query("1d", pattern="^(1d|1wk|1mo)$")):
    r = await M.index_history(index_id, range, interval)
    return r or JSONResponse({"detail": f"تعذر جلب تاريخ المؤشر {index_id}"}, status_code=404)



@app.get("/markets/status")
async def market_status():
    return await M.market_status()


# ══════════════════════════════════════════ الأخبار ═════════════════════════
@app.get("/news")
async def news(q: str | None = None, limit: int = Query(10, le=20)):
    return {"query": q, "results": await M.news(q, limit)}


# ═══════════════════════════ الحسابات والمتابعة والتنبيهات ═══════════════════
@app.post("/auth/register")
async def register(body: dict[str, Any]):
    result = store.register(str(body.get("username", "")).strip(),
                            str(body.get("password", "")))
    if isinstance(result, str):
        raise HTTPException(400, result)
    return result


@app.post("/auth/login")
async def login(body: dict[str, Any]):
    result = store.login(str(body.get("username", "")).strip(),
                         str(body.get("password", "")))
    if isinstance(result, str):
        raise HTTPException(401, result)
    return result


@app.get("/watchlist")
async def watchlist(user: dict = Depends(auth)):
    return {"user": user["u"], "items": store.wl_list(user["uid"])}


@app.post("/watchlist/items")
async def wl_add(body: dict[str, Any], user: dict = Depends(auth)):
    market = str(body.get("market", "")).strip().lower()
    symbol = str(body.get("symbol", "")).strip().upper()
    if not market or not symbol:
        raise HTTPException(422, "market و symbol مطلوبة")
    return store.wl_add(user["uid"], market, symbol)


@app.delete("/watchlist/items/{item_id}")
async def wl_remove(item_id: int, user: dict = Depends(auth)):
    return store.wl_remove(user["uid"], item_id)


@app.get("/watchlist/prices")
async def watchlist_prices(user: dict = Depends(auth)):
    """أسعار قائمة المتابعة كاملة في نداء واحد — مجمّعة حسب السوق."""
    import asyncio
    items = store.wl_list(user["uid"])
    by_market: dict[str, list[str]] = {}
    for it in items:
        by_market.setdefault(it["market"], []).append(it["symbol"])

    async def crypto_batch():
        r = {}
        for p in by_market.get("crypto", []):
            pr = await M.crypto_price(p)
            if pr:
                r[p] = pr
        return r

    async def casa_batch():
        snap = {s["symbol"]: s for s in await M.casa_snapshot()}
        return {sym: snap[sym] for sym in by_market.get("casablanca", []) if sym in snap}

    async def us_batch():
        r = {}
        for s in by_market.get("us", []):
            pr = await M.us_price(s)
            if pr:
                r[s] = pr
        return r

    results = {}
    tasks = []
    if "crypto" in by_market:
        tasks.append(crypto_batch())
    if "casablanca" in by_market:
        tasks.append(casa_batch())
    if "us" in by_market:
        tasks.append(us_batch())
    for group in await asyncio.gather(*tasks):
        results.update(group)

    priced = []
    for it in items:
        data = results.get(it["symbol"])
        row = {**it, "price": data["price"] if data else None,
               "change_percent": (data or {}).get("change_percent")}
        priced.append(row)

    return {"user": user["u"], "count": len(priced), "results": priced}


@app.post("/alerts")
async def alert_add(body: dict[str, Any], user: dict = Depends(auth)):
    direction = str(body.get("direction", "above")).lower()
    if direction not in ("above", "below"):
        raise HTTPException(422, "direction يجب أن تكون above أو below")
    target = body.get("target_price")
    if not isinstance(target, (int, float)) or target <= 0:
        raise HTTPException(422, "target_price مطلوب ويجب أن يكون رقماً موجباً")
    market = str(body.get("market", "")).lower()
    symbol = str(body.get("symbol", "")).upper()
    current = None
    if market == "crypto":
        p = await M.crypto_price(symbol)
        current = p and p["price"]
    elif market == "casablanca":
        p = await M.casa_price(symbol)
        current = p and p["price"]
    elif market == "us":
        p = await M.us_price(symbol)
        current = p and p["price"]
    result = store.alert_add(user["uid"], market, symbol, direction, float(target))
    result["current_price"] = current
    return result


@app.delete("/alerts/{alert_id}")
async def alert_remove(alert_id: int, user: dict = Depends(auth)):
    return store.alert_remove(user["uid"], alert_id)


@app.get("/alerts")
async def alerts_list(user: dict = Depends(auth)):
    return {"user": user["u"], "alerts": store.alerts_list(user["uid"])}


# ═══════════════════════════════════════ مراقبة المصادر ═════════════════════
@app.get("/admin/stats")
async def admin_stats():
    """عدّاد النداءات على المصادر الخارجية — لتراقب أنك بعيد عن حدود الحظر."""
    return {**core.source_stats(), "cache_entries": len(core.CACHE._data)}


if __name__ == "__main__":
    import uvicorn
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   URANUS MARKETS API v3 — يعمل الآن   ║")
    print("  ║   http://localhost:8000  (/docs)      ║")
    print("  ╚══════════════════════════════════════╝\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
