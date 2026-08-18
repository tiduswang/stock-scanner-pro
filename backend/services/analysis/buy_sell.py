"""
买卖点决策与推荐理由生成（T+1模式适配）
- 买入点建议价位、止损、止盈
- 卖出点建议
- 结构化推荐理由（技术/基本/情绪面各维度）
"""
import pandas as pd
from typing import Dict, List, Optional
from backend.utils.logger import log


class BuySellAnalyzer:
    """买卖点决策分析器（T+1模式）"""

    def analyze(self, score_result: Dict, kline: Optional[pd.DataFrame] = None) -> Dict:
        """基于评分结果+K线给出买卖决策"""
        snapshot = score_result.get("snapshot", {}) or {}
        tech = score_result.get("technical", {}) or {}
        fund = score_result.get("fundamental", {}) or {}
        senti = score_result.get("sentiment", {}) or {}
        comprehensive = score_result.get("scores", {}).get("comprehensive_adjusted", 50)
        current_price = snapshot.get("price", 0) or snapshot.get("prev_close", 0) or 0

        result = {
            "action": "hold",           # buy / sell / hold / watch
            "action_cn": "观望",
            "buy_point": None,
            "sell_point": None,
            "stop_loss": None,
            "take_profit": None,
            "position_suggestion": "",
            "time_horizon": "",
            "reasons_buy": [],
            "reasons_sell": [],
            "risk_warnings": [],
        }

        if current_price <= 0:
            result["risk_warnings"].append("当前价格无效，可能是停牌或数据延迟")
            return result

        # ============ 1. 关键价位计算 ============
        ind = tech.get("indicators", {}) or {}
        ma = ind.get("ma", {}) or {}
        boll = ind.get("boll", {}) or {}

        # 支撑/阻力位
        supports = []
        resistances = []
        for m in ["ma5", "ma10", "ma20", "ma60", "ma120", "ma250"]:
            v = ma.get(m)
            if v and v > 0:
                if v < current_price:
                    supports.append(v)
                else:
                    resistances.append(v)
        if boll.get("low") and boll["low"] < current_price:
            supports.append(boll["low"])
        if boll.get("up") and boll["up"] > current_price:
            resistances.append(boll["up"])

        nearest_support = max(supports) if supports else current_price * 0.92
        nearest_resistance = min(resistances) if resistances else current_price * 1.08

        # ============ 2. 建议买入/卖出/止损/止盈 ============
        # T+1模式：买入当天不能卖，安全边际要更高
        if comprehensive >= 70:  # 推荐及以上
            result["action"] = "buy"
            result["action_cn"] = "买入"
            # 买点：尽量回踩支撑附近，分激进+稳健
            buy_aggressive = round(current_price * 0.995, 3)
            buy_safe = round(nearest_support * 1.005, 3)
            result["buy_point"] = {
                "aggressive": buy_aggressive,
                "safe": min(buy_safe, buy_aggressive) if buy_safe else buy_aggressive,
                "description": f"激进价 {buy_aggressive} / 支撑回踩价 {buy_safe if buy_safe else '待确认'}",
            }
            # 止损：买入价下方 3%~5%，或跌破强支撑
            sl_pct = 0.05 if comprehensive >= 85 else 0.04
            stop_loss = round(buy_aggressive * (1 - sl_pct), 3)
            if nearest_support and nearest_support > stop_loss:
                stop_loss = round(nearest_support * 0.995, 3)
            result["stop_loss"] = stop_loss
            # 止盈：第一目标=前阻力位，第二目标=更高
            tp1 = round(nearest_resistance, 3)
            tp2 = round(max(tp1, buy_aggressive * 1.15), 3)
            result["take_profit"] = {
                "target1": tp1,
                "target2": tp2,
                "description": f"第一目标(阻力位){tp1}，第二目标(+15%){tp2}，建议分批止盈",
            }
            # 仓位
            if comprehensive >= 85:
                result["position_suggestion"] = "建议仓位 30%~40%（单只），组合总仓不超过70%"
                result["time_horizon"] = "持有 5~20 个交易日（短中线）"
            else:
                result["position_suggestion"] = "建议仓位 15%~25%（单只），控制总仓位"
                result["time_horizon"] = "持有 3~10 个交易日（短线）"

        elif comprehensive <= 40:  # 回避/卖出
            result["action"] = "sell"
            result["action_cn"] = "卖出/回避"
            sell_weak = round(current_price * 1.005, 3)
            sell_rush = round(nearest_resistance * 0.995, 3) if nearest_resistance else round(current_price * 1.03, 3)
            result["sell_point"] = {
                "rush_sell": sell_rush,
                "weak_sell": sell_weak,
                "description": f"反弹至 {sell_rush} 附近减仓；若跌破前低可直接止损离场",
            }

        else:  # 中性：观望
            result["action"] = "watch" if comprehensive < 55 else "hold"
            result["action_cn"] = "观望/持有"

        # ============ 3. 买入理由 ==========
        reasons_buy: List[str] = []
        if tech.get("breakdown", {}).get("ma_score", 0) >= 70:
            reasons_buy.append("均线多头排列，趋势向上")
        if tech.get("signals", {}).get("macd_golden_cross"):
            reasons_buy.append("MACD金叉，短期动能转强")
        if tech.get("signals", {}).get("ma_golden_cross"):
            reasons_buy.append("MA5上穿MA20金叉")
        rsi_v = tech.get("indicators", {}).get("rsi", 50)
        if 30 <= rsi_v <= 55:
            reasons_buy.append(f"RSI={rsi_v:.1f}，处于相对低位，反弹概率大")
        # 基本面（评分结果来自fundamental_result.breakdown）
        prof_break = fund.get("breakdown", {})
        if prof_break.get("profitability_score", 0) >= 70:
            reasons_buy.append("盈利能力优秀（ROE/净利率较高）")
        if prof_break.get("growth_score", 0) >= 70:
            reasons_buy.append("营收与利润双高增长")
        if prof_break.get("valuation_score", 0) >= 70:
            reasons_buy.append("估值处于合理偏低区间")
        # 情绪面
        if senti.get("news_summary", {}).get("avg_score", 0) >= 0.1:
            reasons_buy.append("新闻面整体偏正向")
        chg = snapshot.get("change_pct", 0) or 0
        if -2 <= chg <= 3:
            reasons_buy.append(f"当日波动适中（{chg:+.2f}%），T+1次日有较好空间")

        # ============ 4. 卖出/风险理由 ==========
        reasons_sell: List[str] = []
        risks: List[str] = []
        if tech.get("breakdown", {}).get("ma_score", 0) <= 35:
            reasons_sell.append("均线空头排列，趋势承压")
        if tech.get("signals", {}).get("macd_death_cross"):
            reasons_sell.append("MACD死叉，短期动能转弱")
        if tech.get("signals", {}).get("ma_death_cross"):
            reasons_sell.append("MA5下穿MA20死叉")
        if rsi_v and rsi_v >= 75:
            reasons_sell.append(f"RSI={rsi_v:.1f} 超买，短期回调概率大")
        if prof_break.get("solvency_score", 0) <= 35:
            risks.append("偿债指标偏弱，财务风险偏大")
        if prof_break.get("valuation_score", 0) <= 30:
            risks.append("估值偏高（PE/PB过高），需警惕杀估值")
        if senti.get("news_summary", {}).get("avg_score", 0) <= -0.1:
            risks.append("近期新闻偏负面，注意消息面风险")
        if senti.get("ann_summary", {}).get("avg_score", 0) <= -0.1:
            risks.append("近期公告偏负面")
        if chg >= 7:
            risks.append(f"当日涨幅 {chg:+.2f}% 过大，T+1追高容易次日被闷杀，不建议追涨")
        if chg <= -5:
            risks.append(f"当日跌幅 {chg:+.2f}%，可能有利空，需先确认止跌再进场")

        result["reasons_buy"] = reasons_buy
        result["reasons_sell"] = reasons_sell
        result["risk_warnings"] = (result["risk_warnings"] or []) + risks

        # ============ 5. T+1特别提醒 ============
        result["t1_tips"] = [
            "A股/ETF为T+1交易：今日买入，下一交易日方可卖出",
            "买入前务必设置止损价并严格执行",
            "建议分批建仓，如先 1/2 仓位，若再回踩支撑再加 1/2",
            "盈利超过 8% 可考虑先止盈一半，锁定利润",
        ]
        return result


_buy_sell_analyzer: Optional[BuySellAnalyzer] = None

def get_buy_sell_analyzer() -> BuySellAnalyzer:
    global _buy_sell_analyzer
    if _buy_sell_analyzer is None:
        _buy_sell_analyzer = BuySellAnalyzer()
    return _buy_sell_analyzer
