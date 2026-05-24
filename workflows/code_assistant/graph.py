"""代码助手工作流

generate → check → decide → end / generate / reflect
                              ↓
                          reflect → generate
"""
from typing import Dict, List, TypedDict
from langgraph.graph import END, StateGraph, START
from langchain_core.messages import HumanMessage, AIMessage
from utils.config import get_code_assistant_config
from utils.logging import get_logger
from utils.exceptions import ConfigError

logger = get_logger("nezha.code_assistant")

_config = get_code_assistant_config()
if not _config:
    raise ConfigError("code_assistant 配置不存在")


class State(TypedDict):
    """工作流状态"""
    error: str
    messages: List
    generation: Dict
    iterations: int
    document: str


def load_document() -> str:
    """加载参考文档（按需调用）"""
    doc_cfg = _config.get("document", {})
    source = doc_cfg.get("source", "url")

    if source == "url":
        from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
        from bs4 import BeautifulSoup as Soup

        urls = doc_cfg.get("urls", [])
        if not urls:
            return ""

        contents = []
        for url in urls:
            try:
                loader = RecursiveUrlLoader(url=url, max_depth=10,
                                           extractor=lambda x: Soup(x, "html.parser").text)
                docs = loader.load()
                contents.append("\n\n".join([doc.page_content for doc in docs]))
            except Exception as e:
                logger.warning(f"加载文档失败 {url}: {e}")

        return "\n\n---\n\n".join(contents)

    return ""


def create_workflow():
    """构建工作流"""
    from .nodes.generate import create_generate_node
    from .nodes.check import create_check_node
    from .nodes.decide import create_decide_node
    from .nodes.reflect import create_reflect_node

    workflow = StateGraph(State)

    workflow.add_node("generate", create_generate_node)
    workflow.add_node("check_code", create_check_node)
    workflow.add_node("decide", create_decide_node)
    workflow.add_node("reflect", create_reflect_node)

    workflow.add_edge(START, "generate")
    workflow.add_edge("generate", "check_code")
    workflow.add_conditional_edges("check_code", create_decide_node, {
        "end": END,
        "reflect": "reflect",
        "generate": "generate"
    })
    workflow.add_edge("reflect", "generate")

    return workflow.compile()


def invoke(question: str, document: str = "", thread_id: str = None) -> Dict:
    """调用代码助手

    Args:
        question: 用户问题
        document: 参考文档（可选，默认空）
        thread_id: 线程ID（可选）

    Returns:
        包含 generation 等字段的字典
    """
    if thread_id is None:
        import uuid
        thread_id = str(uuid.uuid4())

    logger.info(f"调用代码助手，thread_id: {thread_id}")

    # 每次创建新的 workflow 实例，避免 LangGraph 内部状态累积导致 MemoryError
    graph = create_workflow()

    # 设置较大的 recursion_limit，避免在复杂流程中触发限制
    result = graph.invoke({
        "error": "",
        "messages": [HumanMessage(content=question)],
        "generation": {},
        "iterations": 0,
        "document": document
    }, config={"configurable": {"thread_id": thread_id}, "recursion_limit": 100})

    return result