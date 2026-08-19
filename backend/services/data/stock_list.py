"""
股票列表服务（DB优先 + 多数据源回退）
- 优先从本地数据库读取股票列表（极速）
- DB未命中或过期时，从多数据源拉取并回写DB
- 维护拼音首字母搜索索引
"""
import pandas as pd
from typing import List, Dict, Optional, Literal
from datetime import datetime, timedelta
from pypinyin import lazy_pinyin, Style

from backend.utils.logger import log
from backend.utils.cache import cached
from backend.db.session import get_session
from backend.db.models import Stock
from backend.services.data.sources import get_fetcher

MarketType = Literal["A", "HK", "ETF"]

# 股票列表过期时间（小时）—— 超过则重新从远程拉取
_STOCK_LIST_MAX_AGE_HOURS = 12


def _is_db_stale(updated_at: Optional[datetime], max_age_hours: int = _STOCK_LIST_MAX_AGE_HOURS) -> bool:
    """判断DB缓存是否过期"""
    if updated_at is None:
        return True
    return (datetime.utcnow() - updated_at) > timedelta(hours=max_age_hours)


class StockListService:
    """股票列表与搜索索引服务（DB优先 + 多源回退）"""

    def __init__(self):
        self._fetcher = get_fetcher()

    # ============ DB 读取 ============
    def _get_from_db(self, market: MarketType) -> pd.DataFrame:
        """从DB读取股票列表"""
        try:
            with get_session() as s:
                rows = s.query(Stock).filter(Stock.market == market).all()
                if not rows:
                    return pd.DataFrame()
                # 检查是否过期
                if _is_db_stale(rows[0].updated_at):
                    log.debug(f"[数据层] DB {market} 列表已过期，需刷新")
                    return pd.DataFrame()
                data = [r.to_dict() for r in rows]
                return pd.DataFrame(data)
        except Exception as e:
            log.warning(f"[数据层] DB读取{market}列表失败: {e}")
            return pd.DataFrame()

    def _save_to_db(self, df: pd.DataFrame, market: MarketType):
        """将列表写入DB（全量替换）"""
        if df is None or df.empty:
            return
        try:
            records = df.to_dict(orient="records")
            with get_session() as s:
                # 先删除该市场旧数据
                s.query(Stock).filter(Stock.market == market).delete()
                # 批量插入
                for r in records:
                    code = str(r.get("code", "")).strip()
                    if not code:
                        continue
                    name = str(r.get("name", "")).strip()
                    pinyin = "".join(lazy_pinyin(name, style=Style.NORMAL)) if name else ""
                    first_letter = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).upper() if name else ""
                    sector = str(r.get("sector", "") or "")
                    s.add(Stock(
                        code=code, name=name, pinyin=pinyin,
                        first_letter=first_letter, sector=sector, market=market,
                    ))
            log.info(f"[数据层] {market} 列表已写入DB: {len(records)} 只")
        except Exception as e:
            log.error(f"[数据层] DB写入{market}列表失败: {e}")

    # ============ A股列表 ============
    @cached("stock_list", "a_share_list")
    def get_a_share_list(self) -> pd.DataFrame:
        """获取A股全量股票列表（DB优先 → 多源回退）"""
        # 1. 先查DB
        df = self._get_from_db("A")
        if not df.empty:
            log.debug(f"[数据层] A股列表命中DB: {len(df)} 只")
            return df

        # 2. DB未命中，多源拉取
        log.info("[数据层] DB未命中A股列表，从多数据源拉取...")
        raw = self._fetcher.fetch_a_share_list()
        if raw is None or raw.empty:
            log.error("[数据层] A股列表所有数据源均失败")
            return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])

        # 3. 补充拼音索引
        raw["code"] = raw["code"].astype(str).str.zfill(6)
        raw["pinyin"] = raw["name"].apply(
            lambda n: "".join(lazy_pinyin(str(n), style=Style.NORMAL)) if pd.notna(n) and n else ""
        )
        raw["first_letter"] = raw["name"].apply(
            lambda n: "".join(lazy_pinyin(str(n), style=Style.FIRST_LETTER)).upper() if pd.notna(n) and n else ""
        )
        raw["sector"] = ""
        raw["market"] = "A"

        # 4. 写回DB
        self._save_to_db(raw, "A")
        log.info(f"[数据层] 获取A股列表成功，共 {len(raw)} 只")
        return raw

    # ============ 港股列表 ============
    @cached("stock_list", "hk_list")
    def get_hk_list(self) -> pd.DataFrame:
        """获取港股列表（DB优先 → 多源回退）"""
        df = self._get_from_db("HK")
        if not df.empty:
            return df

        log.info("[数据层] DB未命中港股列表，从多数据源拉取...")
        raw = self._fetcher.fetch_hk_list()
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])

        raw["pinyin"] = raw["name"].apply(
            lambda n: "".join(lazy_pinyin(str(n), style=Style.NORMAL)) if pd.notna(n) and n else ""
        )
        raw["first_letter"] = raw["name"].apply(
            lambda n: "".join(lazy_pinyin(str(n), style=Style.FIRST_LETTER)).upper() if pd.notna(n) and n else ""
        )
        raw["sector"] = ""
        raw["market"] = "HK"
        self._save_to_db(raw, "HK")
        log.info(f"[数据层] 获取港股列表成功，共 {len(raw)} 只")
        return raw

    # ============ ETF列表 ============
    @cached("stock_list", "etf_list")
    def get_etf_list(self) -> pd.DataFrame:
        """获取ETF基金列表（DB优先 → 多源回退）"""
        df = self._get_from_db("ETF")
        if not df.empty:
            return df

        log.info("[数据层] DB未命中ETF列表，从多数据源拉取...")
        raw = self._fetcher.fetch_etf_list()
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["code", "name", "pinyin", "first_letter", "sector", "market"])

        raw["code"] = raw["code"].astype(str).str.zfill(6)
        raw["pinyin"] = raw["name"].apply(
            lambda n: "".join(lazy_pinyin(str(n), style=Style.NORMAL)) if pd.notna(n) and n else ""
        )
        raw["first_letter"] = raw["name"].apply(
            lambda n: "".join(lazy_pinyin(str(n), style=Style.FIRST_LETTER)).upper() if pd.notna(n) and n else ""
        )
        raw["sector"] = "ETF"
        raw["market"] = "ETF"
        self._save_to_db(raw, "ETF")
        log.info(f"[数据层] 获取ETF列表成功，共 {len(raw)} 只")
        return raw

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
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # ============ 按板块筛选A股 ============
    def get_a_share_by_sector(self, sector: str) -> List[Dict]:
        """按板块名称筛选A股"""
        import akshare as ak
        df = self.get_a_share_list()
        if df.empty:
            return []
        try:
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
