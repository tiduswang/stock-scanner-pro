"""
股票搜索服务
- 支持股票代码精确/模糊搜索
- 支持名称拼音首字母搜索（如 "PAYH" -> 平安银行）
- 支持完整拼音搜索（如 "pinganyinhang" -> 平安银行）
- 支持名称模糊搜索
- 支持按市场过滤
"""
import re
from typing import List, Dict, Literal, Optional
from backend.utils.logger import log
from backend.services.data.stock_list import get_stock_list_service

MarketType = Literal["A", "HK", "ETF"]


class StockSearchService:
    """股票搜索服务"""

    def __init__(self):
        self.stock_list = get_stock_list_service()

    def search(self,
               keyword: str,
               markets: Optional[List[MarketType]] = None,
               limit: int = 30) -> List[Dict]:
        """
        智能搜索：
          - 纯数字/以6位开头 -> 按代码搜索
          - 全大写英文字母 -> 拼音首字母搜索
          - 小写/混写英文 -> 完整拼音搜索
          - 中文 -> 名称搜索
        """
        keyword = (keyword or "").strip()
        if not keyword:
            return []

        df = self.stock_list.get_all_list(markets)
        if df.empty:
            return []

        results: List[Dict] = []
        keyword_upper = keyword.upper()
        keyword_lower = keyword.lower()
        is_pure_number = bool(re.fullmatch(r"\d+", keyword))
        is_pure_letter_upper = bool(re.fullmatch(r"[A-Z]+", keyword_upper))
        is_pure_letter = bool(re.fullmatch(r"[a-zA-Z]+", keyword))
        has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in keyword)

        # 优先匹配顺序
        scores_map = {}  # index -> score

        for idx, row in df.iterrows():
            code = str(row.get("code", ""))
            name = str(row.get("name", ""))
            fl = str(row.get("first_letter", ""))
            py = str(row.get("pinyin", ""))
            score = 0

            # ===== 代码匹配 =====
            if is_pure_number:
                code_norm = code.zfill(6)
                kw_norm = keyword.zfill(6)
                if code_norm == kw_norm:
                    score = 100
                elif code_norm.startswith(keyword) or code.startswith(keyword):
                    score = 85
                elif keyword in code_norm or keyword in code:
                    score = 70

            # ===== 拼音首字母 =====
            if is_pure_letter_upper and fl:
                if fl == keyword_upper:
                    score = max(score, 95)
                elif fl.startswith(keyword_upper):
                    score = max(score, 80)
                elif keyword_upper in fl:
                    score = max(score, 60)

            # ===== 完整拼音 =====
            if is_pure_letter and py:
                if py == keyword_lower:
                    score = max(score, 95)
                elif py.startswith(keyword_lower):
                    score = max(score, 78)
                elif keyword_lower in py:
                    score = max(score, 55)

            # ===== 中文名 =====
            if has_chinese and name:
                if name == keyword:
                    score = max(score, 100)
                elif name.startswith(keyword):
                    score = max(score, 88)
                elif keyword in name:
                    score = max(score, 75)

            # ===== 宽松匹配：英文全字母做首字母子序列 =====
            if is_pure_letter_upper and fl and score == 0:
                if self._is_subsequence(keyword_upper, fl):
                    score = 35

            if score > 0:
                scores_map[idx] = score

        # 排序取前N
        sorted_items = sorted(scores_map.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        for idx, s in sorted_items:
            row = df.iloc[idx]
            results.append({
                "code": str(row["code"]),
                "name": str(row["name"]),
                "market": str(row.get("market", "")),
                "sector": str(row.get("sector", "")),
                "first_letter": str(row.get("first_letter", "")),
                "pinyin": str(row.get("pinyin", "")),
                "match_score": s,
            })

        log.debug(f"[搜索] keyword={keyword}, 命中 {len(results)} 条")
        return results

    @staticmethod
    def _is_subsequence(pattern: str, text: str) -> bool:
        """判断pattern是否是text的子序列（用于首字母模糊匹配）"""
        it = iter(text)
        return all(ch in it for ch in pattern)

    def suggest_hot(self, markets: Optional[List[MarketType]] = None, limit: int = 10) -> List[Dict]:
        """热门/推荐股票（简单取前N只，后面可接热门榜）"""
        df = self.stock_list.get_all_list(markets)
        if df.empty:
            return []
        rows = df.head(limit).to_dict(orient="records")
        return [{
            "code": str(r["code"]),
            "name": str(r["name"]),
            "market": str(r.get("market", "")),
            "sector": str(r.get("sector", "")),
            "first_letter": str(r.get("first_letter", "")),
        } for r in rows]


_search_service: Optional[StockSearchService] = None

def get_stock_search_service() -> StockSearchService:
    global _search_service
    if _search_service is None:
        _search_service = StockSearchService()
    return _search_service
