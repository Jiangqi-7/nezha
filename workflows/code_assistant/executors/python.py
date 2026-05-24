"""Python 沙箱执行器

使用 subprocess + resource limits 实现轻量级隔离执行。
适用于个人/内网环境，不建议暴露在公网。
"""
import resource
import subprocess
import tempfile
import os
from .base import BaseExecutor, ExecutionResult


class PythonSandboxExecutor(BaseExecutor):
    """Python 沙箱执行器"""

    def __init__(self, timeout: int = 5, memory_mb: int = 128):
        self.timeout = timeout
        self.memory_mb = memory_mb

    def get_language(self) -> str:
        return "python"

    def verify(self, code: str, imports: str = "") -> ExecutionResult:
        full_code = imports + "\n" + code if imports else code

        # 写临时文件执行，避免注入风险
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(full_code)
            temp_path = f.name

        try:
            # 设置资源限制
            max_mem_bytes = self.memory_mb * 1024 * 1024
            try:
                resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))
            except (ValueError, OSError):
                pass  # macOS 不支持 RLIMIT_AS

            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                return ExecutionResult(success=True, output=result.stdout)
            else:
                return ExecutionResult(success=False, error=result.stderr)

        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=f"执行超时 ({self.timeout}s)")
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))
        finally:
            os.unlink(temp_path)