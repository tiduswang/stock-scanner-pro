"""
新闻公告数据服务
- A股个股新闻
- 个股公告
- 情绪评分（简单规则版）
"""
import pandas as pd
import akshare as ak
from typing import List, Dict, Optional, Literal
from backend.utils.logger import log
from backend.utils.cache import cached

MarketType = Literal["A", "HK", "ETF"]


class NewsService:
    """新闻公告数据服务"""

    # 情绪词典（简易版）
    SENTIMENT_POSITIVE = ["增长", "盈利", "突破", "中标", "合作", "回购", "分红", "增持", "利好", "订单", "业绩预增", "扭亏"]
    SENTIMENT_NEGATIVE = ["亏损", "下降", "违规", "处罚", "减持", "风险", "退市", "诉讼", "违约", "质押", "业绩预减", "利空"]

    @cached("news", "news_list")
    def get_stock_news(self, code: str, market: MarketType = "A", limit: int = 30) -> List[Dict]:
        """获取个股新闻列表"""
        log.debug(f"[新闻] 获取 {market} {code} 新闻, 限{limit}条")
        news_list = []
        try:
            if market == "A":
                news_list += self._get_a_news_em(code, limit)
        except Exception as e:
            log.error(f"[新闻] 获取 {code} 新闻失败: {e}")

        # 情绪标注
        for n in news_list:
            n["sentiment"] = self._calc_sentiment(n.get("title", "") + n.get("content", ""))
        return news_list[:limit]

    @cached("news", "ann_list")
    def get_stock_announcements(self, code: str, market: MarketType = "A", limit: int = 20) -> List[Dict]:
        """获取个股公告"""
        log.debug(f"[公告] 获取 {market} {code} 公告, 限{limit}条")
        anns = []
        try:
            if market == "A":
                anns += self._get_a_ann_em(code, limit)
        except Exception as e:
            log.error(f"[公告] 获取 {code} 公告失败: {e}")
        for a in anns:
            a["sentiment"] = self._calc_sentiment(a.get("title", ""))
        return anns[:limit]

    def _get_a_news_em(self, code: str, limit: int) -> List[Dict]:
        """东方财富A股新闻"""
        try:
            code = str(code).zfill(6)
            df = ak.stock_news_em(symbol=code)
            if df is None or df.empty:
                return []
            items = []
            for _, r in df.head(limit).iterrows():
                items.append({
                    "title": str(r.get("新闻标题", "")),
                    "content": str(r.get("新闻内容", ""))[:500],
                    "source": str(r.get("文章来源", "")),
                    "publish_time": str(r.get("发布时间", "")),
                    "url": str(r.get("新闻链接", "")),
                    "type": "news",
                })
            return items
        except Exception as e:
            log.debug(f"[新闻] EM新闻接口异常: {e}")
            return []

    def _get_a_ann_em(self, code: str, limit: int) -> List[Dict]:
        """东方财富A股公告"""
        try:
            code = str(code).zfill(6)
            df = ak.stock_notice_report(symbol=code)
            if df is None or df.empty:
                return []
            items = []
            # 不同版本列名可能不同，兼容处理
            col_title = "公告标题" if "公告标题" in df.columns else "标题"
            col_date = "公告日期" if "公告日期" in df.columns else "日期"
            col_link = "公告链接" if "公告链接" in df.columns else "链接"
            for _, r in df.head(limit).iterrows():
                items.append({
                    "title": str(r.get(col_title, "")),
                    "publish_time": str(r.get(col_date, "")),
                    "url": str(r.get(col_link, "")),
                    "type": "announcement",
                })
            return items
        except Exception as e:
            log.debug(f"[公告] EM公告接口异常: {e}")
            return []

    def _calc_sentiment(self, text: str) -> Dict:
        """简单规则情感分析"""
        if not text:
            return {"score": 0, "label": "neutral", "pos_count": 0, "neg_count": 0}
        pos_count = sum(1 for w in self.SENTIMENT_POSITIVE if w in text)
        neg_count = sum(1 for w in self.SENTIMENT_NEGATIVE if w in text)
        total = pos_count + neg_count
        if total == 0:
            score = 0.0
            label = "neutral"
        else:
            score = (pos_count - neg_count) / total  # -1 ~ 1
            if score > 0.2:
                label = "positive"
            elif score < -0.2:
                label = "negative"
            else:
                label = "neutral"
        return {
            "score": round(score, 3),
            "label": label,
            "pos_count": pos_count,
            "neg_count": neg_count,
        }

    def aggregate_sentiment(self, news_list: List[Dict]) -> Dict:
        """聚合多条新闻的情绪"""
        if not news_list:
            return {"avg_score": 0.0, "positive": 0, "neutral": 0, "negative": 0, "total": 0}
        scores = [n["sentiment"]["score"] for n in news_list]
        labels = [n["sentiment"]["label"] for n in news_list]
        return {
            "avg_score": round(sum(scores) / len(scores), 3),
            "positive": labels.count("positive"),
            "neutral": labels.count("neutral"),
            "negative": labels.count("negative"),
            "total": len(labels),
        }


# 单例
_news_service: Optional[NewsService] = None


def get_news_service() -> NewsService:
    global _news_service
    if _news_service is None:
        _news_service = NewsService()
    return _news_service
