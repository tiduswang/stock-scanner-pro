"""
技术面分析模块
- 均线 (MA5/10/20/60/120/250)
- MACD / RSI / KDJ / BOLL
- 成交量/量价配合
- 趋势判断、金叉死叉
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from backend.utils.logger import log


class TechnicalAnalyzer:
    """技术面分析器"""

    def analyze(self, kline: pd.DataFrame, params: Optional[Dict] = None) -> Dict:
        """
        执行技术面分析
        params: 可调参数（用户从前端调节）
        """
        if kline is None or len(kline) < 20:
            return {"error": "K线数据不足（至少20根）", "score": 0.0, "signals": {}}

        df = kline.copy()
        # 默认参数（可由params覆盖）
        p = {
            "ma_short": 5,
            "ma_mid": 20,
            "ma_long": 60,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "boll_period": 20,
            "boll_std": 2,
        }
        if params:
            p.update(params)

        result = {
            "indicators": {},
            "signals": {},
            "score": 50.0,  # 基础分
            "breakdown": {}
        }

        try:
            # ==== 1. 均线 ====
            df["ma5"] = df["close"].rolling(p["ma_short"]).mean()
            df["ma10"] = df["close"].rolling(10).mean()
            df["ma20"] = df["close"].rolling(p["ma_mid"]).mean()
            df["ma60"] = df["close"].rolling(p["ma_long"]).mean()
            df["ma120"] = df["close"].rolling(120).mean()
            df["ma250"] = df["close"].rolling(250).mean()

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) >= 2 else latest

            result["indicators"]["ma"] = {
                "ma5": self._r(latest.get("ma5")),
                "ma10": self._r(latest.get("ma10")),
                "ma20": self._r(latest.get("ma20")),
                "ma60": self._r(latest.get("ma60")),
                "ma120": self._r(latest.get("ma120")),
                "ma250": self._r(latest.get("ma250")),
            }

            # 均线多头发散评分
            ma_score = 0
            price = latest["close"]
            if price > latest.get("ma5", -1): ma_score += 4
            if price > latest.get("ma20", -1): ma_score += 6
            if price > latest.get("ma60", -1): ma_score += 8
            if latest.get("ma5", 0) > latest.get("ma20", 0): ma_score += 5
            if latest.get("ma20", 0) > latest.get("ma60", 0): ma_score += 5
            # 金叉死叉
            golden_cross = (prev.get("ma5", 0) <= prev.get("ma20", 0)) and (latest.get("ma5", 0) > latest.get("ma20", 0))
            death_cross = (prev.get("ma5", 0) >= prev.get("ma20", 0)) and (latest.get("ma5", 0) < latest.get("ma20", 0))
            result["signals"]["ma_golden_cross"] = bool(golden_cross)
            result["signals"]["ma_death_cross"] = bool(death_cross)
            if golden_cross: ma_score += 15
            if death_cross: ma_score -= 15
            result["breakdown"]["ma_score"] = max(0, min(100, ma_score + 40))

            # ==== 2. MACD ====
            exp1 = df["close"].ewm(span=p["macd_fast"], adjust=False).mean()
            exp2 = df["close"].ewm(span=p["macd_slow"], adjust=False).mean()
            df["dif"] = exp1 - exp2
            df["dea"] = df["dif"].ewm(span=p["macd_signal"], adjust=False).mean()
            df["macd"] = 2 * (df["dif"] - df["dea"])

            latest_macd = df.iloc[-1]
            prev_macd = df.iloc[-2] if len(df) >= 2 else latest_macd
            result["indicators"]["macd"] = {
                "dif": self._r(latest_macd["dif"]),
                "dea": self._r(latest_macd["dea"]),
                "macd": self._r(latest_macd["macd"]),
            }
            macd_score = 50
            if latest_macd["dif"] > latest_macd["dea"]: macd_score += 15
            if latest_macd["dif"] > 0: macd_score += 10
            if (prev_macd["dif"] <= prev_macd["dea"]) and (latest_macd["dif"] > latest_macd["dea"]):
                macd_score += 20  # MACD金叉
            if (prev_macd["dif"] >= prev_macd["dea"]) and (latest_macd["dif"] < latest_macd["dea"]):
                macd_score -= 20  # MACD死叉
            result["signals"]["macd_golden_cross"] = bool((prev_macd["dif"] <= prev_macd["dea"]) and (latest_macd["dif"] > latest_macd["dea"]))
            result["signals"]["macd_death_cross"] = bool((prev_macd["dif"] >= prev_macd["dea"]) and (latest_macd["dif"] < latest_macd["dea"]))
            result["breakdown"]["macd_score"] = max(0, min(100, macd_score))

            # ==== 3. RSI ====
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=p["rsi_period"]).mean()
            avg_loss = loss.rolling(window=p["rsi_period"]).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            df["rsi"] = 100 - (100 / (1 + rs))
            rsi_val = float(df["rsi"].iloc[-1]) if pd.notna(df["rsi"].iloc[-1]) else 50
            result["indicators"]["rsi"] = self._r(rsi_val)
            # RSI评分：30-70中性，<30超买加分，>70超卖减分
            if rsi_val < p["rsi_oversold"]:
                rsi_score = 85  # 超卖反弹
            elif rsi_val > p["rsi_overbought"]:
                rsi_score = 25  # 超买回调
            else:
                rsi_score = 50 + (rsi_val - 50) * 0.5  # 区间内线性
            result["breakdown"]["rsi_score"] = max(0, min(100, rsi_score))

            # ==== 4. 布林带 ====
            df["boll_mid"] = df["close"].rolling(p["boll_period"]).mean()
            df["boll_std"] = df["close"].rolling(p["boll_period"]).std()
            df["boll_up"] = df["boll_mid"] + p["boll_std"] * df["boll_std"]
            df["boll_low"] = df["boll_mid"] - p["boll_std"] * df["boll_std"]
            boll_latest = df.iloc[-1]
            result["indicators"]["boll"] = {
                "up": self._r(boll_latest.get("boll_up")),
                "mid": self._r(boll_latest.get("boll_mid")),
                "low": self._r(boll_latest.get("boll_low")),
            }
            # 位置评分：在下轨附近高分，上轨附近低分
            boll_w = (boll_latest.get("boll_up", 0) - boll_latest.get("boll_low", 0)) or 1
            boll_pos = (price - boll_latest.get("boll_low", 0)) / boll_w  # 0~1
            boll_score = (1 - boll_pos) * 100
            result["breakdown"]["boll_score"] = max(0, min(100, boll_score))

            # ==== 5. 量价配合 ====
            df["vol_ma5"] = df["volume"].rolling(5).mean()
            df["vol_ma20"] = df["volume"].rolling(20).mean()
            vol_ratio = float(latest["volume"] / latest.get("vol_ma20", latest["volume"])) if latest.get("vol_ma20", 0) > 0 else 1
            price_change = (latest["close"] - latest.get("open", latest["close"])) / (latest.get("open", 1) or 1) * 100
            result["indicators"]["volume"] = {
                "volume": self._r(latest["volume"]),
                "vol_ratio": self._r(vol_ratio),
                "vol_ma5": self._r(latest.get("vol_ma5")),
                "vol_ma20": self._r(latest.get("vol_ma20")),
            }
            # 量价评分：放量上涨加分，放量下跌减分
            vol_score = 50
            if price_change > 0 and vol_ratio > 1.2:
                vol_score = 80
            elif price_change < 0 and vol_ratio > 1.2:
                vol_score = 20
            elif price_change > 0:
                vol_score = 60
            elif price_change < 0:
                vol_score = 40
            result["breakdown"]["volume_score"] = max(0, min(100, vol_score))

            # ==== 6. 趋势 ====
            if latest.get("ma20", 0) > latest.get("ma60", 0) > latest.get("ma120", 0):
                trend = "bull"
                trend_score = 80
            elif latest.get("ma20", 0) < latest.get("ma60", 0) < latest.get("ma120", 0):
                trend = "bear"
                trend_score = 25
            else:
                trend = "neutral"
                trend_score = 50
            result["indicators"]["trend"] = trend
            result["breakdown"]["trend_score"] = trend_score

            # ==== 汇总技术面总分（加权）====
            weights = {
                "ma_score": 0.22,
                "macd_score": 0.22,
                "rsi_score": 0.16,
                "boll_score": 0.15,
                "volume_score": 0.15,
                "trend_score": 0.10,
            }
            total = 0.0
            for k, w in weights.items():
                total += result["breakdown"].get(k, 50) * w
            result["score"] = round(total, 2)

        except Exception as e:
            log.error(f"[技术面] 分析失败: {e}")
            result["error"] = str(e)

        return result

    @staticmethod
    def _r(v) -> Optional[float]:
        try:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return None
            return round(float(v), 4)
        except Exception:
            return None


# 单例
_technical_analyzer: Optional[TechnicalAnalyzer] = None


def get_technical_analyzer() -> TechnicalAnalyzer:
    global _technical_analyzer
    if _technical_analyzer is None:
        _technical_analyzer = TechnicalAnalyzer()
    return _technical_analyzer
