"""
股票列表服务：
- 获取A股/港股/ETF全量列表
- 维护拼音首字母搜索索引
- 支持按板块分类
"""
import pandas as pd
import akshare as ak
from typing import List, Dict, Optional, Literal
from pypinyin import lazy_pinyin, Style
from backend.utils.logger import log
from backend.utils.cache import cache_get, cache_set, cached

MarketType = Literal["A", "HK", "ETF"]


class StockListService:
    """股票列表与搜索索引服务"""

    def __init__(self):
        self._index_cache: Dict[MarketType, pd.DataFrame] = {}

    # ============ A股列表 ============
    @cached("stock_list", "a_share_list")
    def get_a_share_list(self) -> pd.DataFrame:
        """获取A股全量股票列表"""
        log.info("[数据层] 正在获取A股列表...")
        try:
            df = ak.stock_info_a_code_name()
            if df is None or df.empty:
                log.warning("[数据层] A股列表为空，返回空DataFrame")
                return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector"])
            df = df.rename(columns={"code": "code", "name": "name"})
            df["code"] = df["code"].astype(str).str.zfill(6)
            # 拼音索引
            df["pinyin"] = df["name"].apply(
                lambda n: "".join(lazy_pinyin(n, style=Style.NORMAL)) if pd.notna(n) else ""
            )
            df["first_letter"] = df["name"].apply(
                lambda n: "".join(lazy_pinyin(n, style=Style.FIRST_LETTER)).upper() if pd.notna(n) else ""
            )
            df["sector"] = ""  # 稍后单独补板块
            df["market"] = "A"
            log.info(f"[数据层] 获取A股列表成功，共 {len(df)} 只")
            return df
        except Exception as e:
            log.error(f"[数据层] 获取A股列表失败: {e}")
            return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])

    # ============ 港股列表 ============
    @cached("stock_list", "hk_list")
    def get_hk_list(self) -> pd.DataFrame:
        """获取港股列表"""
        log.info("[数据层] 正在获取港股列表...")
        try:
            df = ak.stock_hk_spot_em()
            if df is None or df.empty:
                return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])
            result = pd.DataFrame()
            result["code"] = df["代码"].astype(str)
            result["name"] = df["名称"].astype(str)
            result["pinyin"] = result["name"].apply(
                lambda n: "".join(lazy_pinyin(n, style=Style.NORMAL)) if pd.notna(n) else ""
            )
            result["first_letter"] = result["name"].apply(
                lambda n: "".join(lazy_pinyin(n, style=Style.FIRST_LETTER)).upper() if pd.notna(n) else ""
            )
            result["sector"] = df.get("所属行业", "").astype(str)
            result["market"] = "HK"
            log.info(f"[数据层] 获取港股列表成功，共 {len(result)} 只")
            return result
        except Exception as e:
            log.error(f"[数据层] 获取港股列表失败: {e}")
            return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])

    # ============ ETF列表 ============
    @cached("stock_list", "etf_list")
    def get_etf_list(self) -> pd.DataFrame:
        """获取ETF基金列表"""
        log.info("[数据层] 正在获取ETF列表...")
        try:
            df = ak.fund_etf_spot_em()
            if df is None or df.empty:
                return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])
            result = pd.DataFrame()
            result["code"] = df["代码"].astype(str).str.zfill(6)
            result["name"] = df["名称"].astype(str)
            result["pinyin"] = result["name"].apply(
                lambda n: "".join(lazy_pinyin(n, style=Style.NORMAL)) if pd.notna(n) else ""
            )
            result["first_letter"] = result["name"].apply(
                lambda n: "".join(lazy_pinyin(n, style=Style.FIRST_LETTER)).upper() if pd.notna(n) else ""
            )
            result["sector"] = "ETF"
            result["market"] = "ETF"
            log.info(f"[数据层] 获取ETF列表成功，共 {len(result)} 只")
            return result
        except Exception as e:
            log.error(f"[数据层] 获取ETF列表失败: {e}")
            return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])

    def get_market_list(self, market: MarketType = "A") -> pd.DataFrame:
        """获取指定市场的股票列表"""
        if market == "A":
            return self.get_a_share_list()
        elif market == "HK":
            return self.get_hk_list()
        elif market == "ETF":
            return self.get_etf_list()
        return pd.DataFrame()

    def get_all_list(self, markets: Optional[List[MarketType]] = None) -> pd.DataFrame:
        """获取多个市场的合并列表"""
        if markets is None:
            markets = ["A", "HK", "ETF"]
        frames = []
        for m in markets:
            frames.append(self.get_market_list(m))
        return pd.concat(frames, ignore_index=True)

    # ============ 按板块筛选A股 ============
    def get_a_share_by_sector(self, sector: str) -> List[Dict]:
        """按板块名称筛选A股"""
        df = self.get_a_share_list()
        if df.empty:
            return []
        # 方式：通过akshare获取板块成分股
        try:
            # 尝试按概念/行业板块获取
            concept_df = ak.stock_board_concept_cons_em(symbol=sector)
            if concept_df is not None and not concept_df.empty:
                codes = concept_df["代码"].astype(str).str.zfill(6).tolist()
                sub = df[df["code"].isin(codes)].copy()
                sub["sector"] = sector
                return sub.to_dict(orient="records")
        except Exception as e:
            log.debug(f"[数据层] 按概念获取板块成分失败: {e}，尝试行业板块")
            try:
                industry_df = ak.stock_board_industry_cons_em(symbol=sector)
                if industry_df is not None and not industry_df.empty:
                    codes = industry_df["代码"].astype(str).str.zfill(6).tolist()
                    sub = df[df["code"].isin(codes)].copy()
                    sub["sector"] = sector
                    return sub.to_dict(orient="records")
            except Exception as e2:
                log.error(f"[数据层] 按行业获取板块成分也失败: {e2}")
        return []


# 单例
_stock_list_service: Optional[StockListService] = None


def get_stock_list_service() -> StockListService:
    global _stock_list_service
    if _stock_list_service is None:
        _stock_list_service = StockListService()
    return _stock_list_service
