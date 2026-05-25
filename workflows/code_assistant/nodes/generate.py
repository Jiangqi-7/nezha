"""代码生成节点

使用结构化输出生成代码，包含前缀说明、导入语句、代码块。
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field
from jinja2 import Template
from langchain_core.messages import HumanMessage, AIMessage
from utils.config import get_code_assistant_config
from utils.logging import get_logger

logger = get_logger("nezha.code_assistant.generate")

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


def _invoke_in_subprocess(prompt_text: str) -> CodeSolution:
    """在独立进程中调用 LLM，使用结构化输出直接返回 CodeSolution"""
    import subprocess
    import sys
    import json

    project_root = '/mnt/f/PycharmProjects/neZha'
    script = f'''
import sys
import json
sys.path.insert(0, {repr(project_root)})
from utils.model import get_model
from langchain_core.messages import HumanMessage
from workflows.code_assistant.nodes.generate import CodeSolution

model = get_model()
structured_llm = model.with_structured_output(CodeSolution, include_raw=False)
result = structured_llm.invoke([HumanMessage(content={repr(prompt_text)})])
print(json.dumps({{"prefix": result.prefix, "imports": result.imports, "code": result.code}}, ensure_ascii=False))
'''
    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode == 0:
            data = json.loads(result.stdout.strip())
            return CodeSolution(**data)
        else:
            raise RuntimeError(f"Subprocess failed: {result.stderr}")
    except Exception as e:
        raise RuntimeError(f"Subprocess call failed: {e}")


def _format_generate_prompt(document: str, messages: list) -> str:
    """格式化生成请求的 prompt"""
    prompt_file = get_code_assistant_config().get("prompt_file", "code_assistant/generate.md")
    system_prompt = render_prompt_template(prompt_file, document=document, question="")

    msg_str = "\n".join([f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {m.content}" for m in messages])
    return f"{system_prompt}\n\n## 对话历史\n{msg_str}"


def create_generate_node(graph_state: Dict) -> Dict:
    """生成代码解决方案"""
    logger.info("--- 正在生成代码解决方案 ---")

    original_messages = graph_state["messages"]
    messages = []
    for msg in original_messages:
        if hasattr(msg, 'content'):
            messages.append(type(msg)(msg.content))
        else:
            messages.append(msg)

    document = graph_state["document"]
    logger.info(f"generate 输入: iterations={graph_state['iterations']}, messages数={len(messages)}, document长度={len(document)}")

    try:
        prompt_text = _format_generate_prompt(document, messages)
        logger.info(f"调用 LLM (subprocess), messages数={len(messages)}")

        solution = _invoke_in_subprocess(prompt_text)
        logger.info(f"解析成功: code={solution.code[:50]}...")

        messages = messages + [
            AIMessage(content=f"{solution.prefix}\n\n导入: {solution.imports}\n\n代码: {solution.code}")
        ]

        result = {
            "generation": {"prefix": solution.prefix, "imports": solution.imports, "code": solution.code},
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
