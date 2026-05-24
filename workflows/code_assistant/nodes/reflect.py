"""反思节点

基于错误信息生成反思，帮助修正代码。
"""
from typing import Dict
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from utils.model import MODEL
from utils.logging import get_logger

logger = get_logger("nezha.code_assistant.reflect")


def create_reflect_node(graph_state: Dict) -> Dict:
    """反思错误并生成修正建议"""
    logger.info("--- 正在反思 ---")

    # 创建新的 messages 列表，避免 LangGraph 内部状态引用问题
    messages = list(graph_state["messages"])
    document = graph_state["document"]

    # 使用更可靠的请求方式，手动构建请求并处理错误
    from utils.model import get_model
    model = get_model()

    # 构建反思提示
    prompt_text = f"""你是一位编程专家，负责反思代码错误并给出修正建议。

根据对话历史，分析错误原因，给出具体的修正方案。

以下是用户问题和错误：

"""
    for msg in messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        prompt_text += f"\n\n{role}: {msg.content}"

    logger.info("调用 LLM 进行反思")

    # 简单重试逻辑，最多3次
    import time
    max_retries = 3
    last_error = None
    reflections = None

    for attempt in range(max_retries):
        try:
            reflections = model.invoke([HumanMessage(content=prompt_text)])
            break
        except Exception as e:
            last_error = e
            logger.warning(f"反思调用失败 (尝试 {attempt+1}/{max_retries}): {type(e).__name__}")
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)

    # 如果反射失败，返回一个安全的默认值
    if reflections is None or not hasattr(reflections, 'content'):
        logger.warning("反思调用失败，使用默认值")
        reflections = type('obj', (object,), {'content': '代码执行遇到问题，请检查语法和逻辑。'})()

    messages = messages + [
        AIMessage(content=f"以下是对错误的反思: {reflections.content}")
    ]

    return {
        "generation": graph_state["generation"],
        "messages": messages,
        "iterations": graph_state["iterations"],
        "error": "done",
        "document": graph_state["document"]
    }