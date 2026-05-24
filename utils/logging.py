"""全局日志模块

使用方式：
    from utils.logging import get_logger
    logger = get_logger("nezha.xxx")

日志级别（从 config.yaml 读取）：
    DEBUG: 详细信息
    INFO: 一般信息
    WARNING: 警告
    ERROR: 错误
"""

import logging
import sys

# 延迟初始化，避免循环导入
_configured = False
_log_level = logging.INFO


def _ensure_configured():
    """延迟配置日志（避免循环导入）"""
    global _configured, _log_level
    if _configured:
        return

    try:
        from .config import get_logging_config
        log_cfg = get_logging_config()
        level_str = log_cfg.get("level", "INFO")
        _log_level = getattr(logging, level_str.upper(), logging.INFO)
    except Exception:
        _log_level = logging.INFO

    logging.basicConfig(
        level=_log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    _configured = True


def get_logger(name: str = "nezha") -> logging.Logger:
    """获取指定名称的 logger

    Args:
        name: logger 名称，格式为 "nezha.module"

    Returns:
        Logger 实例
    """
    _ensure_configured()
    return logging.getLogger(name)