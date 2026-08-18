"""
基本面数据服务
- 主要财务指标（盈利能力、偿债能力、营运能力、成长能力）
- 估值指标（PE/PB/PEG/PS）
"""
import pandas as pd
import numpy as np
import akshare as ak
from typing import Dict, Optional, Literal
from backend.utils.logger import log
from backend.utils.cache import cached

MarketType = Literal["A", "HK", "ETF"]


class FundamentalService:
    """基本面数据服务"""

    @cached("fundamental", "indicators")
    def get_financial_indicators(self, code: str, market: MarketType = "A") -> Dict:
        """
        获取股票核心财务指标
        返回: 盈利能力/偿债能力/营运能力/成长能力/估值指标
        """
        log.debug(f"[基本面] 获取 {market} {code} 财务指标")
        result = {
            "profitability": {},   # 盈利能力
            "solvency": {},        # 偿债能力
            "operation": {},       # 营运能力
            "growth": {},          # 成长能力
            "valuation": {},       # 估值
            "raw": {}
        }
        try:
            if market == "A":
                return self._get_a_share_fundamental(code, result)
            elif market == "HK":
                return self._get_hk_fundamental(code, result)
            elif market == "ETF":
                return self._get_etf_fundamental(code, result)
        except Exception as e:
            log.error(f"[基本面] 获取 {code} 财务指标失败: {e}")
        return result

    def _get_a_share_fundamental(self, code: str, result: Dict) -> Dict:
        """A股财务指标"""
        code = str(code).zfill(6)

        # 1. 尝试获取关键指标
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code)
            if df is not None and not df.empty:
                row = df.iloc[0]
                # 盈利能力
                result["profitability"] = {
                    "roe": self._safe_float(row.get("净资产收益率(%)", 0)),
                    "roa": self._safe_float(row.get("总资产报酬率(%)", 0)),
                    "net_profit_margin": self._safe_float(row.get("销售净利率(%)", 0)),
                    "gross_margin": self._safe_float(row.get("销售毛利率(%)", 0)),
                }
                # 偿债能力
                result["solvency"] = {
                    "current_ratio": self._safe_float(row.get("流动比率", 0)),
                    "debt_ratio": self._safe_float(row.get("资产负债率(%)", 0)),
                    "quick_ratio": self._safe_float(row.get("速动比率", 0)),
                }
                # 营运能力
                result["operation"] = {
                    "asset_turnover": self._safe_float(row.get("总资产周转率(次)", 0)),
                    "inventory_turnover": self._safe_float(row.get("存货周转率(次)", 0)),
                    "receivable_turnover": self._safe_float(row.get("应收账款周转率(次)", 0)),
                }
                # 成长能力
                result["growth"] = {
                    "revenue_growth": self._safe_float(row.get("主营业务收入增长率(%)", 0)),
                    "profit_growth": self._safe_float(row.get("净利润增长率(%)", 0)),
                    "total_asset_growth": self._safe_float(row.get("总资产增长率(%)", 0)),
                }
        except Exception as e:
            log.debug(f"[基本面] A股关键指标接口失败(可能改版): {e}")

        # 2. 估值指标 - 从实时快照补
        try:
            val_df = ak.stock_a_indicator_lg(symbol=code)
            if val_df is not None and not val_df.empty:
                r = val_df.iloc[-1]
                result["valuation"] = {
                    "pe": self._safe_float(r.get("pe", 0)),
                    "pe_ttm": self._safe_float(r.get("pe_ttm", 0)),
                    "pb": self._safe_float(r.get("pb", 0)),
                    "ps": self._safe_float(r.get("ps", 0)),
                    "ps_ttm": self._safe_float(r.get("ps_ttm", 0)),
                    "dv_ratio": self._safe_float(r.get("dv_ratio", 0)),
                    "total_mv": self._safe_float(r.get("total_mv", 0)),
                }
        except Exception as e:
            log.debug(f"[基本面] A股估值指标接口失败: {e}")

        return result

    def _get_hk_fundamental(self, code: str, result: Dict) -> Dict:
        """港股财务指标（简化）"""
        try:
            # 港股数据较少，给出占位信息
            result["note"] = "港股财务指标数据受限，仅作参考"
        except Exception as e:
            log.debug(f"[基本面] 港股财务: {e}")
        return result

    def _get_etf_fundamental(self, code: str, result: Dict) -> Dict:
        """ETF基本面：不适用传统财务指标，给出基金数据"""
        result["note"] = "ETF不适用传统财务指标，请参考净值、折溢价、持仓数据"
        try:
            code = str(code).zfill(6)
            df = ak.fund_etf_fund_daily_em(symbol=code)
            if df is not None and not df.empty:
                r = df.iloc[0]
                result["valuation"] = {
                    "unit_nav": self._safe_float(r.get("单位净值", 0)),
                    "cumulative_nav": self._safe_float(r.get("累计净值", 0)),
                    "premium_rate": self._safe_float(r.get("溢价率", 0)),
                }
        except Exception as e:
            log.debug(f"[基本面] ETF财务: {e}")
        return result

    @staticmethod
    def _safe_float(v) -> float:
        try:
            if v is None or v == "" or (isinstance(v, float) and np.isnan(v)):
                return 0.0
            return round(float(v), 4)
        except Exception:
            return 0.0


# 单例
_fundamental_service: Optional[FundamentalService] = None


def get_fundamental_service() -> FundamentalService:
    global _fundamental_service
    if _fundamental_service is None:
        _fundamental_service = FundamentalService()
    return _fundamental_service
