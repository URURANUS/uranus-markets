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
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import core
import markets as M


@asynccontextmanager
async def lifespan(_app):
    await core.startup()
    yield
    await core.shutdown()


app = FastAPI(
    title="URANUS Markets LITE API",
    version="1.1.0",
    description="سيرفر لايت متكامل مع الرسوم البيانية والشارتات لجميع الأسواق المنتقاة حصرياً.",
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
        "version": "1.1.0",
        "type": "Lite Edition with Full Charts & History",
        "docs": "/docs",
        "sections": {
            "crypto": ["/crypto/top50", "/crypto/price/{symbol}", "/crypto/history/{symbol}"],
            "exchanges": ["/exchanges", "/exchange/{slug}/stocks", "/casablanca/stocks", "/casablanca/price/{symbol}", "/casablanca/history/{symbol}"],
            "indices": ["/indices", "/indices/history/{slug}"],
            "stocks": ["/stocks/history/{symbol}"],
            "forex": ["/fx/rates", "/fx/convert", "/fx/history"],
            "metals": ["/metals", "/metals/gold", "/metals/silver", "/metals/history/{metal}"]
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
@app.get("/stocks/history/{symbol}")
async def stock_history(symbol: str, range: str = Query("1mo"), interval: str = Query("1d")):
    """بيانات الشموع التاريخية لأي سهم أمريكي أو كندي أو أوروبي (للرسوم البيانية)."""
    hist = await M.stock_history(symbol, range_=range, interval=interval)
    if not hist:
        raise HTTPException(404, f"بيانات التاريخ غير متوفرة لـ {symbol.upper()}")
    return hist


# ══════════════════════════════════════════════ 6. أهم العملات وشارت الصرف ════
@app.get("/fx/rates")
async def fx_rates():
    """أسعار أهم 10 عملات عالمية مقابل الدرهم المغربي (MAD)."""
    return await M.fx_rates()


@app.get("/fx/convert")
async def fx_convert(from_c: str = Query("USD"), to_c: str = Query("MAD"), amount: float = Query(1.0)):
    """تحويل فوري بين أهم العملات (مثال: USD إلى MAD)."""
    res = await M.fx_convert(from_c, to_c, amount)
    if not res:
        raise HTTPException(400, "عملة غير مدعومة في النسخة المخففة")
    return res


@app.get("/fx/history")
async def fx_history(from_c: str = Query("USD"), to_c: str = Query("MAD"), range: str = Query("1mo"), interval: str = Query("1d")):
    """شارت لتغييرات سعر صرف أي عملتين عبر الزمان (للرسم البياني)."""
    hist = await M.fx_history(from_c, to_c, range_str=range, interval=interval)
    if not hist:
        raise HTTPException(400, "تعذر جلب تاريخ زوج العملات المطلوب")
    return hist


# ══════════════════════════════════════════════ 7. الذهب والفضة وشارت المعادن ══
@app.get("/metals")
async def all_metals():
    """أسعار الذهب والفضة بالأونصة والجرام (24، 21، 18) بالدولار وبالدرهم المغربي."""
    return await M.precious_metals()


@app.get("/metals/gold")
async def gold_only():
    """سعر الذهب فقط بتفاصيل العيارات والأونصة بالدولار وبالدرهم."""
    m = await M.precious_metals()
    return {"gold": m["metals"]["gold"], "usd_to_mad_rate": m["usd_to_mad_rate"]}


@app.get("/metals/silver")
async def silver_only():
    """سعر الفضة فقط بالأونصة والجرام بالدولار وبالدرهم."""
    m = await M.precious_metals()
    return {"silver": m["metals"]["silver"], "usd_to_mad_rate": m["usd_to_mad_rate"]}


@app.get("/metals/history/{metal}")
async def metal_history(metal: str, range: str = Query("1mo"), interval: str = Query("1d")):
    """شارت وتاريخ الذهب أو الفضة بالشموع (للرسوم البيانية: gold أو silver)."""
    hist = await M.metal_history(metal, range_=range, interval=interval)
    if not hist:
        raise HTTPException(404, "المعدن غير صحيح (اختر gold أو silver)")
    return hist


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
