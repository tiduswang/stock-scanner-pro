"""
通用路由：健康检查、配置、板块列表、Ollama连通性检查
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.config import get_settings, MARKET_TYPES, A_SHARE_SECTORS
from backend.services.scanner.ai_scanner import OllamaClient

router = APIRouter(prefix="/api/common", tags=["通用"])
_settings = get_settings()


@router.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/config")
def default_config():
    """默认分析配置（权重、默认参数）"""
    return {
        "weights": {
            "technical": _settings.WEIGHT_TECHNICAL,
            "fundamental": _settings.WEIGHT_FUNDAMENTAL,
            "sentiment": _settings.WEIGHT_SENTIMENT,
        },
        "score_threshold": _settings.DEFAULT_SCORE_THRESHOLD,
        "markets": MARKET_TYPES,
        "sectors": A_SHARE_SECTORS,
        "ollama": {
            "base_url": _settings.OLLAMA_BASE_URL,
            "model": _settings.OLLAMA_MODEL,
            "timeout": _settings.OLLAMA_TIMEOUT,
        },
    }


class OllamaCheckResp(BaseModel):
    ok: bool
    msg: str = ""
    service: bool = False
    model_exists: bool = False
    available_models: List[str] = []
    using_model: str = ""


class OllamaCfg(BaseModel):
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[int] = None


@router.post("/ollama/check", response_model=OllamaCheckResp)
async def check_ollama(cfg: Optional[OllamaCfg] = None):
    """检查本地Ollama服务和模型可用性"""
    import asyncio
    client = OllamaClient(
        base_url=cfg.base_url if cfg else None,
        model=cfg.model if cfg else None,
        timeout=cfg.timeout if cfg else None,
    )
    res = await client.check_connection()
    return res
