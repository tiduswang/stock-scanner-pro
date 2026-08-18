"""
基础选股扫描器
- 支持分市场扫描（A股/港股/ETF）
- 支持批量代码/板块扫描
- 支持初筛阈值（得分阈值过滤）
- 支持多线程并发（可配置并发数）
- 进度实时上报
"""
import time
import threading
from typing import Dict, List, Optional, Literal, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.config import MARKET_TYPES, A_SHARE_SECTORS
from backend.utils.logger import log
from backend.services.data.stock_list import get_stock_list_service
from backend.services.analysis.scoring import get_scoring_engine
from backend.services.analysis.buy_sell import get_buy_sell_analyzer
from backend.services.scanner.progress import get_progress_tracker

MarketType = Literal["A", "HK", "ETF"]


class ScanRequest:
    """扫描请求参数"""
    def __init__(self,
                 markets: Optional[List[MarketType]] = None,
                 stock_codes: Optional[List[str]] = None,
                 sector: Optional[str] = None,
                 score_threshold: int = 70,
                 top_n: int = 50,
                 weights: Optional[Dict] = None,
                 analysis_params: Optional[Dict] = None,
                 max_workers: int = 3,
                 include_buy_sell: bool = True):
        self.markets = markets or ["A"]
        self.stock_codes = stock_codes or []
        self.sector = sector
        self.score_threshold = score_threshold
        self.top_n = top_n
        self.weights = weights
        self.analysis_params = analysis_params
        self.max_workers = max(1, min(max_workers, 8))
        self.include_buy_sell = include_buy_sell


