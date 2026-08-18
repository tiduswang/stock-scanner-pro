"""
情绪面分析器
- 新闻聚合情绪
- 公告情绪
- 涨跌停/连板热度（如有）
"""
from typing import Dict, List, Optional
from backend.utils.logger import log


class SentimentAnalyzer:
    """情绪面分析器"""

    def analyze(self, news: List[Dict], announcements: List[Dict],
                snapshot: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        p = {
            "news_weight": 0.55,
            "ann_weight": 0.30,
            "shortterm_weight": 0.15,
        }
        if params:
            p.update(params)

        result = {
            "score": 50.0,
            "breakdown": {},
            "news_summary": {},
            "ann_summary": {},
            "summary_texts": [],
            "error": None,
        }

        try:
            from backend.services.data.news import get_news_service
            ns = get_news_service()

            # ==== 1. 新闻情绪 ====
            ns_agg = ns.aggregate_sentiment(news)
            result["news_summary"] = ns_agg
            # -1~1 -> 0~100
            news_score = 50 + ns_agg["avg_score"] * 50
            # 考虑新闻数量，太少可信度下降
            if ns_agg["total"] < 3:
                news_score = news_score * 0.7 + 50 * 0.3
            result["breakdown"]["news_score"] = round(max(0, min(100, news_score)), 2)

            # ==== 2. 公告情绪 ====
            ann_agg = ns.aggregate_sentiment(announcements)
            result["ann_summary"] = ann_agg
            ann_score = 50 + ann_agg["avg_score"] * 50
            if ann_agg["total"] < 2:
                ann_score = ann_score * 0.6 + 50 * 0.4
            result["breakdown"]["announcement_score"] = round(max(0, min(100, ann_score)), 2)

            # ==== 3. 短期量价情绪（来自快照）====
            st_score = 50
            if snapshot:
                chg = snapshot.get("change_pct", 0) or 0
                amp = snapshot.get("amplitude", 0) or 0
                turnover = snapshot.get("turnover_rate", 0) or 0
                # 小涨温和放量=情绪好；涨停=情绪极好；暴跌=极差
                if chg >= 9.8:
                    st_score = 95
                elif chg >= 3:
                    st_score = 75
                elif chg >= 0:
                    st_score = 58
                elif chg >= -3:
                    st_score = 42
                elif chg >= -9.8:
                    st_score = 20
                else:
                    st_score = 5
                result["summary_texts"].append(f"当日涨跌 {chg:.2f}%, 振幅 {amp:.2f}%, 换手 {turnover:.2f}%")
            result["breakdown"]["shortterm_score"] = max(0, min(100, st_score))

            # ==== 汇总 ====
            total = (
                result["breakdown"]["news_score"] * p["news_weight"] +
                result["breakdown"]["announcement_score"] * p["ann_weight"] +
                result["breakdown"]["shortterm_score"] * p["shortterm_weight"]
            )
            result["score"] = round(total, 2)

            # 文本摘要
            if ns_agg["total"]:
                result["summary_texts"].insert(0, f"新闻：正面{ns_agg['positive']}条/中性{ns_agg['neutral']}条/负面{ns_agg['negative']}条")
            if ann_agg["total"]:
                result["summary_texts"].insert(0, f"公告：正面{ann_agg['positive']}条/中性{ann_agg['neutral']}条/负面{ann_agg['negative']}条")

        except Exception as e:
            log.error(f"[情绪面] 分析失败: {e}")
            result["error"] = str(e)

        return result


_sentiment_analyzer: Optional[SentimentAnalyzer] = None

def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer
