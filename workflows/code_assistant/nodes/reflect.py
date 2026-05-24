"""反思节点

基于错误信息生成反思，帮助修正代码。
"""
from typing import Dict
from langchain_core.messages import AIMessage, HumanMessage
from utils.logging import get_logger

logger = get_logger("nezha.code_assistant.reflect")


def _invoke_reflect_in_subprocess(messages: list) -> str:
    """在独立进程中调用 LLM 进行反思"""
    import subprocess
    import sys

    msg_str = "\n".join([
        f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {m.content}"
        for m in messages
    ])

    script = f'''
import sys
sys.path.insert(0, '/mnt/f/PycharmProjects/neZha')
from utils.model import get_model
from langchain_core.messages import HumanMessage

model = get_model()

prompt_text = """你是一位编程专家，负责反思代码错误并给出修正建议。

根据对话历史，分析错误原因，给出具体的修正方案。

以下是用户问题和错误：

{msg_str}
"""

result = model.invoke([HumanMessage(content=prompt_text)])
print(result.content if hasattr(result, 'content') else str(result))
'''
    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise RuntimeError(f"Subprocess failed: {result.stderr}")
    except Exception as e:
        raise RuntimeError(f"Subprocess call failed: {e}")


def create_reflect_node(graph_state: Dict) -> Dict:
    """反思错误并生成修正建议"""
    logger.info("--- 正在反思 ---")

    messages = list(graph_state["messages"])

    logger.info("调用 LLM 进行反思")

    try:
        reflections_content = _invoke_reflect_in_subprocess(messages)
    except Exception as e:
        logger.warning(f"反思调用失败: {e}")
        reflections_content = "代码执行遇到问题，请检查语法和逻辑。"

    messages = messages + [
        AIMessage(content=f"以下是对错误的反思: {reflections_content}")
    ]

    return {
        "generation": graph_state["generation"],
        "messages": messages,
        "iterations": graph_state["iterations"],
        "error": "done",
        "document": graph_state["document"]
    }