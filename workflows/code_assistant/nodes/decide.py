"""路由决策节点

根据迭代次数和错误状态决定下一步：
- 无错误或达到最大迭代 → 结束
- 反思后 → 直接重新生成（不连续两次反思）
- 有错误且需要反思 → 反思
"""
from typing import Dict
from utils.config import get_code_assistant_config
from utils.logging import get_logger

logger = get_logger("nezha.code_assistant.decide")


def create_decide_node(graph_state: Dict) -> str:
    """决定下一步"""
    error = graph_state["error"]
    iterations = graph_state["iterations"]

    config = get_code_assistant_config()
    max_iterations = config.get("max_iterations", 3)
    enable_reflect = config.get("enable_reflect", False)

    # 不再在 decide 中修改 error 状态，让下一个节点自行设置
    if error == "no" or iterations >= max_iterations:
        logger.info("--- 决定: 完成 ---")
        return "end"
    elif error == "done":
        logger.info("--- 决定: 重新生成 ---")
        return "generate"
    elif enable_reflect and error == "yes":
        logger.info("--- 决定: 反思 ---")
        return "reflect"
    else:
        logger.info("--- 决定: 重新生成 ---")
        return "generate"