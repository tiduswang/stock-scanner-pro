"""
多数据源适配层
- 同一数据提供多个 akshare 接口备选
- 自动重试（指数退避）
- 接口失败自动切换到下一个备选源
- 全市场实时快照一次性拉取（避免逐只查询）

数据源优先级：
  A股列表:  stock_info_a_code_name → stock_zh_a_spot_em(取代码+名称)
  A股日线:  stock_zh_a_hist → stock_zh_a_daily(新浪) 
  A股快照:  stock_zh_a_spot_em(东财) → stock_zh_a_spot(新浪)
  港股列表/快照: stock_hk_spot_em
  ETF列表/快照: fund_etf_spot_em
"""
import time
import random
from typing import Optional, Callable, List, Dict, Literal

import pandas as pd
import akshare as ak

from backend.utils.logger import log

MarketType = Literal["A", "HK", "ETF"]
KlinePeriod = Literal["daily", "weekly", "monthly"]


def _retry(fn: Callable, label: str, max_retries: int = 2, base_delay: float = 0.5) -> Optional[pd.DataFrame]:
    """带指数退避的重试"""
    for attempt in range(max_retries + 1):
        try:
            df = fn()
            if df is not None and not df.empty:
                return df
            log.debug(f"[数据源] {label} 第{attempt+1}次返回空")
        except Exception as e:
            log.warning(f"[数据源] {label} 第{attempt+1}次失败: {e}")
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.3)
            time.sleep(delay)
    return None


def _try_sources(sources: List[tuple], label: str) -> pd.DataFrame:
    """
    按优先级尝试多个数据源，第一个成功即返回
    sources: [(source_name, callable), ...]
    """
    for name, fn in sources:
        df = _retry(fn, f"{label}/{name}")
        if df is not None and not df.empty:
            log.info(f"[数据源] {label} 使用源: {name}, 行数={len(df)}")
            return df
    log.error(f"[数据源] {label} 所有源均失败")
    return pd.DataFrame()


