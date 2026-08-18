"""
内存缓存工具（带TTL过期）
"""
import time
from cachetools import TTLCache
from typing import Any, Optional
from functools import wraps
import threading

from backend.config import get_settings

_settings = get_settings()

# 不同类型的缓存池
_cache_store = {
    "market": TTLCache(maxsize=2000, ttl=_settings.CACHE_MARKET_DATA),
    "fundamental": TTLCache(maxsize=500, ttl=_settings.CACHE_FUNDAMENTAL),
    "news": TTLCache(maxsize=500, ttl=_settings.CACHE_NEWS),
    "stock_list": TTLCache(maxsize=10, ttl=_settings.CACHE_STOCK_LIST),
    "default": TTLCache(maxsize=1000, ttl=600),
}

_lock = threading.RLock()


def get_cache(category: str = "default") -> TTLCache:
    """获取指定分类的缓存池"""
    return _cache_store.get(category, _cache_store["default"])


def cache_get(category: str, key: str) -> Optional[Any]:
    """读取缓存"""
    with _lock:
        pool = get_cache(category)
        return pool.get(key)


def cache_set(category: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    """写入缓存"""
    with _lock:
        pool = get_cache(category)
        pool[key] = value


def cached(category: str, key_prefix: str = ""):
    """
    缓存装饰器
    Args:
        category: 缓存分类
        key_prefix: key前缀
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成cache key: 基于函数名+参数的简单hash
            key_parts = [key_prefix, func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = "|".join(key_parts)
            cached_val = cache_get(category, cache_key)
            if cached_val is not None:
                return cached_val
            result = await func(*args, **kwargs)
            cache_set(category, cache_key, result)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key_parts = [key_prefix, func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = "|".join(key_parts)
            cached_val = cache_get(category, cache_key)
            if cached_val is not None:
                return cached_val
            result = func(*args, **kwargs)
            cache_set(category, cache_key, result)
            return result

        import inspect
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    return decorator
