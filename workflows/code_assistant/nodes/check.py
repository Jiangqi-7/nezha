"""代码检查节点

使用执行器验证代码：
1. 检查导入是否成功
2. 检查代码是否可执行
"""
import re
from typing import Dict
from langchain_core.messages import AIMessage, HumanMessage
from utils.logging import get_logger
from utils.config import get_code_assistant_config

logger = get_logger("nezha.code_assistant.check")

_executor = None


def get_executor():
    """延迟加载执行器"""
    global _executor
    if _executor is None:
        from ..executors import PythonSandboxExecutor
        config = get_code_assistant_config()
        executor_cfg = config.get("executor", {})
        _executor = PythonSandboxExecutor(
            timeout=executor_cfg.get("timeout", 5),
            memory_mb=int(executor_cfg.get("memory_limit", "128m").replace("m", ""))
        )
    return _executor


def strip_code_block_markers(code: str) -> str:
    """去除 markdown 代码块标记"""
    # 去除 ```python ... ``` 或 ``` ... ``` 等标记
    pattern = r"```(\w+)?\s*\n(.*?)\n```"
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(2).strip()
    # 如果没有标记，直接返回
    return code


def create_check_node(graph_state: Dict) -> Dict:
    """检查代码是否可执行"""
    logger.info("--- 正在检查代码 ---")

    messages = graph_state["messages"]
    generation = graph_state["generation"]

    executor = get_executor()
    imports = generation.get("imports", "")
    raw_code = generation.get("code", "")
    code = strip_code_block_markers(raw_code)

    # 检查导入
    if imports.strip():
        result = executor.verify("", imports)
        if not result.success:
            logger.info("--- 导入检查: 失败 ---")
            messages = messages + [HumanMessage(content=f"导入失败: {result.error}")]
            return {
                "generation": generation,
                "messages": messages,
                "iterations": graph_state["iterations"],
                "error": "yes",
                "document": graph_state.get("document", "")
            }

    # 检查代码执行
    result = executor.verify(code, imports)
    if not result.success:
        logger.info("--- 代码执行检查: 失败 ---")
        messages = messages + [HumanMessage(content=f"代码执行失败: {result.error}")]
        return {
            "generation": generation,
            "messages": messages,
            "iterations": graph_state["iterations"],
            "error": "yes",
            "document": graph_state.get("document", "")
        }

    logger.info("--- 无代码测试失败 ---")
    return {
        "generation": generation,
        "messages": messages,
        "iterations": graph_state["iterations"],
        "error": "no",
        "document": graph_state.get("document", "")
    }