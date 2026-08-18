"""
行情数据服务
- 日K线/周K线/月K线
- 实时行情快照
- 成交量、换手率等
"""
import pandas as pd
import numpy as np
import akshare as ak
from typing import Dict, Optional, Literal
from backend.utils.logger import log
from backend.utils.cache import cached

MarketType = Literal["A", "HK", "ETF"]
KlinePeriod = Literal["daily", "weekly", "monthly"]


class MarketDataService:
    """行情数据获取服务"""

    def _normalize_a_code(self, code: str) -> str:
        """规范化A股代码"""
        return str(code).zfill(6)

    def _detect_market(self, code: str, market: Optional[MarketType]) -> MarketType:
        """根据代码推断市场"""
        if market:
            return market
        code = str(code)
        # 港股通常5位
        if len(code) == 5:
            return "HK"
        # ETF常见开头
        if code.startswith(("510", "511", "512", "513", "515", "516", "518", "56", "58", "159", "161")):
            return "ETF"
        return "A"

    # ============ 获取K线数据 ============
    @cached("market", "kline")
    def get_kline(self, code: str, market: Optional[MarketType] = None,
                  period: KlinePeriod = "daily", days: int = 365) -> pd.DataFrame:
        """
        获取K线数据
        Returns: DataFrame columns: [date, open, close, high, low, volume, turnover]
        """
        market = self._detect_market(code, market)
        log.debug(f"[行情] 获取{market} {code} {period} K线, 最近{days}天")
        try:
            df = self._fetch_kline(code, market, period)
            if df is None or df.empty:
                return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "turnover"])
            # 取最近N天
            df = df.tail(days).reset_index(drop=True)
            return df
        except Exception as e:
            log.error(f"[行情] 获取 {code} K线失败: {e}")
            return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "turnover"])

    def _fetch_kline(self, code: str, market: MarketType, period: KlinePeriod) -> pd.DataFrame:
        """不同市场的K线拉取"""
        period_map = {"daily": "日k", "weekly": "周k", "monthly": "月k"}
        ak_period = period_map.get(period, "daily")

        if market == "A":
            code = self._normalize_a_code(code)
            df = ak.stock_zh_a_hist(symbol=code, period=ak_period, adjust="qfq")
            if df is None or df.empty:
                return pd.DataFrame()
            return self._normalize_kline(df, {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume", "成交额": "turnover"
            })

        elif market == "HK":
            df = ak.stock_hk_hist(symbol=code, period=ak_period, adjust="qfq")
            if df is None or df.empty:
                return pd.DataFrame()
            return self._normalize_kline(df, {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume", "成交额": "turnover"
            })

        elif market == "ETF":
            code = self._normalize_a_code(code)
            df = ak.fund_etf_hist_em(symbol=code, period=ak_period, adjust="qfq")
            if df is None or df.empty:
                return pd.DataFrame()
            return self._normalize_kline(df, {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume", "成交额": "turnover"
            })

        return pd.DataFrame()

    def _normalize_kline(self, df: pd.DataFrame, col_map: Dict[str, str]) -> pd.DataFrame:
        """统一K线列名和类型"""
        df = df.rename(columns=col_map)
        df = df[[c for c in ["date", "open", "close", "high", "low", "volume", "turnover"] if c in df.columns]].copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        for c in ["open", "close", "high", "low", "volume", "turnover"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        return df

    # ============ 实时行情快照 ============
    @cached("market", "snapshot")
    def get_realtime_snapshot(self, code: str, market: Optional[MarketType] = None) -> Dict:
        """获取单只股票实时行情快照"""
        market = self._detect_market(code, market)
        log.debug(f"[行情] 获取{market} {code} 实时快照")
        try:
            if market == "A":
                code = self._normalize_a_code(code)
                df = ak.stock_zh_a_spot_em()
                row = df[df["代码"] == code]
                if row.empty:
                    return {}
                r = row.iloc[0]
                return {
                    "code": code,
                    "name": r.get("名称", ""),
                    "price": float(r.get("最新价", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "change_amt": float(r.get("涨跌额", 0) or 0),
                    "volume": float(r.get("成交量", 0) or 0),
                    "turnover": float(r.get("成交额", 0) or 0),
                    "amplitude": float(r.get("振幅", 0) or 0),
                    "high": float(r.get("最高", 0) or 0),
                    "low": float(r.get("最低", 0) or 0),
                    "open": float(r.get("今开", 0) or 0),
                    "prev_close": float(r.get("昨收", 0) or 0),
                    "turnover_rate": float(r.get("换手率", 0) or 0),
                    "pe": float(r.get("市盈率-动态", 0) or 0),
                    "pb": float(r.get("市净率", 0) or 0),
                    "market_cap": float(r.get("总市值", 0) or 0),
                }
            elif market == "HK":
                df = ak.stock_hk_spot_em()
                row = df[df["代码"] == code]
                if row.empty:
                    return {}
                r = row.iloc[0]
                return {
                    "code": code,
                    "name": r.get("名称", ""),
                    "price": float(r.get("最新价", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "volume": float(r.get("成交量", 0) or 0),
                    "turnover": float(r.get("成交额", 0) or 0),
                    "high": float(r.get("最高", 0) or 0),
                    "low": float(r.get("最低", 0) or 0),
                    "prev_close": float(r.get("昨收", 0) or 0),
                }
            elif market == "ETF":
                code = self._normalize_a_code(code)
                df = ak.fund_etf_spot_em()
                row = df[df["代码"] == code]
                if row.empty:
                    return {}
                r = row.iloc[0]
                return {
                    "code": code,
                    "name": r.get("名称", ""),
                    "price": float(r.get("最新价", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "volume": float(r.get("成交量", 0) or 0),
                    "turnover": float(r.get("成交额", 0) or 0),
                    "high": float(r.get("最高", 0) or 0),
                    "low": float(r.get("最低", 0) or 0),
                }
        except Exception as e:
            log.error(f"[行情] 获取 {code} 实时快照失败: {e}")
        return {}


# 单例
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service
