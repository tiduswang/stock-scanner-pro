"""
日志工具封装
"""
import sys
from loguru import logger
from pathlib import Path


def get_logger(name: str = "stock_scanner"):
    """获取配置好的日志器"""
    # 移除默认handler
    try:
        logger.remove()
    except ValueError:
        pass

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True,
    )

    # 添加文件输出
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / f"{name}_{{time:YYYY-MM-DD}}.log",
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    return logger


# 默认日志实例
log = get_logger()
