"""neZha MCP Server 入口

提供 MCP 协议接口，供其他 Agent 调用角色服务。
- call_role: 调用指定角色处理问题
- list_roles: 列出所有可用角色

用法:
    nezha-mcp              # 启动 MCP server（stdio 模式）
"""
import uuid
from fastmcp import FastMCP
from langchain_core.messages import HumanMessage
from workflows.role_playing.graph import role_playing_graph, ROLES_CONFIG
from utils.config import get_app_config
from utils.logging import get_logger

app_config = get_app_config()
APP_NAME = app_config.get("name", "nezha")
APP_MCP = app_config.get("mcp", "nezha-mcp")

logger = get_logger(f"{APP_NAME}.mcp")

mcp = FastMCP(APP_NAME)


@mcp.tool()
def call_role(role: str, prompt: str, session_id: str | None = None,
              current_role: str = "") -> str:
    """调用角色

    Args:
        role: 角色名称（如 lawyer, tech, marketing 等）
        prompt: 输入提示
        session_id: 会话ID（可选，不传自动生成）
        current_role: 当前生效的角色名（用于角色切换）

    Returns:
        角色的回复内容，失败时返回错误信息字符串
    """
    try:
        role_lower = role.lower()
        if role_lower not in ROLES_CONFIG:
            return f"[错误] 角色 {role} 不存在，请检查 roles.yaml 配置"

        tid = session_id or str(uuid.uuid4())
        logger.info(f"调用角色 {role_lower}，session_id: {tid}")

        result = role_playing_graph.invoke(
            {"role": role_lower, "current_role": current_role, "thread_id": tid,
             "messages": [HumanMessage(content=prompt)]},
            config={"configurable": {"thread_id": tid}}
        )

        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return "[错误] 未收到回复"

    except Exception as e:
        logger.error(f"call_role 失败: {e}")
        return f"[错误] {type(e).__name__}: {e}"


@mcp.tool()
def list_roles() -> dict:
    """列出所有可用角色"""
    try:
        return {
            name: {"name": info["name"], "description": info["description"]}
            for name, info in ROLES_CONFIG.items()
        }
    except Exception as e:
        logger.error(f"list_roles 失败: {e}")
        return {"error": str(e)}


@mcp.tool()
def code_assistant(prompt: str) -> dict:
    """代码助手

    Args:
        prompt: 代码需求描述

    Returns:
        包含 generation 等字段的字典
    """
    try:
        from workflows.code_assistant import code_assistant_invoke
        result = code_assistant_invoke(prompt)
        return {
            "success": True,
            "content": result["messages"][-1].content if result["messages"] else "",
            "generation": result.get("generation", {}),
            "iterations": result.get("iterations", 0),
            "error": result.get("error", "")
        }
    except Exception as e:
        logger.error(f"code_assistant 失败: {e}")
        return {"success": False, "error": str(e)}


def main() -> None:
    """启动 MCP Server"""
    logger.info("启动 MCP Server")
    mcp.run()


if __name__ == "__main__":
    main()