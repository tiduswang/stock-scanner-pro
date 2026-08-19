"""
行情数据服务（DB优先 + 多数据源回退）
- 日K线优先从本地DB读取（极速），DB缺失时多源拉取并回写
- 实时快照采用"全市场批量拉取→写DB→单只从DB读"策略，避免逐只拉全市场
- 全部经过多数据源重试+自动切换
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Literal

import pandas as pd

from backend.utils.logger import log
from backend.utils.cache import cached
from backend.db.session import get_session, db_engine
from backend.db.models import DailyKline, RealtimeSnapshot
from backend.services.data.sources import get_fetcher

MarketType = Literal["A", "HK", "ETF"]
KlinePeriod = Literal["daily", "weekly", "monthly"]

# 快照过期时间（秒）—— 盘中5分钟内复用DB缓存
_SNAPSHOT_TTL = 300
# 全市场快照内存刷新标记（避免频繁全量拉取）
_last_full_snapshot_time: Dict[str, float] = {}  # market -> timestamp
_SNAPSHOT_LOCK = threading.Lock()


class MarketDataService:
    """行情数据获取服务（DB优先 + 多源回退）"""

    def __init__(self):
        self._fetcher = get_fetcher()

    def _normalize_a_code(self, code: str) -> str:
        return str(code).zfill(6)

    def _detect_market(self, code: str, market: Optional[MarketType]) -> MarketType:
        if market:
            return market
        code = str(code)
        if len(code) == 5:
            return "HK"
        if code.startswith(("510", "511", "512", "513", "515", "516", "518", "56", "58", "159", "161")):
            return "ETF"
        return "A"

    # ============ K线：DB优先 ============
    def _get_kline_from_db(self, code: str, days: int) -> pd.DataFrame:
        """从DB读取K线"""
        try:
            with get_session() as s:
                rows = s.query(DailyKline).filter(
                    DailyKline.code == code
                ).order_by(DailyKline.trade_date.desc()).limit(days).all()
                if not rows:
                    return pd.DataFrame()
                data = [{
                    "date": r.trade_date, "open": r.open, "close": r.close,
                    "high": r.high, "low": r.low, "volume": r.volume, "turnover": r.turnover
                } for r in reversed(rows)]
                return pd.DataFrame(data)
        except Exception as e:
            log.warning(f"[行情] DB读取K线失败 {code}: {e}")
            return pd.DataFrame()

    def _save_kline_to_db(self, code: str, market: str, df: pd.DataFrame):
        """将K线写入DB（增量更新）"""
        if df is None or df.empty:
            return
        try:
            with get_session() as s:
                for _, r in df.iterrows():
                    trade_date = str(r.get("trade_date", r.get("date", "")))
                    if not trade_date:
                        continue
                    # 检查是否已存在
                    existing = s.query(DailyKline).filter(
                        DailyKline.code == code, DailyKline.trade_date == trade_date
                    ).first()
                    if existing:
                        existing.open = float(r.get("open", 0))
                        existing.close = float(r.get("close", 0))
                        existing.high = float(r.get("high", 0))
                        existing.low = float(r.get("low", 0))
                        existing.volume = float(r.get("volume", 0))
                        existing.turnover = float(r.get("turnover", 0))
                    else:
                        s.add(DailyKline(
                            code=code, market=market, trade_date=trade_date,
                            open=float(r.get("open", 0)), close=float(r.get("close", 0)),
                            high=float(r.get("high", 0)), low=float(r.get("low", 0)),
                            volume=float(r.get("volume", 0)), turnover=float(r.get("turnover", 0)),
                        ))
            log.debug(f"[行情] K线已写入DB {code}: {len(df)} 条")
        except Exception as e:
            log.error(f"[行情] DB写入K线失败 {code}: {e}")

    @cached("market", "kline")
    def get_kline(self, code: str, market: Optional[MarketType] = None,
                  period: KlinePeriod = "daily", days: int = 365) -> pd.DataFrame:
        """获取K线数据（DB优先 → 多源回退）"""
        market = self._detect_market(code, market)
        code = self._normalize_a_code(code) if market != "HK" else str(code)

        # 1. 先查DB
        df_db = self._get_kline_from_db(code, days)
        if not df_db.empty and len(df_db) >= days * 0.8:
            # DB数据足够，检查最新日期是否近期
            latest_date = df_db.iloc[-1]["date"] if "date" in df_db.columns else ""
            # 如果有近期数据（最近7天内），直接返回
            if latest_date:
                try:
                    ld = datetime.strptime(latest_date, "%Y-%m-%d")
                    if (datetime.now() - ld).days <= 7:
                        log.debug(f"[行情] K线命中DB {code}: {len(df_db)} 条")
                        return df_db.tail(days).reset_index(drop=True)
                except ValueError:
                    pass

        # 2. DB不足或过期，多源拉取
        log.debug(f"[行情] DB不足，多源拉取 {market} {code} {period}")
        raw = self._fetcher.fetch_kline(code, market, period)
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "turnover"])

        # 3. 统一列名
        df = self._fetcher.normalize_kline(raw)
        if df.empty:
            return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "turnover"])

        # 4. 写回DB（仅日线缓存，周/月线不缓存）
        if period == "daily":
            self._save_kline_to_db(code, market, df)

        # 5. 返回最近N天
        df = df.tail(days).reset_index(drop=True)
        df = df.rename(columns={"trade_date": "date"})
        return df

    # ============ 实时快照：全市场批量 → DB → 单只读 ============
    def _refresh_full_snapshot(self, market: MarketType):
        """一次性拉取全市场快照写入DB"""
        with _SNAPSHOT_LOCK:
            # 5分钟内已刷新过，跳过
            last = _last_full_snapshot_time.get(market, 0)
            if time.time() - last < _SNAPSHOT_TTL:
                return
            log.info(f"[行情] 刷新{market}全市场快照...")
            try:
                raw_df = self._fetcher.fetch_all_snapshot(market)
                if raw_df is None or raw_df.empty:
                    log.warning(f"[行情] {market}全量快照拉取失败")
                    return
                items = self._fetcher.normalize_snapshot(raw_df, market)
                if not items:
                    return
                # 批量写DB
                with get_session() as s:
                    for item in items:
                        code = item.get("code", "")
                        if not code:
                            continue
                        existing = s.query(RealtimeSnapshot).filter(
                            RealtimeSnapshot.code == code
                        ).first()
                        if existing:
                            for k, v in item.items():
                                if k != "code" and hasattr(existing, k):
                                    setattr(existing, k, v)
                            existing.updated_at = datetime.utcnow()
                        else:
                            s.add(RealtimeSnapshot(**item))
                _last_full_snapshot_time[market] = time.time()
                log.info(f"[行情] {market}全市场快照已刷新: {len(items)} 只")
            except Exception as e:
                log.error(f"[行情] 刷新{market}全量快照失败: {e}")

    def _get_snapshot_from_db(self, code: str) -> Optional[Dict]:
        """从DB读取单只快照（检查过期）"""
        try:
            with get_session() as s:
                row = s.query(RealtimeSnapshot).filter(RealtimeSnapshot.code == code).first()
                if row is None:
                    return None
                # 检查是否过期
                if row.updated_at and (datetime.utcnow() - row.updated_at).total_seconds() > _SNAPSHOT_TTL:
                    return None
                return row.to_dict()
        except Exception as e:
            log.warning(f"[行情] DB读取快照失败 {code}: {e}")
            return None

    @cached("market", "snapshot")
    def get_realtime_snapshot(self, code: str, market: Optional[MarketType] = None) -> Dict:
        """获取单只股票实时快照（DB优先 → 全市场批量刷新 → DB读）"""
        market = self._detect_market(code, market)
        code = self._normalize_a_code(code) if market != "HK" else str(code)

        # 1. 先查DB
        snap = self._get_snapshot_from_db(code)
        if snap:
            return snap

        # 2. DB未命中或过期，触发全市场刷新（5分钟内只拉一次）
        self._refresh_full_snapshot(market)
        # 3. 再从DB读
        snap = self._get_snapshot_from_db(code)
        if snap:
            return snap

        # 4. 兜底：直接单只拉取（极少走到这）
        log.debug(f"[行情] 全市场快照未覆盖 {code}，直接单只拉取")
        return self._fetch_single_snapshot(code, market)

    def _fetch_single_snapshot(self, code: str, market: MarketType) -> Dict:
        """单只快照兜底（全市场快照失败时的fallback）"""
        try:
            raw_df = self._fetcher.fetch_all_snapshot(market)
            if raw_df is None or raw_df.empty:
                return {}
            items = self._fetcher.normalize_snapshot(raw_df, market)
            for item in items:
                if item.get("code") == code:
                    # 写DB
                    try:
                        with get_session() as s:
                            existing = s.query(RealtimeSnapshot).filter(
                                RealtimeSnapshot.code == code
                            ).first()
                            if existing:
                                for k, v in item.items():
                                    if k != "code" and hasattr(existing, k):
                                        setattr(existing, k, v)
                            else:
                                s.add(RealtimeSnapshot(**item))
                    except Exception:
                        pass
                    return item
        except Exception as e:
            log.error(f"[行情] 单只快照兜底失败 {code}: {e}")
        return {}


# 单例
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service
