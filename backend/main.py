"""
FastAPI 主入口
启动:
  pip install -r requirements.txt
  python -m backend.main
或:
  uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload

访问：
  前端页面（零构建版，无需npm）: http://127.0.0.1:8888/
  API文档: http://127.0.0.1:8888/docs
  (Vue工程版npm构建后会挂载到 /vue 路径)
"""
import os
import sys
from pathlib import Path

# 把项目根目录加入sys.path，方便 import backend.xxx
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()  # 加载 .env

from backend.config import get_settings
from backend.utils.logger import log

_settings = get_settings()

app = FastAPI(
    title="智能选股系统 Pro",
    description="A股/港股/ETF 量化选股 + 本地Ollama AI 深度分析 (T+1交易模式)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 数据库初始化（建表）
from backend.db.session import init_db
init_db()

# 路由注册
from backend.routers.common import router as common_router
from backend.routers.search import router as search_router
from backend.routers.analyze import router as analyze_router
from backend.routers.scan import router as scan_router
from backend.routers.data import router as data_router

app.include_router(common_router)
app.include_router(search_router)
app.include_router(analyze_router)
app.include_router(scan_router)
app.include_router(data_router)


# ============ 静态前端文件：两种模式 ============
# 1) 零构建版 (CDN Element Plus) —— 推荐默认使用，开箱即用
_no_build_dir = _ROOT / "frontend_no_build"
# 2) Vue工程构建版 —— 用户跑过 npm run build 后生成
_vue_dist_dir = _ROOT / "frontend" / "dist"


def _mount_no_build():
    """挂载零构建前端到根路径"""
    if not _no_build_dir.exists():
        return False
    try:
        # 直接把 no build 目录当静态文件挂到 /ui 作为备用
        app.mount("/ui-static", StaticFiles(directory=str(_no_build_dir)), name="ui_no_build_files")
    except Exception:
        pass
    return True


_mount_no_build()


def _mount_vue_build():
    """挂载构建好的 Vue3 前端到 /vue 路径"""
    if not _vue_dist_dir.exists():
        return False
    try:
        app.mount(
            "/vue/assets",
            StaticFiles(directory=str(_vue_dist_dir / "assets")),
            name="vue_assets",
        )
        return True
    except Exception:
        return False


_has_vue = _mount_vue_build()


@app.get("/vue/{full_path:path}")
def vue_spa_fallback(full_path: str):
    """Vue 构建版 SPA fallback（访问 /vue/* 都走Vue）"""
    if not _has_vue:
        return {"msg": "Vue版前端未构建，请执行 frontend 目录下 npm install && npm run build", "tip": "也可以直接访问 / 使用零构建版"}
    if full_path.startswith("assets/"):
        return {"msg": "Not Found", "path": full_path}
    index_html = _vue_dist_dir / "index.html"
    return FileResponse(str(index_html))


@app.get("/{full_path:path}")
def root_fallback(full_path: str, request: Request):
    """
    根路径 fallback 优先级：
    1) API / docs / redoc 不动
    2) 否则返回零构建版 index.html（开箱即用）
    """
    if (
        full_path.startswith("api/")
        or full_path.startswith("docs")
        or full_path.startswith("redoc")
        or full_path.startswith("ui-static/")
        or full_path.startswith("vue/")
        or full_path.startswith("openapi.json")
        or full_path.startswith("favicon")
    ):
        return {"msg": "Not Found", "path": full_path}

    index_html = _no_build_dir / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    # 退而求其次，返回 Vue 版
    if _has_vue:
        return FileResponse(str(_vue_dist_dir / "index.html"))
    return {
        "msg": "智能选股后端运行中 ✅",
        "docs": "/docs",
        "tip_1": "访问前端(零构建版)请打开 / (此页面)",
        "tip_2": "若想用Vue版：cd frontend && npm install && npm run build，然后访问 /vue",
    }


@app.on_event("startup")
async def _startup():
    log.info("=" * 60)
    log.info(f"🚀 智能选股系统 Pro 启动: http://{_settings.APP_HOST}:{_settings.APP_PORT}")
    log.info(f"  🖥️  前端页面(零构建,无需npm): http://127.0.0.1:{_settings.APP_PORT}/")
    if _has_vue:
        log.info(f"  🖥️  Vue工程版前端:          http://127.0.0.1:{_settings.APP_PORT}/vue")
    log.info(f"  📚 API 文档(Swagger):       http://127.0.0.1:{_settings.APP_PORT}/docs")
    log.info(f"  🤖 Ollama: {_settings.OLLAMA_BASE_URL} (model={_settings.OLLAMA_MODEL})")
    log.info(f"  ⚖️  权重: 技术{_settings.WEIGHT_TECHNICAL} / 基本{_settings.WEIGHT_FUNDAMENTAL} / 情绪{_settings.WEIGHT_SENTIMENT}")
    log.info(f"  📌 交易模式: T+1 (A股/ETF 当日买入次日方可卖出)")
    log.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=_settings.APP_HOST,
        port=_settings.APP_PORT,
        reload=_settings.APP_DEBUG,
        log_level="info",
    )
