"""
数据同步路由
- POST /api/data/sync    触发数据同步（股票列表/日线/快照）
- GET  /api/data/sync/status  查询同步进度
- GET  /api/data/db/stats  本地数据库统计
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from backend.services.data.sync_service import get_sync_service
from backend.db.session import get_session
from backend.db.models import Stock, DailyKline, RealtimeSnapshot
from backend.utils.logger import log

router = APIRouter(prefix="/api/data", tags=["数据同步"])


class SyncRequest(BaseModel):
    markets: List[str] = ["A"]
    sync_type: str = "daily_kline"  # stock_list / daily_kline / snapshot
    days: int = 365


@router.post("/sync")
def trigger_sync(req: SyncRequest):
    """触发数据同步"""
    svc = get_sync_service()
    if req.sync_type == "stock_list":
        msg = svc.sync_stock_list(req.markets)
    elif req.sync_type == "daily_kline":
        msg = svc.sync_daily_klines(req.markets, req.days)
    elif req.sync_type == "snapshot":
        msg = svc.sync_snapshots(req.markets)
    else:
        return {"ok": False, "msg": f"未知同步类型: {req.sync_type}"}
    return {"ok": True, "msg": msg, "sync_type": req.sync_type, "markets": req.markets}


@router.get("/sync/status")
def sync_status():
    """查询同步进度"""
    svc = get_sync_service()
    return svc.get_status()


@router.get("/db/stats")
def db_stats():
    """本地数据库统计"""
    try:
        with get_session() as s:
            stocks = s.query(Stock).count()
            klines = s.query(DailyKline).count()
            snapshots = s.query(RealtimeSnapshot).count()
            # 各市场股票数
            from sqlalchemy import func
            by_market = {}
            for m in ["A", "HK", "ETF"]:
                by_market[m] = s.query(func.count(Stock.code)).filter(Stock.market == m).scalar() or 0
            return {
                "ok": True,
                "stocks": stocks,
                "daily_klines": klines,
                "snapshots": snapshots,
                "by_market": by_market,
            }
    except Exception as e:
        log.error(f"DB统计失败: {e}")
        return {"ok": False, "msg": str(e)}