class MultiSourceFetcher:
    """多数据源获取器（单例）"""

    # ============ 股票列表 ============
    def fetch_a_share_list(self) -> pd.DataFrame:
        """A股全量列表（多源备选）"""
        def _src1():
            df = ak.stock_info_a_code_name()
            if df is None or df.empty:
                return None
            df = df.rename(columns={"code": "code", "name": "name"})
            df["code"] = df["code"].astype(str).str.zfill(6)
            return df[["code", "name"]]

        def _src2():
            # 东财实时行情里取代码+名称（全市场5000+只）
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return None
            df = df[["代码", "名称"]].copy()
            df.columns = ["code", "name"]
            df["code"] = df["code"].astype(str).str.zfill(6)
            return df

        return _try_sources([("stock_info_a_code_name", _src1), ("stock_zh_a_spot_em", _src2)], "A股列表")

    def fetch_hk_list(self) -> pd.DataFrame:
        """港股列表"""
        def _src1():
            df = ak.stock_hk_spot_em()
            if df is None or df.empty:
                return None
            result = pd.DataFrame()
            result["code"] = df["代码"].astype(str)
            result["name"] = df["名称"].astype(str)
            return result[["code", "name"]]

        return _try_sources([("stock_hk_spot_em", _src1)], "港股列表")

    def fetch_etf_list(self) -> pd.DataFrame:
        """ETF列表"""
        def _src1():
            df = ak.fund_etf_spot_em()
            if df is None or df.empty:
                return None
            result = pd.DataFrame()
            result["code"] = df["代码"].astype(str).str.zfill(6)
            result["name"] = df["名称"].astype(str)
            return result[["code", "name"]]

        return _try_sources([("fund_etf_spot_em", _src1)], "ETF列表")

    def fetch_market_list(self, market: MarketType) -> pd.DataFrame:
        """获取指定市场的股票列表"""
        if market == "A":
            return self.fetch_a_share_list()
        elif market == "HK":
            return self.fetch_hk_list()
        elif market == "ETF":
            return self.fetch_etf_list()
        return pd.DataFrame()

    # ============ K线数据 ============
    def fetch_kline(self, code: str, market: MarketType, period: KlinePeriod = "daily") -> pd.DataFrame:
        """获取单只股票K线（多源备选）"""
        period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
        ak_period = period_map.get(period, "daily")

        if market == "A":
            code = str(code).zfill(6)
            # 新浪源 symbol 需带市场前缀: 6/5/9开头为沪市, 其余深市
            if code.startswith(("6", "5", "9")):
                sina_symbol = f"sh{code}"
            else:
                sina_symbol = f"sz{code}"
            def _src1():
                return ak.stock_zh_a_daily(symbol=sina_symbol, adjust="qfq")
            def _src2():
                return ak.stock_zh_a_hist(symbol=code, period=ak_period, adjust="qfq")
            return _try_sources(
                [("stock_zh_a_daily", _src1), ("stock_zh_a_hist", _src2)],
                f"A股K线 {code}",
            )

        elif market == "HK":
            def _src1():
                return ak.stock_hk_hist(symbol=str(code), period=ak_period, adjust="qfq")
            return _try_sources([("stock_hk_hist", _src1)], f"港股K线 {code}")

        elif market == "ETF":
            code = str(code).zfill(6)
            def _src1():
                return ak.fund_etf_hist_em(symbol=code, period=ak_period, adjust="qfq")
            return _try_sources([("fund_etf_hist_em", _src1)], f"ETF K线 {code}")

        return pd.DataFrame()

    # ============ 全市场实时快照（批量，不再逐只） ============
    def fetch_all_a_share_snapshot(self) -> pd.DataFrame:
        """一次性获取A股全市场实时快照（5000+只）"""
        def _src1():
            return ak.stock_zh_a_spot_em()
        return _try_sources([("stock_zh_a_spot_em", _src1)], "A股全量快照")

    def fetch_all_hk_snapshot(self) -> pd.DataFrame:
        """港股全市场快照"""
        def _src1():
            return ak.stock_hk_spot_em()
        return _try_sources([("stock_hk_spot_em", _src1)], "港股全量快照")

    def fetch_all_etf_snapshot(self) -> pd.DataFrame:
        """ETF全市场快照"""
        def _src1():
            return ak.fund_etf_spot_em()
        return _try_sources([("fund_etf_spot_em", _src1)], "ETF全量快照")

    def fetch_all_snapshot(self, market: MarketType) -> pd.DataFrame:
        """获取指定市场全量快照"""
        if market == "A":
            return self.fetch_all_a_share_snapshot()
        elif market == "HK":
            return self.fetch_all_hk_snapshot()
        elif market == "ETF":
            return self.fetch_all_etf_snapshot()
        return pd.DataFrame()

    # ============ 快照列名统一化 ============
    @staticmethod
    def normalize_snapshot(df: pd.DataFrame, market: MarketType) -> List[Dict]:
        """将原始快照 DataFrame 转为统一 Dict 列表（用于批量写DB）"""
        if df is None or df.empty:
            return []
        results: List[Dict] = []
        for _, r in df.iterrows():
            item = {"market": market}
            if market == "A":
                item["code"] = str(r.get("代码", "")).zfill(6)
                item["name"] = str(r.get("名称", ""))
                item["price"] = float(r.get("最新价", 0) or 0)
                item["change_pct"] = float(r.get("涨跌幅", 0) or 0)
                item["change_amt"] = float(r.get("涨跌额", 0) or 0)
                item["volume"] = float(r.get("成交量", 0) or 0)
                item["turnover"] = float(r.get("成交额", 0) or 0)
                item["amplitude"] = float(r.get("振幅", 0) or 0)
                item["high"] = float(r.get("最高", 0) or 0)
                item["low"] = float(r.get("最低", 0) or 0)
                item["open"] = float(r.get("今开", 0) or 0)
                item["prev_close"] = float(r.get("昨收", 0) or 0)
                item["turnover_rate"] = float(r.get("换手率", 0) or 0)
                item["pe"] = float(r.get("市盈率-动态", 0) or 0)
                item["pb"] = float(r.get("市净率", 0) or 0)
                item["market_cap"] = float(r.get("总市值", 0) or 0)
            elif market == "HK":
                item["code"] = str(r.get("代码", ""))
                item["name"] = str(r.get("名称", ""))
                item["price"] = float(r.get("最新价", 0) or 0)
                item["change_pct"] = float(r.get("涨跌幅", 0) or 0)
                item["volume"] = float(r.get("成交量", 0) or 0)
                item["turnover"] = float(r.get("成交额", 0) or 0)
                item["high"] = float(r.get("最高", 0) or 0)
                item["low"] = float(r.get("最低", 0) or 0)
                item["prev_close"] = float(r.get("昨收", 0) or 0)
            elif market == "ETF":
                item["code"] = str(r.get("代码", "")).zfill(6)
                item["name"] = str(r.get("名称", ""))
                item["price"] = float(r.get("最新价", 0) or 0)
                item["change_pct"] = float(r.get("涨跌幅", 0) or 0)
                item["volume"] = float(r.get("成交量", 0) or 0)
                item["turnover"] = float(r.get("成交额", 0) or 0)
                item["high"] = float(r.get("最高", 0) or 0)
                item["low"] = float(r.get("最低", 0) or 0)
            results.append(item)
        return results

    # ============ K线列名统一化 ============
    @staticmethod
    def normalize_kline(df: pd.DataFrame) -> pd.DataFrame:
        """将原始K线 DataFrame 转为统一格式"""
        if df is None or df.empty:
            return pd.DataFrame(columns=["trade_date", "open", "close", "high", "low", "volume", "turnover"])
        col_map = {
            "日期": "trade_date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume", "成交额": "turnover",
            # 新浪源 stock_zh_a_daily 英文列名
            "date": "trade_date", "amount": "turnover",
            "turnover": "turnover_rate",
        }
        df = df.rename(columns=col_map)
        keep = [c for c in ["trade_date", "open", "close", "high", "low", "volume", "turnover"] if c in df.columns]
        df = df[keep].copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
        for c in ["open", "close", "high", "low", "volume", "turnover"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        return df


# 单例
_fetcher: Optional[MultiSourceFetcher] = None


def get_fetcher() -> MultiSourceFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = MultiSourceFetcher()
    return _fetcher
