"""代码生成节点

使用结构化输出生成代码，包含前缀说明、导入语句、代码块。
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field
from jinja2 import Template
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from utils.config import get_code_assistant_config
from utils.model import MODEL
from utils.logging import get_logger

logger = get_logger("nezha.code_assistant.generate")

# 提示词模板路径
PROMPT_DIR = Path(__file__).parent.parent.parent.parent / "config" / "prompts"


class CodeSolution(BaseModel):
    """代码解决方案"""
    prefix: str = Field(description="问题和解决方案的描述")
    imports: str = Field(description="代码块导入语句")
    code: str = Field(description="不包括导入语句的代码块")


@lru_cache(maxsize=16)
def _load_template(prompt_file: str) -> Template:
    """缓存加载的模板"""
    template_path = PROMPT_DIR / prompt_file
    return Template(template_path.read_text(encoding="utf-8"))


def render_prompt_template(prompt_file: str, document: str, question: str) -> str:
    """渲染 Jinja2 提示词模板"""
    template = _load_template(prompt_file)
    return template.render(document=document, question=question)


# 缓存 structured_llm 和 prompt，避免每次创建新的 RunnableSequence
_structured_llm_cache = {}


def _get_structured_llm():
    """获取缓存的结构化 LLM"""
    global _structured_llm_cache
    if "llm" not in _structured_llm_cache:
        _structured_llm_cache["llm"] = MODEL.with_structured_output(CodeSolution, include_raw=True)
    return _structured_llm_cache["llm"]


def _get_base_prompt(document: str):
    """获取基础 prompt template"""
    global _structured_llm_cache
    cache_key = f"prompt_{hash(document) % 1000}"
    if cache_key not in _structured_llm_cache:
        prompt_file = get_code_assistant_config().get("prompt_file", "code_assistant/generate.md")
        system_prompt = render_prompt_template(prompt_file, document=document, question="")
        _structured_llm_cache[cache_key] = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("placeholder", "{messages}")
        ])
    return _structured_llm_cache[cache_key]


def _build_fresh_chain(document: str):
    """获取新的 chain

    使用 get_model() 获取单例，避免重复创建资源导致 MemoryError。
    直接返回 model，避免 prompt | model RunnableSequence 在 LangGraph workflow 中
    导致的 MemoryError 和网络问题。
    """
    from utils.model import get_model
    return get_model()


def _invoke_in_subprocess(prompt_text: str) -> str:
    """在独立进程中调用 LLM，避免网络层在 workflow 中的问题"""
    import subprocess
    import json
    import sys

    script = f'''
import sys
sys.path.insert(0, '/mnt/f/PycharmProjects/neZha')
from utils.model import get_model
from langchain_core.messages import HumanMessage

model = get_model()
result = model.invoke([HumanMessage(content={repr(prompt_text)})])
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


def _format_generate_prompt(document: str, messages: list) -> str:
    """格式化生成请求的 prompt"""
    prompt_file = get_code_assistant_config().get("prompt_file", "code_assistant/generate.md")
    system_prompt = render_prompt_template(prompt_file, document=document, question="")

    # 格式化为消息字符串
    msg_str = "\n".join([f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {m.content}" for m in messages])

    return f"{system_prompt}\n\n## 对话历史\n{msg_str}"


def _parse_code_solution(raw_output) -> Dict:
    """手动解析 LLM 输出为 CodeSolution

    因为 with_structured_output 在 LangGraph workflow 中会导致 MemoryError，
    所以改用手动解析方式。
    """
    import json
    import re

    content = raw_output.content if hasattr(raw_output, 'content') else str(raw_output)

    # 尝试从 content 中提取 JSON
    # 优先查找 ```json ... ``` 块
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        try:
            data = json.loads(json_str)
            return {
                "prefix": data.get("prefix", ""),
                "imports": data.get("imports", ""),
                "code": data.get("code", "")
            }
        except json.JSONDecodeError:
            pass

    # 尝试解析中文格式: prefix: xxx\nimports: xxx\ncode: xxx
    # 这种格式每个字段占一行
    lines = content.split('\n')
    prefix_lines = []
    imports_lines = []
    code_lines = []
    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith('prefix：') or line.startswith('prefix:'):
            current_section = 'prefix'
            prefix_lines.append(line.split('：', 1)[-1].split(':', 1)[-1].strip())
        elif line.startswith('imports：') or line.startswith('imports:'):
            current_section = 'imports'
            imports_lines.append(line.split('：', 1)[-1].split(':', 1)[-1].strip())
        elif line.startswith('code：') or line.startswith('code:'):
            current_section = 'code'
            code_lines.append(line.split('：', 1)[-1].split(':', 1)[-1].strip())
        elif line.startswith('```') or line.startswith('"""'):
            continue
        elif current_section == 'prefix':
            prefix_lines.append(line)
        elif current_section == 'imports':
            imports_lines.append(line)
        elif current_section == 'code':
            code_lines.append(line)

    if prefix_lines and code_lines:
        return {
            "prefix": '\n'.join(prefix_lines).strip(),
            "imports": '\n'.join(imports_lines).strip(),
            "code": '\n'.join(code_lines).strip()
        }

    # 如果中文格式解析失败，尝试带引号的JSON格式
    prefix_match = re.search(r'"prefix"\s*:\s*"([^"]*)"', content)
    imports_match = re.search(r'"imports"\s*:\s*"([^"]*)"', content)
    code_match = re.search(r'"code"\s*:\s*"([^"]*)"', content)

    if prefix_match and code_match:
        return {
            "prefix": prefix_match.group(1),
            "imports": imports_match.group(1) if imports_match else "",
            "code": code_match.group(1)
        }

    raise ValueError(f"无法解析 LLM 输出: {content[:200]}")


