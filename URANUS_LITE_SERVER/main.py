"""
URANUS MARKETS LITE API — النسخة السريعة والمخففة
══════════════════════════════════════════════════
المحتويات الحصرية:
1. أهم 50 عملة مشفرة (Top 50 Crypto) + الشموع التاريخية
2. البورصات المنتقاة (10 بورصات) + أسعار ومؤشرات كل بورصة + تاريخها
3. أهم العملات العالمية والدرهم المغربي + شارت تاريخ العملات
4. الذهب والفضة (بالأونصة والجرام بالدولار والدرهم) + شارت تاريخ الذهب والفضة
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import core
import markets as M


class PortfolioItem(BaseModel):
    type: Literal["currency", "metal", "crypto", "casablanca", "stock"]
    symbol: str = Field(..., min_length=1, description="رمز الأصل مثل EUR أو GOLD أو BTC أو IAM أو AAPL")
    amount: float = Field(..., ge=0, description="الكمية أو الوزن أو عدد الأسهم")
    unit: Literal["gram", "ounce"] | None = Field("gram", description="للمعادن: gram أو ounce")
    karat: Literal["24k", "21k", "18k", "pure_999"] | None = Field(None, description="للمعادن: 24k, 21k, 18k, pure_999")
    label: str | None = Field(None, description="اسم مخصص اختياري للمحفظة")


class PortfolioRequest(BaseModel):
    target_currency: str = Field("MAD", min_length=3, max_length=5)
    items: list[PortfolioItem] = Field(default_factory=list, max_length=100)


@asynccontextmanager
async def lifespan(_app):
    await core.startup()
    yield
    await core.shutdown()


app = FastAPI(
    title="URANUS Markets LITE API",
    version="1.2.0",
    description="سيرفر لايت متكامل وسريع لتطبيقات تتبع النفقات والمحافظ والأسواق المالية.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "URANUS Markets LITE API",
        "version": "1.2.0",
        "type": "Lite Edition for Expense Tracking, Sync & Live Markets",
        "docs": "/docs",
        "sections": {
            "search": ["/search?q={query}", "/crypto/search?q={query}", "/casablanca/search?q={query}", "/stocks/search?q={query}"],
            "crypto": ["/crypto/top50", "/crypto/price/{symbol}", "/crypto/history/{symbol}"],
            "exchanges": ["/exchanges", "/exchange/{slug}/stocks", "/casablanca/stocks", "/casablanca/price/{symbol}", "/casablanca/history/{symbol}"],
            "indices": ["/indices", "/indices/history/{slug}"],
            "stocks": ["/stocks/price/{symbol}", "/stocks/history/{symbol}"],
            "forex": ["/fx/rates?base=MAD", "/fx/rates/{base}", "/fx/convert?from=USD&to=MAD&amount=1", "/fx/history?from=USD&to=MAD", "/fx/rate-on-date?from=USD&to=MAD&date=YYYY-MM-DD&amount=1"],
            "metals": ["/metals?currency=MAD", "/metals/gold?currency=MAD", "/metals/silver?currency=MAD", "/metals/history/{metal}"],
            "expense_tracker": ["/sync/rates?base=MAD", "POST /portfolio/value"]
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok", "edition": "lite", "cache_entries": len(core.CACHE._data)}


# ══════════════════════════════════════════════ 1. الكريبتو (Top 50) ═════════
@app.get("/crypto/top50")
async def crypto_top50():
    """أهم 50 عملة كريبتو بالترتيب والأسعار والتغيرات اللحظية بطلب واحد."""
    data = await M.crypto_top50()
    return {"market": "crypto", "count": len(data), "coins": data}


@app.get("/crypto/price/{pair}")
async def crypto_price(pair: str):
    """سعر عملة معينة (مثال: BTC, ETH, SOL, DOGE)."""
    p = await M.crypto_price(pair)
    if not p:
        raise HTTPException(404, f"{pair.upper()} غير موجود")
    return p


@app.get("/crypto/history/{pair}")
async def crypto_history(pair: str, interval: str = Query("1d"), limit: int = Query(30, le=500)):
    """شارت وشموع تاريخية لأي عملة من الـ 50 (للرسوم البيانية)."""
    candles = await M.crypto_history(pair, interval, limit)
    if not candles:
        raise HTTPException(400, "رمز أو فترة غير صحيحة")
    return {"symbol": pair.upper(), "interval": interval, "count": len(candles), "candles": candles}


# ══════════════════════════════════════════════ 2. البورصات المنتقاة ════════
@app.get("/exchanges")
async def lite_exchanges():
    """البورصات المنتقاة الـ 10 الكبرى مع حالتها الحية (مفتوحة / مغلقة)."""
    ex_list = []
    for slug, info in M.LITE_EXCHANGES.items():
        ex_list.append({
            "slug": slug,
            "name": info["name"],
            "country": info["country"],
            "flag": info["flag"],
            "currency": info["currency"],
            "state": core.market_state(slug),
        })
    return {"count": len(ex_list), "exchanges": ex_list}


@app.get("/exchange/{slug}/stocks")
async def exchange_stocks(slug: str, limit: int = Query(50, le=100)):
    """أسهم بورصة معينة من البورصات الـ 10 (america, canada, france, germany, uk, morocco...)."""
    slug = slug.lower()
    if slug not in M.LITE_EXCHANGES:
        raise HTTPException(404, f"البورصة {slug} غير مدرجة في النسخة المخففة. المتاحة: {list(M.LITE_EXCHANGES.keys())}")
    stocks = await M.get_exchange_stocks(slug, limit=limit)
    return {"exchange": slug, "count": len(stocks), "stocks": stocks}


# ══════════════════════════════════════════════ 3. بورصة الدار البيضاء وتاريخها ══
@app.get("/casablanca/stocks")
async def casa_stocks():
    """جميع أسهم بورصة الدار البيضاء المغربية (74 سهماً بالدرهم)."""
    stocks = await M.casa_stocks()
    return {"market": "casablanca", "currency": "MAD", "count": len(stocks), "stocks": stocks}


@app.get("/casablanca/price/{symbol}")
async def casa_price(symbol: str):
    """سعر سهم مغربي محدد بالدرهم (مثال: ATW, IAM, ADH, AKT)."""
    p = await M.casa_price(symbol)
    if not p:
        raise HTTPException(404, f"السهم المغربي {symbol.upper()} غير موجود")
    return p


@app.get("/casablanca/history/{symbol}")
async def casa_history(symbol: str, days: int = Query(30, le=180)):
    """شارت وتاريخ أي سهم مغربي (أو مؤشر MASI) بالنقاط اليومية للرسم البياني."""
    hist = await M.casa_stock_history(symbol, days=days)
    if not hist:
        raise HTTPException(404, f"بيانات التاريخ غير متوفرة لـ {symbol.upper()}")
    return hist


# ══════════════════════════════════════════════ 4. المؤشرات الكبرى وتاريخها ═══
@app.get("/indices")
async def lite_indices():
    """مؤشرات البورصات الـ 10 الكبرى (MASI, S&P 500, Dow, Nasdaq, CAC 40, DAX, FTSE, TSX...)."""
    data = await M.get_indices_list()
    return {"count": len(data), "indices": data}


@app.get("/indices/history/{slug}")
async def index_history(slug: str, range: str = Query("1mo"), interval: str = Query("1d")):
    """شارت وتاريخ أي مؤشر بورصة (مثال: sp500, masi, cac40, dax, ftse100, tsx)."""
    hist = await M.get_index_history(slug, range_=range, interval=interval)
    if not hist:
        raise HTTPException(404, f"المؤشر {slug} غير موجود. المتاح: {list(M.LITE_INDICES.keys())}")
    return hist


# ══════════════════════════════════════════════ 5. الأسهم وتاريخ الشموع ══════
@app.get("/stocks/price/{symbol}")
async def stock_price(symbol: str):
    """السعر اللحظي لأي سهم أمريكي أو كندي أو أوروبي (مثل AAPL, TSLA, MC.PA)."""
    q = await M.stock_price(symbol)
    if not q:
        raise HTTPException(404, f"السهم {symbol.upper()} غير موجود أو تعذر جلب سعره")
    return q


@app.get("/stocks/history/{symbol}")
async def stock_history(symbol: str, range: str = Query("1mo"), interval: str = Query("1d")):
    """بيانات الشموع التاريخية لأي سهم أمريكي أو كندي أو أوروبي (للرسوم البيانية)."""
    hist = await M.stock_history(symbol, range_=range, interval=interval)
    if not hist:
        raise HTTPException(404, f"بيانات التاريخ غير متوفرة لـ {symbol.upper()}")
    return hist


# ══════════════════════════════════════════════ 6. أهم العملات وشارت الصرف ════
@app.get("/fx/rates")
async def fx_rates(base: str = Query("MAD", description="العملة الأساسية مثل MAD أو EUR أو USD")):
    """أسعار أهم 11 عملة عالمية مقابل العملة الأساسية المختارة (افتراضيًا MAD)."""
    res = await M.fx_rates(base)
    if not res:
        raise HTTPException(400, f"عملة الأساس غير مدعومة: {base.upper()}")
    return res


@app.get("/fx/rates/{base}")
async def fx_rates_by_base(base: str):
    """أسعار أهم 11 عملة مقابل عملة أساس محددة في المسار (مثال: /fx/rates/EUR)."""
    res = await M.fx_rates(base)
    if not res:
        raise HTTPException(400, f"عملة الأساس غير مدعومة: {base.upper()}")
    return res


@app.get("/fx/convert")
async def fx_convert(
    from_curr: str | None = Query(None, alias="from", description="العملة المصدر مثل USD"),
    to_curr: str | None = Query(None, alias="to", description="العملة الهدف مثل MAD"),
    from_c: str | None = Query(None, description="بديل متوافق لـ from"),
    to_c: str | None = Query(None, description="بديل متوافق لـ to"),
    amount: float = Query(1.0),
):
    """تحويل فوري بين العملات (يدعم ?from=EUR&to=MAD وكذلك ?from_c=EUR&to_c=MAD)."""
    src = from_curr or from_c or "USD"
    dst = to_curr or to_c or "MAD"
    res = await M.fx_convert(src, dst, amount)
    if not res:
        raise HTTPException(400, "عملة غير مدعومة في النسخة المخففة")
    return res


@app.get("/fx/history")
async def fx_history(
    from_curr: str | None = Query(None, alias="from"),
    to_curr: str | None = Query(None, alias="to"),
    from_c: str | None = Query(None),
    to_c: str | None = Query(None),
    range: str = Query("1mo"),
    interval: str = Query("1d"),
):
    """شارت لتغييرات سعر صرف أي عملتين عبر الزمان (يدعم from/to و from_c/to_c)."""
    src = from_curr or from_c or "USD"
    dst = to_curr or to_c or "MAD"
    hist = await M.fx_history(src, dst, range_str=range, interval=interval)
    if not hist:
        raise HTTPException(400, "تعذر جلب تاريخ زوج العملات المطلوب")
    return hist


@app.get("/fx/rate-on-date")
async def fx_rate_on_date(
    date: str = Query(..., description="التاريخ بصيغة YYYY-MM-DD مثل 2026-10-15"),
    from_curr: str | None = Query(None, alias="from"),
    to_curr: str | None = Query(None, alias="to"),
    from_c: str | None = Query(None),
    to_c: str | None = Query(None),
    amount: float = Query(1.0),
):
    """سعر الصرف التاريخي لفاتورة أو مصروف بتاريخ محدد (مع الرجوع لأقرب يوم تداول سابق في العطل)."""
    src = from_curr or from_c or "USD"
    dst = to_curr or to_c or "MAD"
    try:
        res = await M.fx_rate_on_date(src, dst, date, amount)
    except ValueError:
        raise HTTPException(400, "صيغة التاريخ غير صحيحة، استخدم YYYY-MM-DD")
    if not res:
        raise HTTPException(404, f"تعذر جلب سعر الصرف التاريخي لـ {src.upper()}/{dst.upper()} في {date}")
    return res


# ══════════════════════════════════════════════ 7. الذهب والفضة وشارت المعادن ══
@app.get("/metals")
async def all_metals(currency: str = Query("MAD", description="العملة لعرض أسعار المعادن مثل MAD أو EUR أو SAR")):
    """أسعار الذهب والفضة الحية بالأونصة والجرام (24، 21، 18) بالدولار وبالعملة المختارة."""
    m = await M.precious_metals(currency)
    if not m:
        raise HTTPException(400, f"عملة غير مدعومة: {currency.upper()}")
    return m


@app.get("/metals/gold")
async def gold_only(currency: str = Query("MAD")):
    """سعر الذهب فقط بتفاصيل العيارات والأونصة بالدولار وبالعملة المختارة."""
    m = await M.precious_metals(currency)
    if not m:
        raise HTTPException(400, f"عملة غير مدعومة: {currency.upper()}")
    return {
        "currency": m["currency"],
        "gold": m["metals"]["gold"],
        "usd_to_mad_rate": m["usd_to_mad_rate"],
        "usd_to_currency_rate": m["usd_to_currency_rate"],
        "updated_at": m["updated_at"],
    }


@app.get("/metals/silver")
async def silver_only(currency: str = Query("MAD")):
    """سعر الفضة الحي فقط بالأونصة والجرام بالدولار وبالعملة المختارة."""
    m = await M.precious_metals(currency)
    if not m:
        raise HTTPException(400, f"عملة غير مدعومة: {currency.upper()}")
    return {
        "currency": m["currency"],
        "silver": m["metals"]["silver"],
        "usd_to_mad_rate": m["usd_to_mad_rate"],
        "usd_to_currency_rate": m["usd_to_currency_rate"],
        "updated_at": m["updated_at"],
    }


@app.get("/metals/history/{metal}")
async def metal_history(metal: str, range: str = Query("1mo"), interval: str = Query("1d")):
    """شارت وتاريخ الذهب أو الفضة بالشموع (للرسوم البيانية: gold أو silver)."""
    hist = await M.metal_history(metal, range_=range, interval=interval)
    if not hist:
        raise HTTPException(404, "المعدن غير صحيح (اختر gold أو silver)")
    return hist


# ══════════════════════════════════════════════ 8. محرك البحث (Search Engine) ═
@app.get("/search")
async def unified_search_endpoint(q: str = Query(min_length=1, description="كلمة البحث")):
    """بحث موحد وشامل في كل الأسواق (كريبتو، أسهم كازا، أسهم عالمية، عملات، ذهب وفضة)."""
    return await M.unified_search(q)


@app.get("/crypto/search")
async def crypto_search_endpoint(q: str = Query(min_length=1)):
    """بحث داخل أهم 50 عملة كريبتو (بالاسم أو الرمز مثل BTC, Solana)."""
    results = await M.crypto_search(q)
    return {"query": q, "count": len(results), "results": results}


@app.get("/casablanca/search")
async def casa_search_endpoint(q: str = Query(min_length=1)):
    """بحث داخل أسهم بورصة الدار البيضاء (بالاسم أو الرمز مثل ATW, الضحى)."""
    results = await M.casa_search(q)
    return {"query": q, "count": len(results), "results": results}


@app.get("/stocks/search")
async def stocks_search_endpoint(q: str = Query(min_length=1)):
    """بحث داخل الأسهم الأمريكية والعالمية (مثل Apple, Tesla, Nvidia)."""
    results = await M.stocks_search(q)
    return {"query": q, "count": len(results), "results": results}


# ══════════════════════════════════════════════ 9. المزامنة والمحفظة (للأندرويد) ══
@app.get("/sync/rates")
async def sync_rates_endpoint(base: str = Query("MAD", description="العملة الأساسية لحسابات المستخدم مثل MAD أو EUR")):
    """حزمة خفيفة ومضغوطة (~2KB) لمزامنة العملات والذهب والفضة وتخزينها محلياً (Offline Cache) في تطبيق النفقات."""
    res = await M.sync_rates(base)
    if not res:
        raise HTTPException(400, f"تعذر جلب حزمة المزامنة للعملة: {base.upper()}")
    return res


@app.post("/portfolio/value")
async def portfolio_value_endpoint(payload: PortfolioRequest):
    """حساب القيمة الإجمالية لمحفظة/مدخرات المستخدم بعملته الأساسية بدون حفظ أي بيانات على السيرفر."""
    items = [it.model_dump() for it in payload.items]
    res = await M.portfolio_value(payload.target_currency, items)
    if not res:
        raise HTTPException(400, f"العملة الهدف غير مدعومة: {payload.target_currency.upper()}")
    return res


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
