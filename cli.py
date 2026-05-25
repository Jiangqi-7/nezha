"""neZha CLI 入口

用法:
    nezha-cli server              # 启动 daemon 服务
    nezha-cli --role tech --prompt "问题"  # 调用服务（服务需先启动）
    nezha-cli --interactive       # 交互模式
    nezha-cli --list-roles        # 列出所有角色
"""
__version__ = "0.1.0"

import argparse
import json
import os
import socket
import uuid
from langchain_core.messages import HumanMessage
from workflows.role_playing.graph import role_playing_graph, ROLES_CONFIG
from utils.config import get_app_config
from utils.exception_handler import format_error
from utils.logging import get_logger

app_config = get_app_config()
APP_NAME = app_config.get("name", "nezha")
APP_CLI = app_config.get("cli", "nezha-cli")

logger = get_logger(APP_NAME)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555
AUTH_TOKEN = os.getenv("NEZHA_AUTH_TOKEN", "")

if not AUTH_TOKEN:
    import warnings
    warnings.warn("NEZHA_AUTH_TOKEN 未设置，认证被禁用（不推荐生产环境）")


def send_request(request: dict, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict:
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((host, port))
        if AUTH_TOKEN:
            request["token"] = AUTH_TOKEN
        client.sendall(json.dumps(request, ensure_ascii=False).encode("utf-8"))
        data = client.recv(65536).decode("utf-8")
        client.close()
        return json.loads(data)
    except ConnectionRefusedError:
        return {"success": False, "error": f"无法连接到 {host}:{port}，请先运行 neZha server"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_request(request: dict) -> dict:
    if AUTH_TOKEN and request.get("token") != AUTH_TOKEN:
        return {"success": False, "error": "鉴权失败"}

    action = request.get("action")

    if action == "call_role":
        role = request.get("role", "").lower()
        prompt = request.get("prompt", "")
        session_id = request.get("session_id") or str(uuid.uuid4())
        current_role = request.get("current_role", "")

        if role not in ROLES_CONFIG:
            return {"success": False, "error": f"角色 {role} 不存在"}

        try:
            result = role_playing_graph.invoke(
                {"role": role, "current_role": current_role, "thread_id": session_id,
                 "messages": [HumanMessage(content=prompt)]},
                config={"configurable": {"thread_id": session_id}}
            )
            messages = result.get("messages", [])
            content = messages[-1].content if messages else ""
            return {"success": True, "content": content, "session_id": session_id,
                    "current_role": result.get("current_role", role)}
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            return {"success": False, "error": format_error(e)}

    elif action == "list_roles":
        return {
            "success": True,
            "roles": {name: {"name": info["name"], "description": info["description"]}
                     for name, info in ROLES_CONFIG.items()}
        }
    else:
        return {"success": False, "error": f"未知 action: {action}"}


def run_server(host: str, port: int):
    import threading

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    logger.info(f"neZha server 启动成功 {host}:{port}")

    def handle_client(client, addr):
        try:
            data = client.recv(65536).decode("utf-8")
            if data:
                if len(data) > 1024 * 1024:
                    client.sendall(json.dumps({"success": False, "error": "请求过大"}))
                else:
                    request = json.loads(data)
                    request.pop("token", None)
                    response = handle_request(request)
                    client.sendall(json.dumps(response, ensure_ascii=False).encode("utf-8"))
        except json.JSONDecodeError:
            client.sendall(json.dumps({"success": False, "error": "无效 JSON"}))
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
        finally:
            client.close()

    while True:
        try:
            client, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
            thread.start()
        except KeyboardInterrupt:
            logger.info("收到中断信号，关闭服务器")
            break

    server.close()


def run_interactive():
    print("=== neZha 交互式 CLI ===")
    print("命令: role <角色> 切换角色, session 查看session, quit 退出\n")

    session_id = str(uuid.uuid4())
    current_role = ""

    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue

            if user_input.lower() in ('quit', 'q'):
                break
            if user_input.lower().startswith('role '):
                new_role = user_input.split()[1].lower()
                if new_role in ROLES_CONFIG:
                    current_role = new_role
                    session_id = str(uuid.uuid4())
                    print(f"已切换到: {current_role}, session: {session_id}\n")
                continue
            if user_input.lower() in ('session', 'sid'):
                print(f"session: {session_id}\n")
                continue

            if not current_role:
                print(f"请先选择角色: {', '.join(ROLES_CONFIG.keys())}\n")
                continue

            try:
                result = role_playing_graph.invoke(
                    {"role": current_role, "current_role": current_role, "thread_id": session_id,
                     "messages": [HumanMessage(content=user_input)]},
                    config={"configurable": {"thread_id": session_id}}
                )
                msgs = result.get("messages", [])
                if msgs:
                    print(msgs[-1].content)
            except Exception as e:
                print(f"错误: {format_error(e)}\n")

        except KeyboardInterrupt:
            print("\n退出")
            break


def main():
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Agent 工作流编排框架")
    parser.add_argument("--host", default=DEFAULT_HOST, help="服务器地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="服务器端口")
    parser.add_argument("--role", help="角色名称")
    parser.add_argument("--prompt", help="输入提示")
    parser.add_argument("--session-id", help="会话ID（可选）")
    parser.add_argument("--list-roles", action="store_true", help="列出所有角色")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument("--code", action="store_true", help="使用代码助手模式")
    parser.add_argument("command", nargs="?", help="子命令: server")

    args = parser.parse_args()

    if args.code and args.prompt:
        from workflows.code_assistant import code_assistant_invoke as invoke_code
        result = invoke_code(args.prompt)
        msgs = result.get("messages", [])
        if msgs:
            print(msgs[-1].content)
        return

    if args.role and args.prompt:
        role_lower = args.role.lower()
        if role_lower not in ROLES_CONFIG:
            print(f"错误: 角色 {args.role} 不存在")
            return

        session_id = args.session_id or str(uuid.uuid4())
        try:
            result = role_playing_graph.invoke(
                {"role": role_lower, "current_role": role_lower, "thread_id": session_id,
                 "messages": [HumanMessage(content=args.prompt)]},
                config={"configurable": {"thread_id": session_id}}
            )
            messages = result.get("messages", [])
            if messages:
                logger.info("=== neZha 返回结果 ===")
                print(messages[-1].content)
        except Exception as e:
            import traceback
            print(f"错误: {format_error(e)}")
            print(f"堆栈: {traceback.format_exc()}")
        return

    if args.command == "server":
        run_server(args.host, args.port)
        return

    if args.interactive:
        run_interactive()
        return

    if args.list_roles:
        print("可用角色:")
        for name, info in ROLES_CONFIG.items():
            print(f"  {name}: {info['name']} - {info['description']}")
        return

    # 无参数时默认进入交互模式
    run_interactive()


if __name__ == "__main__":
    main()