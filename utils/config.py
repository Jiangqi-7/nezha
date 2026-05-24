"""配置文件加载工具

提供 YAML 配置文件加载，支持缓存避免重复读取。
可通过删除 load_yaml.cache_clear() 清除缓存。
"""

import yaml
from pathlib import Path
from functools import lru_cache
from .logging import get_logger

logger = get_logger("nezha.config")

# config 目录路径
CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=32)
def load_yaml(name: str) -> dict:
    """加载 YAML 配置文件，缓存结果

    Args:
        name: 配置文件名（不含路径），如 "config.yaml"

    Returns:
        解析后的字典对象

    Note:
        缓存清除：load_yaml.cache_clear()
    """
    path = CONFIG_DIR / name
    logger.debug(f"加载配置文件: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_config() -> dict:
    """加载统一配置文件（config.yaml）

    Returns:
        完整配置字典
    """
    return load_yaml("config.yaml")


def get_model_config() -> dict:
    """获取模型配置"""
    return get_config().get("model", {})


def get_logging_config() -> dict:
    """获取日志配置"""
    return get_config().get("logging", {})


def get_roles_config() -> dict:
    """获取角色配置"""
    return get_config().get("roles", {})


def get_app_config() -> dict:
    """获取应用配置"""
    return get_config().get("app", {})