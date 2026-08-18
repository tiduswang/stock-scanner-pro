# -*- coding: utf-8 -*-
"""
启动前校验脚本：
1) 安装 requirements.txt 依赖（清华源加速）
2) 语法检查 compileall
3) 最小导入检查 backend.main
4) 启动 uvicorn 作为后台进程 -> 打印访问地址
"""
import subprocess
import sys
import os
import time
import compileall
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

def log(msg: str):
    print(f"[bootstrap] {msg}", flush=True)

def step1_install():
    log("==== Step 1/4: 安装 Python 依赖 ====")
    req = ROOT / "requirements.txt"
    if not req.exists():
        log(f"requirements.txt 不存在: {req}")
        return False
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--trusted-host", "pypi.tuna.tsinghua.edu.cn",
        "-r", str(req),
    ]
    log("执行: " + " ".join(cmd))
    r = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
    if r.returncode != 0:
        log(f"pip install 返回非零: {r.returncode}，尝试使用官方源重试一次")
        cmd2 = [sys.executable, "-m", "pip", "install", "-r", str(req)]
        r2 = subprocess.run(cmd2, stdout=sys.stdout, stderr=sys.stderr)
        if r2.returncode != 0:
            log("pip 安装失败，请手动检查网络 / 权限")
            return False
    log("依赖安装完成")
    return True

def step2_compile():
    log("==== Step 2/4: Python 语法检查 (compileall) ====")
    backend_dir = ROOT / "backend"
    if not backend_dir.exists():
        log("backend 目录不存在！")
        return False
    ok = compileall.compile_dir(str(backend_dir), quiet=0, legacy=True)
    if not ok:
        log("存在语法错误，请修复上方报错")
        return False
    log("语法检查通过 ✅")
    return True

def step3_import_check():
    log("==== Step 3/4: 模块导入检查 ====")
    try:
        from backend.config import get_settings, MARKET_TYPES, A_SHARE_SECTORS
        s = get_settings()
        log(f"  - 配置加载 OK: host={s.APP_HOST}, port={s.APP_PORT}, model={s.OLLAMA_MODEL}")
        log(f"  - 支持市场: {MARKET_TYPES}")
        log(f"  - A股板块数: {len(A_SHARE_SECTORS)}")

        from backend.utils.logger import log as blog
        blog.info("  - 日志模块 OK")

        from backend.utils.cache import cache_get, cache_set
        cache_set("default", "_ping_test", 1)
        assert cache_get("default", "_ping_test") == 1
        log("  - 缓存模块 OK")

        from backend.services.analysis.technical import TechnicalAnalyzer
        from backend.services.analysis.fundamental_analysis import FundamentalAnalyzer
        from backend.services.analysis.sentiment import SentimentAnalyzer
        from backend.services.analysis.scoring import ScoringEngine
        from backend.services.analysis.buy_sell import BuySellAnalyzer
        from backend.services.scanner.progress import ProgressTracker
        from backend.services.scanner.base_scanner import BaseScanner, ScanRequest
        from backend.services.scanner.ai_scanner import AIScanner, OllamaClient
        from backend.services.search.stock_search import StockSearchService
        log("  - 所有核心服务可导入 ✅")

        from backend.main import app
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        log(f"  - FastAPI app 构造完成，路由数: {len(routes)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        log(f"导入失败: {e}")
        return False
    log("模块导入检查通过 ✅")
    return True

def main():
    steps = [
        ("依赖安装", step1_install),
        ("语法检查", step2_compile),
        ("导入检查", step3_import_check),
    ]
    only_verify = "--verify-only" in sys.argv

    for name, fn in steps:
        ok = fn()
        if not ok:
            log(f"❌ {name} 失败，终止")
            sys.exit(1)

    if only_verify:
        log("===== verify-only 模式完成，全部通过 ✅ =====")
        sys.exit(0)

    log("==== Step 4/4: 启动 Web 服务 ====")
    log("  Tip: 访问 http://127.0.0.1:8888/ 打开零构建前端页面")
    log("       API文档: http://127.0.0.1:8888/docs")
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app",
           "--host", "0.0.0.0", "--port", "8888", "--reload"]
    log("执行: " + " ".join(cmd))
    subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

if __name__ == "__main__":
    main()
