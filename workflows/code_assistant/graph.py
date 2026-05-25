"""代码助手工作流

generate → check → decide → end / generate / reflect
                              ↓
                          reflect → generate
"""
from functools import lru_cache
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


@lru_cache(maxsize=1)
def load_document() -> str:
    """加载参考文档（subprocess 调用避免阻塞）"""
    import subprocess
    import sys

    doc_cfg = _config.get("document", {})
    source = doc_cfg.get("source", "url")
    if source != "url":
        return ""

    urls = doc_cfg.get("urls", [])
    if not urls:
        return ""

    script = '''
import sys
import signal
sys.path.insert(0, '/mnt/f/PycharmProjects/neZha')

# 设置 45 秒超时
signal.alarm(45)

try:
    from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
    from bs4 import BeautifulSoup as Soup

    urls = %s
    contents = []
    for url in urls:
        try:
            loader = RecursiveUrlLoader(url=url, max_depth=2,
                                       extractor=lambda x: Soup(x, "html.parser").text)
            docs = loader.load()
            contents.append("\\n\\n".join([doc.page_content for doc in docs]))
        except Exception as e:
            print(f"加载失败 {url}: {e}", file=sys.stderr)
    print("\\n\\n---\\n\\n".join(contents))
except Exception as e:
    print(f"加载异常: {e}", file=sys.stderr)
''' % (urls,)

    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=50
        )
        return result.stdout if result.returncode == 0 else ""
    except subprocess.TimeoutExpired:
        print("文档加载超时 (45s)", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"文档加载异常: {e}", file=sys.stderr)
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
        document: 参考文档（可选，未提供时从配置加载）
        thread_id: 线程ID（可选）

    Returns:
        包含 generation 等字段的字典
    """
    if thread_id is None:
        import uuid
        thread_id = str(uuid.uuid4())

    logger.info(f"调用代码助手，thread_id: {thread_id}")

    # 如果未提供 document，从配置自动加载（使用 lru_cache 缓存结果，仅首次加载）
    if not document:
        document = load_document()
        if document:
            logger.info(f"已加载文档，长度: {len(document)}")
        else:
            logger.info("未配置文档或加载失败")

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