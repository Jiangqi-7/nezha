"""代码执行器接口

提供可插拔的代码验证执行器：
- PythonSandboxExecutor: Python 沙箱执行（超时+内存限制）
- Judge0Executor: Judge0 API 执行（预留）
"""
from abc import ABC, abstractmethod
from typing import NamedTuple


class ExecutionResult(NamedTuple):
    """执行结果"""
    success: bool
    output: str = ""
    error: str = ""


class BaseExecutor(ABC):
    """代码执行器基类"""

    @abstractmethod
    def verify(self, code: str, imports: str = "") -> ExecutionResult:
        """验证代码是否可执行

        Args:
            code: 代码块
            imports: 导入语句

        Returns:
            ExecutionResult(success, output, error)
        """
        pass

    @abstractmethod
    def get_language(self) -> str:
        """返回支持的语言"""
        pass