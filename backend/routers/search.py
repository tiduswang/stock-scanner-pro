"""
搜索路由：股票代码/拼音搜索、热门推荐
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional, Literal

from backend.services.search.stock_search import get_stock_search_service

router = APIRouter(prefix="/api/search", tags=["搜索"])

MarketType = Literal["A", "HK", "ETF"]


@router.get("/stock")
def search_stock(
    q: str = Query(..., min_length=1, description="搜索关键字：支持代码/拼音首字母/全拼音/中文名称"),
    markets: Optional[str] = Query(None, description="市场过滤，逗号分隔，如 A,HK,ETF"),
    limit: int = Query(30, ge=1, le=100),
):
    svc = get_stock_search_service()
    market_list = None
    if markets:
        market_list = [m.strip() for m in markets.split(",") if m.strip() in ("A", "HK", "ETF")]
        if not market_list:
            market_list = None
    results = svc.search(keyword=q, markets=market_list, limit=limit)
    return {"keyword": q, "total": len(results), "items": results}


@router.get("/hot")
def hot_suggest(
    markets: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    svc = get_stock_search_service()
    market_list = None
    if markets:
        market_list = [m.strip() for m in markets.split(",") if m.strip() in ("A", "HK", "ETF")]
    items = svc.suggest_hot(markets=market_list, limit=limit)
    return {"items": items}
