"""
综合评分引擎
- 汇总技术面/基本面/情绪面得分
- 权重可配置
- T+1交易模式适配
"""
import pandas as pd
from typing import Dict, Optional, Literal
from backend.config import get_settings, MARKET_TYPES
from backend.utils.logger import log
from backend.services.data.market_data import get_market_data_service
from backend.services.data.fundamental import get_fundamental_service
from backend.services.data.news import get_news_service
from backend.services.analysis.technical import get_technical_analyzer
from backend.services.analysis.fundamental_analysis import get_fundamental_analyzer
from backend.services.analysis.sentiment import get_sentiment_analyzer


class ScoringEngine:
    """综合评分引擎"""

    def __init__(self):
        self.settings = get_settings()
        self.market_svc = get_market_data_service()
        self.fund_svc = get_fundamental_service()
        self.news_svc = get_news_service()
        self.tech = get_technical_analyzer()
        self.fund_analyzer = get_fundamental_analyzer()
        self.senti = get_sentiment_analyzer()

    def score_stock(self, code: str, market: Literal["A", "HK", "ETF"] = "A",
                    weights: Optional[Dict] = None, analysis_params: Optional[Dict] = None) -> Dict:
        """
        单只股票综合评分
        Args:
            weights: {technical, fundamental, sentiment} 总和=1
            analysis_params: {technical:{}, fundamental:{}, sentiment:{}} 各面参数
        """
        # 默认权重
        w = {
            "technical": self.settings.WEIGHT_TECHNICAL,
            "fundamental": self.settings.WEIGHT_FUNDAMENTAL,
            "sentiment": self.settings.WEIGHT_SENTIMENT,
        }
        if weights:
            w.update(weights)
        # 归一化
        s = sum(w.values()) or 1
        w = {k: v / s for k, v in w.items()}

        ap = analysis_params or {}

        # ========== 1. 拉数据 ==========
        kline = self.market_svc.get_kline(code, market, "daily", 365)
        snapshot = self.market_svc.get_realtime_snapshot(code, market) or {}
        fundamental = self.fund_svc.get_financial_indicators(code, market) or {}
        news = self.news_svc.get_stock_news(code, market, limit=20)
        announcements = self.news_svc.get_stock_announcements(code, market, limit=10)

        # ========== 2. 三面分析 ==========
        tech_result = self.tech.analyze(kline, ap.get("technical"))
        fund_result = self.fund_analyzer.analyze(fundamental, ap.get("fundamental"))
        senti_result = self.senti.analyze(news, announcements, snapshot, ap.get("sentiment"))

        tech_score = tech_result.get("score", 0)
        fund_score = fund_result.get("score", 0)
        senti_score = senti_result.get("score", 0)

        # ========== 3. 综合得分 ==========
        comprehensive = (
            tech_score * w["technical"] +
            fund_score * w["fundamental"] +
            senti_score * w["sentiment"]
        )

        # ========== 4. T+1模式风险修正 ==========
        # T+1下：当日暴涨股追高风险高；当日暴跌抄底需谨慎但可关注
        adj_comprehensive = comprehensive
        chg_pct = snapshot.get("change_pct", 0) or 0
        if chg_pct >= 7:
            adj_comprehensive *= 0.9  # 过热惩罚
        elif chg_pct <= -6:
            adj_comprehensive = adj_comprehensive * 0.9 + comprehensive * 0.05  # 小幅修正

        # ========== 5. 评级 ==========
        rating, rating_color, rating_desc = self._rating(adj_comprehensive)

        result = {
            "code": code,
            "market": market,
            "market_name": MARKET_TYPES.get(market, ""),
            "name": snapshot.get("name", "") or self._guess_name(code, market),
            "snapshot": snapshot,
            "scores": {
                "technical": round(tech_score, 2),
                "fundamental": round(fund_score, 2),
                "sentiment": round(senti_score, 2),
                "comprehensive": round(comprehensive, 2),
                "comprehensive_adjusted": round(adj_comprehensive, 2),
            },
            "weights": w,
            "rating": rating,
            "rating_color": rating_color,
            "rating_desc": rating_desc,
            "technical": tech_result,
            "fundamental": fund_result,
            "sentiment": senti_result,
            "news_count": len(news),
            "announcement_count": len(announcements),
            "kline_sample_size": len(kline),
        }
        return result

    def _rating(self, score: float):
        if score >= 85:
            return "S", "#e74c3c", "强烈推荐（极佳买入机会）"
        elif score >= 75:
            return "A", "#e67e22", "推荐（可考虑买入）"
        elif score >= 65:
            return "B", "#f1c40f", "中性偏多（逢低关注）"
        elif score >= 55:
            return "C", "#3498db", "中性（观望为主）"
        elif score >= 40:
            return "D", "#95a5a6", "中性偏空（谨慎）"
        else:
            return "E", "#7f8c8d", "回避（不建议参与）"

    def _guess_name(self, code: str, market: str) -> str:
        from backend.services.data.stock_list import get_stock_list_service
        sl = get_stock_list_service()
        df = sl.get_market_list(market) if market in MARKET_TYPES else sl.get_all_list()
        row = df[df["code"] == str(code).zfill(6) if market in ("A", "ETF") else df["code"] == str(code)]
        if not row.empty:
            return row.iloc[0].get("name", "")
        return ""


_scoring_engine: Optional[ScoringEngine] = None

def get_scoring_engine() -> ScoringEngine:
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = ScoringEngine()
    return _scoring_engine
