"""
数据同步服务
- 收盘后一次性全市场批量拉取日线存入本地DB
- 股票列表/实时快照同步
- 进度追踪（total/processed/eta/stage）
- 多线程并发拉取（可配置并发数）
"""
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.utils.logger import log
from backend.config import get_settings
from backend.db.session import get_session
from backend.db.models import Stock, DailyKline, RealtimeSnapshot, SyncLog
from backend.services.data.sources import get_fetcher
from backend.services.data.stock_list import get_stock_list_service

MarketType = Literal["A", "HK", "ETF"]


class SyncState:
    """同步进度状态（内存）"""
    def __init__(self):
        self.status: str = "idle"  # idle/running/done/error
        self.sync_type: str = ""
        self.markets: List[str] = []
        self.total: int = 0
        self.processed: int = 0
        self.success: int = 0
        self.failed: int = 0
        self.current_stage: str = ""
        self.started_at: float = 0
        self.eta_text: str = ""
        self.error_msg: str = ""

    def to_dict(self) -> Dict:
        elapsed = time.time() - self.started_at if self.started_at and self.status == "running" else 0
        pct = round(self.processed / self.total * 100, 1) if self.total > 0 else 0
        speed = self.processed / elapsed if elapsed > 1 else 0
        remaining = (self.total - self.processed) / speed if speed > 0.01 else 0
        if remaining > 0:
            if remaining > 60:
                eta = f"约{int(remaining/60)}分钟"
            else:
                eta = f"约{int(remaining)}秒"
        else:
            eta = ""
        return {
            "status": self.status,
            "sync_type": self.sync_type,
            "markets": self.markets,
            "total": self.total,
            "processed": self.processed,
            "success": self.success,
            "failed": self.failed,
            "progress_pct": pct,
            "current_stage": self.current_stage,
            "eta_text": eta,
            "elapsed": round(elapsed, 1),
            "speed_per_sec": round(speed, 2),
        }


