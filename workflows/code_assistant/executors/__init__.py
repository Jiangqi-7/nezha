"""可插拔执行器

- BaseExecutor: 抽象基类
- PythonSandboxExecutor: Python 沙箱执行
- Judge0Executor: Judge0 API 执行（预留）
"""
from .base import BaseExecutor, ExecutionResult
from .python import PythonSandboxExecutor

__all__ = ["BaseExecutor", "ExecutionResult", "PythonSandboxExecutor"]