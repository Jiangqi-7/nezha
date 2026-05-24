"""统一异常处理模块

使用方式：
    @handle_exceptions
    def my_func():
        ...

环境变量：
    NEZHA_DEBUG=true 开启调试模式

异常处理流程：
    1. 捕获所有 Exception
    2. 判断是否为 NezhaError
    3. NezhaError: 格式化 code + message + detail
    4. 其他异常: 格式化为 500 内部错误，DEBUG_MODE 下包含详情
"""

import os
from utils.exceptions import NezhaError

# 从环境变量读取，默认为 False
DEBUG_MODE = os.getenv("NEZHA_DEBUG", "false").lower() == "true"


def get_debug_mode() -> bool:
    """延迟读取 DEBUG_MODE，避免模块加载时取值问题"""
    return os.getenv("NEZHA_DEBUG", "false").lower() == "true"


def format_error(exc: Exception) -> str:
    """将异常格式化为友好消息"""
    if isinstance(exc, NezhaError):
        msg = f"[错误 {exc.code}] {exc.message}"
        if get_debug_mode() and exc.detail:
            msg += f"\n详情: {exc.detail}"
        return msg

    msg = f"[错误 500] 服务器内部错误"
    if get_debug_mode():
        msg += f"\n类型: {type(exc).__name__}"
        msg += f"\n信息: {str(exc)}"
    return msg


def handle_exceptions(func):
    """装饰器：统一异常处理

    捕获被装饰函数的异常，转换为友好错误消息返回

    Args:
        func: 被装饰的函数

    Returns:
        包装后的函数
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return format_error(e)
    return wrapper