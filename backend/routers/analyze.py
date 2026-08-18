"""
分析路由：单只股票量化分析 + 买卖点 + 深度分析报告
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Literal

from backend.services.data.market_data import get_market_data_service
from backend.services.analysis.scoring import get_scoring_engine
from backend.services.analysis.buy_sell import get_buy_sell_analyzer
from backend.services.scanner.ai_scanner import OllamaClient

router = APIRouter(prefix="/api/analyze", tags=["单股分析"])

MarketType = Literal["A", "HK", "ETF"]


class AnalyzeReq(BaseModel):
    code: str
    market: MarketType = "A"
    weights: Optional[Dict[str, float]] = None
    analysis_params: Optional[Dict] = None
    include_kline: bool = True
    kline_days: int = 120


@router.post("/stock")
def analyze_stock(req: AnalyzeReq):
    """单只股票量化分析+买卖点"""
    engine = get_scoring_engine()
    bs = get_buy_sell_analyzer()
    md = get_market_data_service()

    score_res = engine.score_stock(req.code, req.market, weights=req.weights, analysis_params=req.analysis_params)
    kline = md.get_kline(req.code, req.market, "daily", req.kline_days) if req.include_kline else None
    buy_sell_res = bs.analyze(score_res, kline)

    return {
        "score": score_res,
        "buy_sell": buy_sell_res,
        "kline": kline.to_dict(orient="records") if kline is not None and not kline.empty else [],
    }


class AIDeepReq(BaseModel):
    code: str
    market: MarketType = "A"
    score_res: Optional[Dict] = None   # 可传已有的评分结果
    weights: Optional[Dict[str, float]] = None
    analysis_params: Optional[Dict] = None
    ollama_cfg: Optional[Dict] = None  # {base_url, model, timeout}


@router.post("/stock/ai")
def ai_deep_analyze(req: AIDeepReq):
    """单只股票AI深度分析（流式SSE建议用ws/sse，这里返回整段；也可用于同步展示）"""
    # 先评分
    engine = get_scoring_engine()
    score_res = req.score_res or engine.score_stock(req.code, req.market, req.weights, req.analysis_params)

    # 构造单只股票prompt
    import json
    sys_prompt = """你是资深A股量化分析师，针对下面这只股票的量化评分结果，给出专业的深度解读：
- 一句话投资评级（强烈推荐/谨慎推荐/中性/回避）
- 核心看点（3条）与风险（3条）
- 技术面解读（趋势、买卖信号）
- 基本面解读（盈利/估值/成长）
- T+1模式下的操作建议（买入价区间、止损价、止盈目标、仓位）
语言简洁专业。"""
    user_prompt = f"""股票分析输入数据：{json.dumps(score_res, ensure_ascii=False, indent=2)}"""

    client = OllamaClient(
        base_url=req.ollama_cfg.get("base_url") if req.ollama_cfg else None,
        model=req.ollama_cfg.get("model") if req.ollama_cfg else None,
        timeout=req.ollama_cfg.get("timeout") if req.ollama_cfg else None,
    )
    report = client.chat_sync(sys_prompt, user_prompt)
    return {
        "score": score_res,
        "ai_report": report,
    }
