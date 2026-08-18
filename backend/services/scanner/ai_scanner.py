"""
AI智能选股扫描器
- 调用本地Ollama模型
- 对初筛通过的股票进行AI深度分析
- 支持: 分市场扫描 / 自定义代码 / 板块 / 按评分阈值筛选后再深度分析
"""
import json
import time
import threading
from typing import Dict, List, Optional, Literal, Generator

import httpx
from backend.config import get_settings
from backend.utils.logger import log
from backend.services.scanner.base_scanner import BaseScanner, ScanRequest
from backend.services.scanner.progress import get_progress_tracker

MarketType = Literal["A", "HK", "ETF"]


class OllamaClient:
    """简化版 Ollama 客户端（支持流式）"""

    def __init__(self, base_url: str = None, model: str = None, timeout: int = None):
        s = get_settings()
        self.base_url = (base_url or s.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or s.OLLAMA_MODEL
        self.timeout = timeout or s.OLLAMA_TIMEOUT
        log.info(f"[Ollama] 初始化: {self.base_url}, model={self.model}")

    async def check_connection(self) -> Dict:
        """检查Ollama服务和模型可用性"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                # 1. 服务通不通
                r = await c.get(f"{self.base_url}/api/tags")
                if r.status_code != 200:
                    return {"ok": False, "msg": f"Ollama服务不可用: HTTP {r.status_code}"}
                data = r.json() or {}
                names = [m.get("name", "") for m in data.get("models", [])]
                # 2. 模型存在吗
                model_ok = any(self.model in n for n in names)
                return {
                    "ok": True,
                    "service": True,
                    "model_exists": model_ok,
                    "available_models": names,
                    "using_model": self.model,
                    "msg": "OK" if model_ok else f"模型 {self.model} 不存在，可用: {names[:8]}",
                }
        except Exception as e:
            return {"ok": False, "msg": f"连接Ollama失败: {e}"}

    def chat_sync(self, system_prompt: str, user_prompt: str) -> str:
        """同步非流式调用（简单场景）"""
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 4096},
        }
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(f"{self.base_url}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json() or {}
                return data.get("response", "") or ""
        except Exception as e:
            log.error(f"[Ollama] 生成失败: {e}")
            return f"[AI生成失败: {e}]"

    def chat_stream_sync(self, system_prompt: str, user_prompt: str) -> Generator[str, None, None]:
        """同步流式调用（逐token产出）"""
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": True,
            "options": {"temperature": 0.3, "num_ctx": 4096},
        }
        try:
            with httpx.Client(timeout=self.timeout) as c:
                with c.stream("POST", f"{self.base_url}/api/generate", json=payload) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            tok = d.get("response", "") or ""
                            if tok:
                                yield tok
                            if d.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            log.error(f"[Ollama] 流式生成失败: {e}")
            yield f"

[AI流式生成失败: {e}]"


class AIScanner:
    """AI选股：先基础扫描（过滤），再AI深度分析"""

    def __init__(self):
        self.base = BaseScanner()
        self.tracker = get_progress_tracker()

    def _ollama(self, custom_cfg: Optional[Dict] = None) -> OllamaClient:
        if custom_cfg:
            return OllamaClient(
                base_url=custom_cfg.get("base_url"),
                model=custom_cfg.get("model"),
                timeout=custom_cfg.get("timeout"),
            )
        return OllamaClient()

    # ============ 构建AI Prompt ============
    def _build_prompt(self, stock_results: List[Dict]) -> tuple:  # (system, user)
        system_prompt = """你是一位有10年经验的中国A股量化分析师，风格稳健、理性、注重风险收益比。请根据以下股票数据（技术面/基本面/情绪面评分+买入卖出建议），输出专业的AI深度分析：

要求：
1. 先给出【总览】：这批股票的整体印象、当前市场环境下的策略方向（短/中/长线）、仓位建议。
2. 再按分数从高到低对每只股票分别给出【个股解读】：
   - 一句话结论（看好/中性/回避）
   - 核心买入逻辑（3条以内）
   - 主要风险点（2条以内）
   - 操作建议（买入区/止损/止盈/持有期）
3. 最后给出【组合推荐】：从列表中选3~5只构建一个适合T+1交易的组合，给出每只权重分配和组合止损止盈方案。

注意：
- 严格基于提供的数据，不要编造未给出的数据（如未给PE就不要提具体PE值）。
- 强调A股T+1交易特性：当日买入次日方可卖出，避免追高、建议分批。
- 语言专业但易懂，尽量结构化输出。
- 所有评分：0-100分，85分以上=S/强烈推荐，75-85=A/推荐，65-75=B/中性偏多
"""

        # 精简版传给AI
        slim_list = []
        for s in stock_results:
            snapshot = s.get("snapshot", {}) or {}
            bs = s.get("buy_sell", {}) or {}
            slim = {
                "代码": s.get("code"),
                "名称": s.get("name"),
                "市场": s.get("market_name"),
                "综合评分": s.get("score"),
                "评级": s.get("rating"),
                "当前价": snapshot.get("price"),
                "涨跌幅%": snapshot.get("change_pct"),
                "技术面得分": s.get("scores", {}).get("technical"),
                "基本面得分": s.get("scores", {}).get("fundamental"),
                "情绪面得分": s.get("scores", {}).get("sentiment"),
                "建议操作": bs.get("action_cn"),
                "建议买入价": bs.get("buy_point", {}).get("description") if bs.get("buy_point") else None,
                "止损价": bs.get("stop_loss"),
                "止盈目标": bs.get("take_profit", {}).get("description") if bs.get("take_profit") else None,
                "买入理由": s.get("buy_sell", {}).get("reasons_buy", []),
                "风险提示": s.get("buy_sell", {}).get("risk_warnings", []) or s.get("buy_sell", {}).get("reasons_sell", []),
            }
            slim_list.append(slim)

        user_prompt = f"""以下是本次AI选股初筛通过的股票清单（共 {len(slim_list)} 只，按综合评分从高到低排序）：

{json.dumps(slim_list, ensure_ascii=False, indent=2)}

请按照系统提示格式输出深度分析报告。注意T+1交易约束和仓位管理。"""

        return system_prompt, user_prompt

    # ============ 启动AI扫描（先基础扫描 -> AI深度分析）============
    def start_ai_scan(self, req: ScanRequest,
                      ollama_cfg: Optional[Dict] = None,
                      mode: str = "after_filter") -> str:
        """
        启动AI选股扫描
        mode:
            "after_filter" - 先基础扫描（评分过滤），再对top N进行AI分析（默认，最快）
            "selected_only" - 对用户指定的stock_codes或板块直接进行AI分析（评分过滤可选）
        """
        # 1. 先基础扫描获取量化结果
        base_scan_id = self.base.start_scan(req)
        # 等基础扫描完成后，再启动AI分析
        t = threading.Thread(
            target=self._run_ai_thread,
            args=(base_scan_id, req, ollama_cfg, mode),
            daemon=True,
        )
        t.start()
        return base_scan_id  # 复用同一个scan_id

    def _wait_base_done(self, scan_id: str, timeout_sec: int = 60 * 60):
        """轮询等待基础扫描结束"""
        start = time.time()
        while time.time() - start < timeout_sec:
            p = self.tracker.get(scan_id)
            if p and p.get("status") in ("done", "error"):
                return p
            time.sleep(1.0)
        return None

    def _run_ai_thread(self, scan_id: str, req: ScanRequest,
                       ollama_cfg: Optional[Dict], mode: str):
        # 等待基础扫描结束
        base = self._wait_base_done(scan_id)
        if not base:
            self.tracker.log(scan_id, "[AI] 等待基础扫描超时")
            return
        if base.get("status") != "done":
            self.tracker.log(scan_id, f"[AI] 基础扫描失败，中止AI分析: {base.get('error_msg','')}")
            return
        top_stocks = base.get("results", []) or []
        if not top_stocks:
            self.tracker.log(scan_id, "[AI] 初筛通过股票为空，跳过AI分析")
            self.tracker.finish(scan_id, "done")
            return

        self.tracker.log(scan_id, f"[AI] 开始深度分析 {len(top_stocks)} 只股票，调用Ollama模型...")
        self.tracker.update(scan_id, "", "", passed=True, stage="AI生成深度分析报告中...")

        # 2. 调用Ollama
        ollama = self._ollama(ollama_cfg)
        sys_p, user_p = self._build_prompt(top_stocks)

        ai_report_parts: List[str] = []
        try:
            # 流式逐块记录到progress的stage_log里，同时整段保存
            last_log_time = 0
            for tok in ollama.chat_stream_sync(sys_p, user_p):
                ai_report_parts.append(tok)
                now = time.time()
                if now - last_log_time > 1.0:  # 每1秒更新一下状态
                    preview = "".join(ai_report_parts[-80:]).replace("
", " / ")
                    self.tracker._progresses[scan_id].ai_streaming_preview = preview
                    last_log_time = now
        except Exception as e:
            ai_report_parts.append(f"

[AI分析异常: {e}]")

        final_report = "".join(ai_report_parts).strip()

        # 3. 结果存入scan（附加ai_report字段）
        with self.tracker._lock:
            p = self.tracker._progresses.get(scan_id)
            if p:
                # 给每只股票附加ai的个股结论：这里做一个简单做法，整段report放scan级
                setattr(p, "ai_report", final_report)
                p.stage_log.append({"time": time.strftime("%H:%M:%S"), "msg": f"[AI] 深度分析报告生成完毕，{len(final_report)} 字"})

        self.tracker.log(scan_id, "[AI] 分析完成")
        self.tracker.finish(scan_id, "done")


_ai_scanner: Optional[AIScanner] = None

def get_ai_scanner() -> AIScanner:
    global _ai_scanner
    if _ai_scanner is None:
        _ai_scanner = AIScanner()
    return _ai_scanner
