"""
基本面分析器
- 盈利能力评分
- 偿债能力评分
- 营运能力评分
- 成长能力评分
- 估值合理性评分
"""
from typing import Dict, Optional
from backend.utils.logger import log


class FundamentalAnalyzer:
    """基本面分析器"""

    def analyze(self, fundamental_data: Dict, params: Optional[Dict] = None) -> Dict:
        """执行基本面分析"""
        p = {
            "pe_max_good": 20,     # PE低于此为加分
            "pe_max_acceptable": 60,  # PE高于此为重扣分
            "pb_max_good": 2,
            "pb_max_acceptable": 8,
            "roe_good": 15,
            "debt_ratio_good": 40,
            "debt_ratio_bad": 70,
            "growth_good": 20,
        }
        if params:
            p.update(params)

        result = {
            "score": 50.0,
            "breakdown": {},
            "summary": [],
            "error": None,
        }

        try:
            profitability = fundamental_data.get("profitability", {}) or {}
            solvency = fundamental_data.get("solvency", {}) or {}
            operation = fundamental_data.get("operation", {}) or {}
            growth = fundamental_data.get("growth", {}) or {}
            valuation = fundamental_data.get("valuation", {}) or {}

            # ETF/港股特殊标记
            note = fundamental_data.get("note", "")
            if note:
                result["note"] = note

            # ==== 1. 盈利能力 ====
            roe = profitability.get("roe", 0) or 0
            npm = profitability.get("net_profit_margin", 0) or 0
            profit_score = 50
            if roe >= p["roe_good"]:
                profit_score = 90
            elif roe >= 8:
                profit_score = 70
            elif roe >= 3:
                profit_score = 50
            elif roe > 0:
                profit_score = 35
            else:
                profit_score = 15
            if npm > 20: profit_score += 5
            result["breakdown"]["profitability_score"] = max(0, min(100, profit_score))
            if roe > 0:
                result["summary"].append(f"ROE {roe:.2f}%, 净利率 {npm:.2f}%")

            # ==== 2. 偿债能力 ====
            debt = solvency.get("debt_ratio", 0) or 0
            current = solvency.get("current_ratio", 0) or 0
            solv_score = 50
            if debt and debt > 0:
                if debt <= p["debt_ratio_good"]:
                    solv_score = 85
                elif debt <= p["debt_ratio_bad"]:
                    solv_score = 55
                else:
                    solv_score = 30
            if current >= 2:
                solv_score += 10
            result["breakdown"]["solvency_score"] = max(0, min(100, solv_score))
            if debt:
                result["summary"].append(f"资产负债率 {debt:.2f}%, 流动比率 {current:.2f}")

            # ==== 3. 营运能力 ====
            ato = operation.get("asset_turnover", 0) or 0
            op_score = 50
            if ato >= 1.0:
                op_score = 80
            elif ato >= 0.6:
                op_score = 65
            elif ato >= 0.3:
                op_score = 50
            elif ato > 0:
                op_score = 35
            result["breakdown"]["operation_score"] = max(0, min(100, op_score))

            # ==== 4. 成长能力 ====
            rev_g = growth.get("revenue_growth", 0) or 0
            pro_g = growth.get("profit_growth", 0) or 0
            growth_score = 50
            if pro_g >= p["growth_good"]:
                growth_score = 90
            elif pro_g >= 10:
                growth_score = 70
            elif pro_g >= 0:
                growth_score = 50
            elif pro_g >= -20:
                growth_score = 30
            else:
                growth_score = 15
            if rev_g >= 20: growth_score += 5
            result["breakdown"]["growth_score"] = max(0, min(100, growth_score))
            result["summary"].append(f"营收增长 {rev_g:.2f}%, 净利润增长 {pro_g:.2f}%")

            # ==== 5. 估值 ====
            pe = valuation.get("pe_ttm", 0) or valuation.get("pe", 0) or 0
            pb = valuation.get("pb", 0) or 0
            val_score = 50
            if pe > 0:
                if pe <= p["pe_max_good"]:
                    val_score = 85
                elif pe <= 40:
                    val_score = 65
                elif pe <= p["pe_max_acceptable"]:
                    val_score = 45
                else:
                    val_score = 25
                # PEG: 如果有利润增长
                peg_g = pro_g if pro_g > 0 else 1
                peg = pe / peg_g
                if 0.5 <= peg <= 1.5:
                    val_score += 5
                elif peg < 0.5:
                    val_score += 10
            if pb > 0:
                if pb <= p["pb_max_good"]:
                    val_score = min(100, val_score + 5)
                elif pb > p["pb_max_acceptable"]:
                    val_score = max(0, val_score - 10)
            result["breakdown"]["valuation_score"] = max(0, min(100, val_score))
            if pe or pb:
                result["summary"].append(f"PE(TTM) {pe:.2f}, PB {pb:.2f}")

            # ==== 汇总 ====
            # 对于ETF/港股，权重不同
            if note and ("ETF" in note or "港股" in note):
                weights = {
                    "profitability_score": 0.10,
                    "solvency_score": 0.10,
                    "operation_score": 0.10,
                    "growth_score": 0.10,
                    "valuation_score": 0.60,
                }
            else:
                weights = {
                    "profitability_score": 0.25,
                    "solvency_score": 0.15,
                    "operation_score": 0.15,
                    "growth_score": 0.25,
                    "valuation_score": 0.20,
                }
            total = 0.0
            for k, w in weights.items():
                total += result["breakdown"].get(k, 50) * w
            result["score"] = round(total, 2)

        except Exception as e:
            log.error(f"[基本面] 分析失败: {e}")
            result["error"] = str(e)

        return result


_fundamental_analyzer: Optional[FundamentalAnalyzer] = None

def get_fundamental_analyzer() -> FundamentalAnalyzer:
    global _fundamental_analyzer
    if _fundamental_analyzer is None:
        _fundamental_analyzer = FundamentalAnalyzer()
    return _fundamental_analyzer
