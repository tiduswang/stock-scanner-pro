"""
选股扫描路由：基础选股扫描 + AI选股 + SSE进度
"""
import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

from backend.services.scanner.base_scanner import ScanRequest, get_base_scanner
from backend.services.scanner.ai_scanner import get_ai_scanner
from backend.services.scanner.progress import get_progress_tracker

router = APIRouter(prefix="/api/scan", tags=["选股扫描"])

MarketType = Literal["A", "HK", "ETF"]


class ScanReq(BaseModel):
    markets: List[MarketType] = Field(default_factory=lambda: ["A"])
    stock_codes: Optional[List[str]] = None
    sector: Optional[str] = None
    score_threshold: int = 70
    top_n: int = 50
    weights: Optional[Dict[str, float]] = None
    analysis_params: Optional[Dict] = None
    max_workers: int = 3
    include_buy_sell: bool = True


class AIScanReq(ScanReq):
    # AI模式：after_filter = 先量化筛再AI深度（默认）；selected_only = 直接对给定代码/板块AI分析
    ai_mode: Literal["after_filter", "selected_only"] = "after_filter"
    ollama_cfg: Optional[Dict] = None  # {base_url, model, timeout}


def _req_to_scan(r: ScanReq) -> ScanRequest:
    return ScanRequest(
        markets=r.markets,
        stock_codes=r.stock_codes,
        sector=r.sector,
        score_threshold=r.score_threshold,
        top_n=r.top_n,
        weights=r.weights,
        analysis_params=r.analysis_params,
        max_workers=r.max_workers,
        include_buy_sell=r.include_buy_sell,
    )


@router.post("/start")
def start_scan(r: ScanReq):
    """启动普通选股扫描，返回scan_id"""
    scanner = get_base_scanner()
    scan_id = scanner.start_scan(_req_to_scan(r))
    return {"scan_id": scan_id}


@router.post("/ai/start")
def start_ai_scan(r: AIScanReq):
    """启动AI选股扫描，返回scan_id"""
    ai = get_ai_scanner()
    scan_id = ai.start_ai_scan(_req_to_scan(r), ollama_cfg=r.ollama_cfg, mode=r.ai_mode)
    return {"scan_id": scan_id}


@router.get("/progress/{scan_id}")
def get_progress(scan_id: str):
    """获取当前进度快照（轮询用）"""
    p = get_progress_tracker().get(scan_id)
    if not p:
        return {"not_found": True, "scan_id": scan_id}
    # 附加ai_report
    raw = get_progress_tracker()._progresses.get(scan_id)
    if raw and hasattr(raw, "ai_report"):
        p["ai_report"] = raw.ai_report
    return p


@router.get("/progress/{scan_id}/stream")
async def progress_stream(scan_id: str, request: Request):
    """SSE实时进度流"""
    tracker = get_progress_tracker()
    p = tracker.get(scan_id)
    if not p:
        # 立即返回错误事件
        async def _empty():
            yield f"event: error\ndata: {json.dumps({'msg': 'scan_id不存在'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    async def _gen():
        last_pct = -1.0
        sent_done = False
        try:
            while True:
                if await request.is_disconnected():
                    break
                p = tracker.get(scan_id)
                if not p:
                    break
                # 附加ai_report
                raw = tracker._progresses.get(scan_id)
                if raw and hasattr(raw, "ai_report"):
                    p["ai_report"] = raw.ai_report
                cur_pct = p.get("progress_pct", 0)
                status = p.get("status", "")
                # 每1%或状态变化推送
                if abs(cur_pct - last_pct) >= 1 or status in ("done", "error"):
                    last_pct = cur_pct
                    yield f"event: progress\ndata: {json.dumps(p, ensure_ascii=False)}\n\n"
                if status in ("done", "error") and not sent_done:
                    sent_done = True
                    yield f"event: final\ndata: {json.dumps(p, ensure_ascii=False)}\n\n"
                    break
                await asyncio.sleep(0.8)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
