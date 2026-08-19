"""
应用配置模块
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """全局配置"""
    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8888
    APP_DEBUG: bool = True

    # Ollama 配置
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT: int = 300

    # 缓存时间(秒)
    CACHE_MARKET_DATA: int = 300      # 行情数据 5分钟
    CACHE_FUNDAMENTAL: int = 3600     # 财务数据 1小时
    CACHE_NEWS: int = 1800            # 新闻公告 30分钟
    CACHE_STOCK_LIST: int = 86400     # 股票列表 1天

    # 分析权重（总和=1）
    WEIGHT_TECHNICAL: float = 0.45
    WEIGHT_FUNDAMENTAL: float = 0.35
    WEIGHT_SENTIMENT: float = 0.20

    # AI选股默认分数阈值
    DEFAULT_SCORE_THRESHOLD: int = 70

    # 数据库配置
    DATABASE_URL: str = ""  # 留空则默认用 SQLite: data/stock.db
    # 数据同步配置
    SYNC_MAX_WORKERS: int = 5
    SYNC_RETRY: int = 2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()


class RuntimeState:
    """运行时可变状态（不通过 pydantic，直接类属性）"""
    current_ollama_model: str = ""


runtime = RuntimeState()
# 初始化为配置默认值
runtime.current_ollama_model = get_settings().OLLAMA_MODEL


# 市场类型定义
MARKET_TYPES = {
    "A": "A股",
    "HK": "港股",
    "ETF": "ETF基金",
}

# A股板块列表
A_SHARE_SECTORS = [
    "银行", "保险", "证券", "房地产", "煤炭", "钢铁", "有色金属",
    "化工", "医药生物", "食品饮料", "家用电器", "汽车", "电子", "计算机",
    "通信", "传媒", "军工", "电力设备", "新能源", "光伏", "半导体",
    "白酒", "消费", "金融", "基建", "建材", "石油石化", "农林牧渔",
]
