"""
扫描进度追踪器
- 当前进度百分比
- 已处理/总数
- 预计剩余时间
- 阶段日志
"""
import time
import threading
import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from backend.utils.logger import log


@dataclass
class ScanProgress:
    """扫描进度数据结构"""
    scan_id: str = ""
    status: str = "pending"   # pending / running / paused / done / error
    total: int = 0
    processed: int = 0
    failed: int = 0
    passed_filter: int = 0     # 初筛通过数量
    current_code: str = ""
    current_stage: str = "准备中"
    stage_log: List[Dict] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    elapsed_sec: float = 0.0
    eta_sec: float = 0.0       # 预计剩余时间(秒)
    eta_text: str = ""
    speed_per_sec: float = 0.0  # 每秒处理数量
    results: List[Dict] = field(default_factory=list)
    error_msg: str = ""

    def to_dict(self):
        d = asdict(self)
        d["eta_text"] = self._format_eta(self.eta_sec)
        d["elapsed_text"] = self._format_time(self.elapsed_sec)
        d["progress_pct"] = round((self.processed / self.total) * 100, 2) if self.total else 0
        return d

    @staticmethod
    def _format_time(sec: float) -> str:
        if sec <= 0:
            return "0秒"
        sec = int(sec)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        parts = []
        if h:
            parts.append(f"{h}小时")
        if m:
            parts.append(f"{m}分")
        parts.append(f"{s}秒")
        return "".join(parts)

    def _format_eta(self, sec: float) -> str:
        if self.status == "done":
            return "已完成"
        if self.status == "error":
            return "错误中止"
        if sec <= 0 or self.speed_per_sec <= 0:
            return "估算中..."
        return f"预计还需 {self._format_time(sec)}"


class ProgressTracker:
    """全局扫描进度追踪器（线程安全）"""

    def __init__(self):
        self._progresses: Dict[str, ScanProgress] = {}
        self._lock = threading.RLock()
        self._listeners: Dict[str, List[Callable]] = {}  # scan_id -> callbacks

    def create_scan(self, total: int, desc: str = "扫描") -> str:
        scan_id = uuid.uuid4().hex[:12]
        with self._lock:
            p = ScanProgress(
                scan_id=scan_id,
                status="pending",
                total=max(total, 1),
                start_time=time.time(),
            )
            p.stage_log.append({"time": time.strftime("%H:%M:%S"), "msg": f"【开始】{desc}，共 {total} 只标的"})
            self._progresses[scan_id] = p
        log.info(f"[进度] 创建扫描 {scan_id}, 总数={total}")
        return scan_id

    def start(self, scan_id: str):
        with self._lock:
            p = self._progresses.get(scan_id)
            if p:
                p.status = "running"
                p.stage_log.append({"time": time.strftime("%H:%M:%S"), "msg": "开始分析..."})

    def update(self, scan_id: str, code: str, name: str = "", passed: bool = True,
               stage: str = "", failed: bool = False):
        with self._lock:
            p = self._progresses.get(scan_id)
            if not p:
                return
            p.current_code = code
            if stage:
                p.current_stage = stage
            p.processed += 1
            if passed:
                p.passed_filter += 1
            if failed:
                p.failed += 1
            # 时间计算
            p.elapsed_sec = time.time() - p.start_time
            if p.processed > 0:
                p.speed_per_sec = p.processed / p.elapsed_sec if p.elapsed_sec > 0 else 0
                remaining = p.total - p.processed
                p.eta_sec = remaining / p.speed_per_sec if p.speed_per_sec > 0 else 0
            # 阶段日志（每5%或有事件记一次）
            pct = (p.processed / p.total) * 100 if p.total else 0
            if p.processed % max(1, p.total // 20) == 0 or pct >= 100:
                p.stage_log.append({
                    "time": time.strftime("%H:%M:%S"),
                    "msg": f"进度 {pct:.1f}% ({p.processed}/{p.total}) 已通过筛选 {p.passed_filter} 只",
                })
            self._notify(scan_id, p)

    def append_result(self, scan_id: str, result_item: Dict):
        with self._lock:
            p = self._progresses.get(scan_id)
            if p:
                p.results.append(result_item)

    def log(self, scan_id: str, msg: str):
        with self._lock:
            p = self._progresses.get(scan_id)
            if p:
                p.stage_log.append({"time": time.strftime("%H:%M:%S"), "msg": msg})
                self._notify(scan_id, p)

    def finish(self, scan_id: str, status: str = "done", error_msg: str = ""):
        with self._lock:
            p = self._progresses.get(scan_id)
            if not p:
                return
            p.status = status
            p.end_time = time.time()
            p.elapsed_sec = p.end_time - p.start_time
            p.eta_sec = 0
            if error_msg:
                p.error_msg = error_msg
            msg_map = {
                "done": f"【完成】总耗时 {ScanProgress._format_time(p.elapsed_sec)}，初筛通过 {p.passed_filter} 只，失败 {p.failed} 只",
                "error": f"【异常】{error_msg}",
                "paused": "【暂停】",
            }
            p.stage_log.append({"time": time.strftime("%H:%M:%S"), "msg": msg_map.get(status, "")})
            self._notify(scan_id, p)
        log.info(f"[进度] 扫描 {scan_id} {status}")

    def get(self, scan_id: str) -> Optional[Dict]:
        with self._lock:
            p = self._progresses.get(scan_id)
            return p.to_dict() if p else None

    def _notify(self, scan_id: str, p: ScanProgress):
        cbs = self._listeners.get(scan_id, [])
        d = p.to_dict()
        for cb in cbs:
            try:
                cb(d)
            except Exception as e:
                log.debug(f"[进度] 监听器异常: {e}")

    def add_listener(self, scan_id: str, cb: Callable):
        with self._lock:
            self._listeners.setdefault(scan_id, []).append(cb)


# 单例
_tracker: Optional[ProgressTracker] = None

def get_progress_tracker() -> ProgressTracker:
    global _tracker
    if _tracker is None:
        _tracker = ProgressTracker()
    return _tracker
