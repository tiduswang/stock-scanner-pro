# -*- coding: utf-8 -*-
"""
智能选股系统 Pro - 独立安装 App
================================
本脚本只负责「环境与依赖准备」，不启动 Web 服务。主程序 start.bat / backend.main
不含任何依赖安装逻辑，运行前请先执行本脚本完成安装。

功能：
  1) 依赖安装：pip install -r requirements.txt（清华源加速，失败回退官方源）
  2) 依赖检查：逐个 import 关键包，列出缺失
  3) 语法检查：compileall 编译 backend 目录
  4) 模块导入检查：尝试 import backend.main 与核心服务，验证可启动

用法：
  python installer.py                 # 完整安装+检查
  python installer.py --check-only     # 仅检查，不安装（CI/复检用）
  python installer.py --install-only  # 仅安装依赖，不做后续检查
  python installer.py --no-mirror      # 不使用清华源，直接官方源

退出码：
  0 = 全部通过
  非0 = 失败（详见控制台输出）
"""
import subprocess
import sys
import os
import compileall
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# 需要校验的核心依赖（import名 -> pip包名）
REQUIRED_DEPS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "akshare": "akshare",
    "pandas": "pandas",
    "numpy": "numpy",
    "pypinyin": "pypinyin",
    "httpx": "httpx",
    "dotenv": "python-dotenv",
    "loguru": "loguru",
    "cachetools": "cachetools",
    "pydantic_settings": "pydantic-settings",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "ollama": "ollama",
    "sqlalchemy": "SQLAlchemy",
}


def log(msg: str) -> None:
    print(f"[installer] {msg}", flush=True)


def banner(title: str) -> None:
    log("=" * 60)
    log(f"  {title}")
    log("=" * 60)


# =============================================================
# Step 1: 依赖安装
# =============================================================
def step_install(use_mirror: bool = True) -> bool:
    banner("Step 1/4: 安装 Python 依赖")
    req = ROOT / "requirements.txt"
    if not req.exists():
        log(f"[错误] 找不到 requirements.txt: {req}")
        return False

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    if use_mirror:
        cmd += [
            "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple",
            "--trusted-host", "pypi.tuna.tsinghua.edu.cn",
        ]
    log(f"执行: {' '.join(cmd)}")
    r = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
    if r.returncode != 0:
        if use_mirror:
            log("[警告] 清华源安装失败，回退到官方源重试...")
            cmd2 = [sys.executable, "-m", "pip", "install", "-r", str(req)]
            log(f"执行: {' '.join(cmd2)}")
            r2 = subprocess.run(cmd2, stdout=sys.stdout, stderr=sys.stderr)
            if r2.returncode != 0:
                log("[错误] pip 安装失败，请手动检查网络/权限/numpy冲突")
                log("       常见修复: pip install --force-reinstall --no-deps numpy==2.1.2")
                return False
        else:
            log("[错误] pip 安装失败")
            return False
    log("依赖安装完成 ✅")
    return True


# =============================================================
# Step 2: 依赖检查（逐个 import）
# =============================================================
def step_check_deps() -> bool:
    banner("Step 2/4: 依赖检查")
    ok, missing = [], []
    for mod, pkg in REQUIRED_DEPS.items():
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "?")
            ok.append(f"  ✓ {pkg} ({ver})")
        except ImportError:
            missing.append(pkg)

    log(f"已安装: {len(ok)}/{len(REQUIRED_DEPS)}")
    for line in ok:
        log(line)
    if missing:
        log(f"[错误] 缺失依赖: {', '.join(missing)}")
        log(f"       请运行: python installer.py  或  pip install {' '.join(missing)}")
        return False
    log("全部依赖就绪 ✅")
    return True


# =============================================================
# Step 3: 语法检查
# =============================================================
def step_compile() -> bool:
    banner("Step 3/4: Python 语法检查 (compileall)")
    backend_dir = ROOT / "backend"
    if not backend_dir.exists():
        log(f"[错误] backend 目录不存在: {backend_dir}")
        return False
    ok = compileall.compile_dir(str(backend_dir), quiet=1, legacy=True)
    if not ok:
        log("[错误] 存在语法错误，请修复上方报错")
        return False
    log("语法检查通过 ✅")
    return True


# =============================================================
# Step 4: 模块导入检查（验证可启动）
# =============================================================
def step_import_check() -> bool:
    banner("Step 4/4: 模块导入检查")
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
        log(f"[错误] 导入失败: {e}")
        return False
    log("模块导入检查通过 ✅")
    return True


# =============================================================
# 主流程
# =============================================================
def main() -> int:
    banner("智能选股系统 Pro - 独立安装 App")
    log(f"Python: {sys.version.split()[0]}")
    log(f"项目根目录: {ROOT}")

    check_only = "--check-only" in sys.argv
    install_only = "--install-only" in sys.argv
    no_mirror = "--no-mirror" in sys.argv

    if check_only:
        log("模式: --check-only（仅检查，不安装）")
        steps = [
            ("依赖检查", step_check_deps),
            ("语法检查", step_compile),
            ("导入检查", step_import_check),
        ]
    elif install_only:
        log("模式: --install-only（仅安装依赖）")
        steps = [("依赖安装", lambda: step_install(use_mirror=not no_mirror))]
    else:
        log("模式: 完整安装+检查")
        steps = [
            ("依赖安装", lambda: step_install(use_mirror=not no_mirror)),
            ("依赖检查", step_check_deps),
            ("语法检查", step_compile),
            ("导入检查", step_import_check),
        ]

    for name, fn in steps:
        if not fn():
            log(f"❌ {name} 失败，终止")
            return 1

    log("")
    log("=" * 60)
    log("  ✅ 安装与检查全部完成！")
    log("  下一步：运行主程序 start.bat 或")
    log("         python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
