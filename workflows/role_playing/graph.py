"""角色扮演工作流

基于 LangGraph 的状态机工作流，支持多轮对话和角色切换。

使用 MessagesState + add_messages reducer 实现自动历史管理：
- 节点返回 {"messages": [response]} 自动追加到现有消息
- MemorySaver 自动保存/恢复消息历史
- 调用时只需传入 role + messages，无需手动拼接历史
- 角色切换时通过 role_messages_store 存档/恢复各角色历史
"""
from pathlib import Path
from functools import lru_cache
from typing import Annotated, TypedDict, List, Dict, Tuple
from langgraph.graph import MessagesState, StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from utils.config import get_roles_config
from utils.exceptions import ConfigError, PromptFileNotFoundError, ModelInvokeError, PromptReadError, EmptyResponseError
from utils.logging import get_logger
from utils.model import MODEL

logger = get_logger("nezha.graph")

ROLES_CONFIG = get_roles_config()
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
for name, config in ROLES_CONFIG.items():
    if "prompt_file" not in config:
        raise ConfigError(f"角色 {name} 缺少 prompt_file 配置")
    prompt_path = CONFIG_DIR / config["prompt_file"]
    if not prompt_path.exists():
        raise PromptFileNotFoundError(f"角色 {name} 的提示词文件不存在: {prompt_path}")

logger.info(f"已存在 {len(ROLES_CONFIG)} 个角色配置")


class State(TypedDict):
    role: str
    current_role: str
    thread_id: str
    messages: Annotated[List[AIMessage], add_messages]


@lru_cache(maxsize=32)
def load_prompt_template(prompt_file: str) -> PromptTemplate:
    try:
        content = (CONFIG_DIR / prompt_file).read_text(encoding="utf-8")
        return PromptTemplate.from_template(content)
    except Exception as e:
        raise PromptReadError(detail=str(e))


# 角色对话历史存储：(thread_id, role) -> messages
role_messages_store: Dict[Tuple[str, str], List] = {}

# 已打印过 system message 的 thread_id
_printed_system: set = set()


def route(state: State) -> str:
    role = (state.get("role") or "").lower()
    if role in ROLES_CONFIG:
        return role
    return "unknown"


def create_role_node(role: str):
    def handler(state: State) -> dict:
        thread_id = state.get("thread_id", "")
        current_role = state.get("current_role", "")

        config = ROLES_CONFIG[role]
        prompt_template = load_prompt_template(config["prompt_file"])

        # 角色切换时：先存档当前角色，再恢复新角色历史
        if current_role and current_role != role:
            role_messages_store[(thread_id, current_role)] = list(state["messages"])
            logger.info(f"存档 {current_role} 对话: {len(state['messages'])} 条")

            stored = role_messages_store.get((thread_id, role), [])
            if stored:
                state["messages"] = stored
                logger.info(f"恢复 {role} 历史: {len(stored)} 条")

        has_system = any(isinstance(m, SystemMessage) for m in state["messages"])

        new_system = None
        if has_system:
            full_messages = state["messages"]
        else:
            new_system = SystemMessage(content=prompt_template.template)
            full_messages = [new_system] + state["messages"]

        logger.info(f"[{role}] 调用，消息数: {len(full_messages)}")

        try:
            response = MODEL.invoke(full_messages)
            # 调试打印，注释掉避免污染返回
            # if thread_id not in _printed_system:
            #     full_messages[0].pretty_print()
            #     _printed_system.add(thread_id)
            # full_messages[-1].pretty_print()
            # response.pretty_print()
        except Exception as e:
            logger.error(f"模型调用失败: {e}")
            raise ModelInvokeError(f"模型调用失败: {str(e)}")

        if not response.content:
            logger.error(f"角色 {role} 返回空内容")
            raise EmptyResponseError()

        # 存档完整历史到 store
        role_messages_store[(thread_id, role)] = full_messages + [response]

        return {"current_role": role, "messages": [response]}

    return handler


workflow = StateGraph(State)
workflow.add_node("route", lambda s: s)

for role in ROLES_CONFIG:
    workflow.add_node(role, create_role_node(role))

workflow.add_node("unknown", lambda s: {
    "messages": [AIMessage(content=f"角色不存在: {s.get('role', '')}，请检查 roles.yaml 配置")]
})

workflow.set_entry_point("route")
workflow.add_conditional_edges("route", route, {r: r for r in ROLES_CONFIG} | {"unknown": "unknown"})
workflow.add_edge("unknown", END)
for role in ROLES_CONFIG:
    workflow.add_edge(role, END)

checkpointer = MemorySaver()
role_playing_graph = workflow.compile(checkpointer=checkpointer)