class BaseScanner:
    """基础选股扫描器"""

    def __init__(self):
        self.stock_list = get_stock_list_service()
        self.scoring = get_scoring_engine()
        self.buy_sell = get_buy_sell_analyzer()
        self.tracker = get_progress_tracker()

    # ============ 股票池构建 ============
    def _build_pool(self, req: ScanRequest) -> List[Dict]:
        """根据扫描参数构建待扫描股票池"""
        pool: List[Dict] = []

        # 1. 优先：用户指定了具体代码
        if req.stock_codes:
            # 根据代码推断市场，这里简化：对每个代码在所有市场列表里查找
            all_df = self.stock_list.get_all_list()
            for code in req.stock_codes:
                code_str = str(code).strip()
                # A股/ETF用 zfill
                a_code = code_str.zfill(6)
                row = all_df[all_df["code"] == code_str]
                if row.empty:
                    row = all_df[all_df["code"] == a_code]
                if not row.empty:
                    r = row.iloc[0]
                    pool.append({"code": r["code"], "name": r["name"], "market": r["market"]})
                else:
                    # fallback：当作A股，让后面的接口报错
                    pool.append({"code": a_code, "name": "", "market": "A"})
            log.info(f"[选股] 使用自定义股票池: {len(pool)} 只")
            return pool

        # 2. 其次：按板块扫描（仅A股支持较完善）
        if req.sector and req.sector in A_SHARE_SECTORS + ["所有板块"]:
            recs = []
            if req.sector == "所有板块":
                all_a = self.stock_list.get_a_share_list()
                recs = all_a.to_dict(orient="records")
            else:
                recs = self.stock_list.get_a_share_by_sector(req.sector)
            for r in recs:
                pool.append({"code": r["code"], "name": r.get("name", ""), "market": "A"})
            log.info(f"[选股] 板块 {req.sector}: {len(pool)} 只")
            return pool

        # 3. 按市场全扫
        for m in req.markets:
            df = self.stock_list.get_market_list(m)
            if df.empty:
                continue
            # 全量扫描太多 -> 这里默认限制（按成交额粗筛交给用户）
            limit = {"A": 300, "HK": 100, "ETF": 100}.get(m, 100)
            rows = df.head(limit).to_dict(orient="records")
            for r in rows:
                pool.append({"code": r["code"], "name": r.get("name", ""), "market": r.get("market", m)})
        log.info(f"[选股] 按市场 {req.markets} 构建股票池: {len(pool)} 只")
        return pool

    # ============ 执行扫描（异步SSE友好：启动后台线程，通过tracker取进度）============
    def start_scan(self, req: ScanRequest) -> str:
        """启动扫描，返回 scan_id，通过进度追踪器取状态"""
        pool = self._build_pool(req)
        total = len(pool)
        if total == 0:
            scan_id = self.tracker.create_scan(0)
            self.tracker.finish(scan_id, "error", "股票池为空，请调整筛选条件")
            return scan_id

        scan_id = self.tracker.create_scan(total, f"扫描{', '.join([MARKET_TYPES.get(m,m) for m in req.markets])}")

        # 后台执行
        t = threading.Thread(
            target=self._run_scan_thread,
            args=(scan_id, pool, req),
            daemon=True,
        )
        t.start()
        self.tracker.start(scan_id)
        return scan_id

    def _run_scan_thread(self, scan_id: str, pool: List[Dict], req: ScanRequest):
        """后台扫描线程：并发评分、结果过滤排序"""
        passed_items: List[Dict] = []

        def _work(item: Dict) -> Optional[Dict]:
            code = item["code"]
            name = item.get("name", "")
            market = item.get("market", "A")
            try:
                # 1. 评分
                score_res = self.scoring.score_stock(
                    code, market,
                    weights=req.weights,
                    analysis_params=req.analysis_params,
                )
                final_score = score_res.get("scores", {}).get("comprehensive_adjusted", 0)
                # 2. 初筛阈值
                passed = final_score >= req.score_threshold
                # 3. 买卖点（可选）
                buy_sell_res = {}
                if req.include_buy_sell and passed:
                    from backend.services.data.market_data import get_market_data_service
                    kline = get_market_data_service().get_kline(code, market, "daily", 365)
                    buy_sell_res = self.buy_sell.analyze(score_res, kline)
                return {
                    "code": code,
                    "name": name or score_res.get("name", ""),
                    "market": market,
                    "market_name": MARKET_TYPES.get(market, ""),
                    "score": round(final_score, 2),
                    "rating": score_res.get("rating", ""),
                    "rating_color": score_res.get("rating_color", ""),
                    "snapshot": score_res.get("snapshot", {}),
                    "scores": score_res.get("scores", {}),
                    "technical_summary": score_res.get("technical", {}).get("breakdown", {}),
                    "fundamental_summary": score_res.get("fundamental", {}).get("summary", []),
                    "sentiment_summary": score_res.get("sentiment", {}).get("summary_texts", []),
                    "buy_sell": buy_sell_res,
                    "_passed": passed,
                    "_full_score": score_res,
                }
            except Exception as e:
                log.debug(f"[选股] 处理 {code} 异常: {e}")
                return {"code": code, "name": name, "market": market, "_passed": False, "_failed": True, "_err": str(e)}

        try:
            with ThreadPoolExecutor(max_workers=req.max_workers) as pool_exec:
                fut_map = {pool_exec.submit(_work, item): item for item in pool}
                for fut in as_completed(fut_map):
                    item = fut_map[fut]
                    try:
                        result = fut.result() or {}
                    except Exception as e:
                        result = {"code": item["code"], "name": item.get("name", ""), "market": item.get("market", "A"), "_passed": False, "_failed": True, "_err": str(e)}
                    passed_flag = result.get("_passed", False)
                    failed_flag = result.get("_failed", False)
                    # 进度更新
                    self.tracker.update(
                        scan_id,
                        result.get("code", ""),
                        result.get("name", ""),
                        passed=passed_flag,
                        failed=failed_flag,
                        stage=f"正在分析: {result.get('name','')} ({result.get('code','')})",
                    )
                    # 只保留通过的
                    if passed_flag:
                        lite = {k: v for k, v in result.items() if not k.startswith("_")}
                        passed_items.append(lite)
                        self.tracker.append_result(scan_id, lite)
        except Exception as e:
            log.error(f"[选股] 扫描异常: {e}")
            self.tracker.finish(scan_id, "error", str(e))
            return

        # 排序并取前N
        passed_items.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_items = passed_items[: req.top_n]

        # 用排序后的替换results
        self.tracker._progresses[scan_id].results = top_items
        self.tracker.log(scan_id, f"【筛选】 {len(passed_items)} 只通过阈值 {req.score_threshold}，取前 {len(top_items)} 只输出")
        self.tracker.finish(scan_id, "done")


_base_scanner: Optional[BaseScanner] = None

def get_base_scanner() -> BaseScanner:
    global _base_scanner
    if _base_scanner is None:
        _base_scanner = BaseScanner()
    return _base_scanner