class DataSyncService:
    """数据同步服务（单例）"""

    def __init__(self):
        self._fetcher = get_fetcher()
        self._stock_list = get_stock_list_service()
        self._settings = get_settings()
        self._state = SyncState()
        self._lock = threading.Lock()

    @property
    def state(self) -> SyncState:
        return self._state

    def get_status(self) -> Dict:
        return self._state.to_dict()

    # ============ 同步股票列表 ============
    def sync_stock_list(self, markets: List[str]) -> str:
        """同步股票列表到DB（后台线程）"""
        with self._lock:
            if self._state.status == "running":
                return "已有同步任务在运行"
            self._state = SyncState()
            self._state.status = "running"
            self._state.sync_type = "stock_list"
            self._state.markets = markets
            self._state.started_at = time.time()
            self._state.total = len(markets)
            self._state.current_stage = "同步股票列表..."

        t = threading.Thread(target=self._run_stock_list_sync, args=(markets,), daemon=True)
        t.start()
        return "started"

    def _run_stock_list_sync(self, markets: List[str]):
        try:
            for m in markets:
                self._state.current_stage = f"同步{m}股列表..."
                df = self._stock_list.get_market_list(m)  # DB优先，miss会拉取并写DB
                # 强制刷新：清除内存缓存，直接从远程拉
                from backend.utils.cache import get_cache
                get_cache("stock_list").clear()
                df = self._fetcher.fetch_market_list(m)
                if not df.empty:
                    self._stock_list._save_to_db(df, m)
                with self._lock:
                    self._state.processed += 1
                    if not df.empty:
                        self._state.success += 1
                    else:
                        self._state.failed += 1
            self._state.status = "done"
            self._state.current_stage = "股票列表同步完成"
            self._log_sync("stock_list", markets)
        except Exception as e:
            log.error(f"[同步] 股票列表同步失败: {e}")
            self._state.status = "error"
            self._state.error_msg = str(e)

    # ============ 同步全市场日线 ============
    def sync_daily_klines(self, markets: List[str], days: int = 365) -> str:
        """批量拉取全市场日线存DB（后台线程，多线程并发）"""
        with self._lock:
            if self._state.status == "running":
                return "已有同步任务在运行"
            self._state = SyncState()
            self._state.status = "running"
            self._state.sync_type = "daily_kline"
            self._state.markets = markets
            self._state.started_at = time.time()
            self._state.current_stage = "构建股票池..."

        t = threading.Thread(target=self._run_kline_sync, args=(markets, days), daemon=True)
        t.start()
        return "started"

    def _run_kline_sync(self, markets: List[str], days: int):
        try:
            # 1. 构建股票池
            all_stocks: List[Dict] = []
            for m in markets:
                df = self._stock_list.get_market_list(m)
                if df.empty:
                    log.warning(f"[同步] {m}列表为空，跳过")
                    continue
                for _, r in df.iterrows():
                    all_stocks.append({
                        "code": str(r.get("code", "")),
                        "name": str(r.get("name", "")),
                        "market": m,
                    })
            self._state.total = len(all_stocks)
            log.info(f"[同步] 日线同步: {len(all_stocks)} 只, 并发={self._settings.SYNC_MAX_WORKERS}")

            if not all_stocks:
                self._state.status = "done"
                self._state.current_stage = "无股票可同步"
                return

            # 2. 多线程拉取
            workers = max(1, min(self._settings.SYNC_MAX_WORKERS, 8))

            def _sync_one(item: Dict, days_n: int) -> bool:
                code = item["code"]
                market = item["market"]
                try:
                    raw = self._fetcher.fetch_kline(code, market, "daily")
                    if raw is None or raw.empty:
                        return False
                    df = self._fetcher.normalize_kline(raw)
                    if df.empty:
                        return False
                    # 只保留最近 days_n 天，减少DB写入量
                    if days_n and len(df) > days_n:
                        df = df.tail(days_n).copy()
                    # 增量写DB
                    self._save_klines_batch(code, market, df)
                    return True
                except Exception as e:
                    log.debug(f"[同步] {code} K线拉取失败: {e}")
                    return False

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_sync_one, item, days): item for item in all_stocks}
                for fut in as_completed(futures):
                    item = futures[fut]
                    try:
                        ok = fut.result()
                    except Exception:
                        ok = False
                    with self._lock:
                        self._state.processed += 1
                        if ok:
                            self._state.success += 1
                        else:
                            self._state.failed += 1
                        self._state.current_stage = f"同步: {item['name']}({item['code']})"

            self._state.status = "done"
            self._state.current_stage = f"日线同步完成: {self._state.success}/{self._state.total}"
            self._log_sync("daily_kline", markets)
        except Exception as e:
            log.error(f"[同步] 日线同步失败: {e}")
            self._state.status = "error"
            self._state.error_msg = str(e)

    def _save_klines_batch(self, code: str, market: str, df):
        """批量写K线到DB（增量）：先查已有日期集合，减少逐行查询"""
        try:
            with get_session() as s:
                # 一次性查出该 code 已有的交易日期集合
                existing_dates = set(
                    r[0] for r in s.query(DailyKline.trade_date).filter(DailyKline.code == code).all()
                )
                for _, r in df.iterrows():
                    trade_date = str(r.get("trade_date", ""))
                    if not trade_date:
                        continue
                    if trade_date in existing_dates:
                        # 已有则更新（按主键定位）
                        obj = s.query(DailyKline).filter(
                            DailyKline.code == code, DailyKline.trade_date == trade_date
                        ).first()
                        if obj:
                            obj.open = float(r.get("open", 0))
                            obj.close = float(r.get("close", 0))
                            obj.high = float(r.get("high", 0))
                            obj.low = float(r.get("low", 0))
                            obj.volume = float(r.get("volume", 0))
                            obj.turnover = float(r.get("turnover", 0))
                    else:
                        s.add(DailyKline(
                            code=code, market=market, trade_date=trade_date,
                            open=float(r.get("open", 0)), close=float(r.get("close", 0)),
                            high=float(r.get("high", 0)), low=float(r.get("low", 0)),
                            volume=float(r.get("volume", 0)), turnover=float(r.get("turnover", 0)),
                        ))
                        existing_dates.add(trade_date)
        except Exception as e:
            log.error(f"[同步] 批量写K线失败 {code}: {e}")

    # ============ 同步全市场快照 ============
    def sync_snapshots(self, markets: List[str]) -> str:
        """全市场实时快照批量拉取存DB"""
        with self._lock:
            if self._state.status == "running":
                return "已有同步任务在运行"
            self._state = SyncState()
            self._state.status = "running"
            self._state.sync_type = "snapshot"
            self._state.markets = markets
            self._state.total = len(markets)
            self._state.started_at = time.time()
            self._state.current_stage = "拉取全市场快照..."

        t = threading.Thread(target=self._run_snapshot_sync, args=(markets,), daemon=True)
        t.start()
        return "started"

    def _run_snapshot_sync(self, markets: List[str]):
        try:
            for m in markets:
                self._state.current_stage = f"拉取{m}全市场快照..."
                try:
                    raw_df = self._fetcher.fetch_all_snapshot(m)
                    if raw_df is None or raw_df.empty:
                        log.warning(f"[同步] {m}快照拉取失败")
                        with self._lock:
                            self._state.processed += 1
                            self._state.failed += 1
                        continue
                    items = self._fetcher.normalize_snapshot(raw_df, m)
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
                    with self._lock:
                        self._state.processed += 1
                        self._state.success += 1
                    self._state.current_stage = f"{m}快照已同步: {len(items)} 只"
                except Exception as e:
                    log.error(f"[同步] {m}快照同步失败: {e}")
                    with self._lock:
                        self._state.processed += 1
                        self._state.failed += 1
            self._state.status = "done"
            self._state.current_stage = "快照同步完成"
            self._log_sync("snapshot", markets)
        except Exception as e:
            log.error(f"[同步] 快照同步失败: {e}")
            self._state.status = "error"
            self._state.error_msg = str(e)

    def _log_sync(self, sync_type: str, markets: List[str]):
        """记录同步日志到DB"""
        try:
            with get_session() as s:
                s.add(SyncLog(
                    sync_type=sync_type,
                    market=",".join(markets),
                    total=self._state.total,
                    processed=self._state.processed,
                    success=self._state.success,
                    failed=self._state.failed,
                    status=self._state.status,
                    error_msg=self._state.error_msg,
                    finished_at=datetime.utcnow(),
                ))
        except Exception:
            pass


# 单例
_sync_service: Optional[DataSyncService] = None


def get_sync_service() -> DataSyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = DataSyncService()
    return _sync_service