def create_generate_node(graph_state: Dict) -> Dict:
    """生成代码解决方案"""
    logger.info("--- 正在生成代码解决方案 ---")

    # 创建完全新的消息列表，复制每个消息以避免 LangGraph 内部状态引用
    original_messages = graph_state["messages"]
    messages = []
    for msg in original_messages:
        # 创建新的消息对象，避免引用原始的 LangGraph 内部消息
        if hasattr(msg, 'content'):
            messages.append(type(msg)(msg.content))
        else:
            messages.append(msg)

    document = graph_state["document"]

    logger.info(f"generate 输入: iterations={graph_state['iterations']}, messages数={len(messages)}, document长度={len(document)}")

    try:
        # 构建 prompt
        prompt_text = _format_generate_prompt(document, messages)
        logger.info(f"调用 LLM, messages数={len(messages)}")

        # 在独立进程中调用 LLM
        raw_content = _invoke_in_subprocess(prompt_text)
        logger.info(f"LLM 调用成功, content长度={len(raw_content)}")

        # 构造 AIMessage 对象用于后续处理
        from langchain_core.messages import AIMessage
        raw_output = AIMessage(content=raw_content)

        # 手动解析输出
        solution_dict = _parse_code_solution(raw_output)
        logger.info(f"解析成功: code={solution_dict['code'][:50]}...")

        # 使用 solution_dict 而非 solution 对象
        prefix = solution_dict['prefix']
        imports = solution_dict['imports']
        code = solution_dict['code']

        messages = messages + [
            AIMessage(content=f"{prefix}\n\n导入: {imports}\n\n代码: {code}")
        ]

        result = {
            "generation": {"prefix": prefix, "imports": imports, "code": code},
            "messages": messages,
            "iterations": graph_state["iterations"] + 1,
            "document": graph_state.get("document", "")
        }
        logger.info(f"generate 完成: iterations={result['iterations']}, messages数={len(result['messages'])}")
        return result

    except Exception as e:
        logger.error(f"generate 异常: {type(e).__name__}: {str(e)[:200]}")
        try:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"堆栈: {tb[:500]}")
        except Exception:
            logger.error("无法获取异常堆栈")
        raise