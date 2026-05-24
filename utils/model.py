"""模型工厂

支持多 Provider 统一调用：
- OpenAI 兼容（openai, volcengine, minimax, zhipu, moonshot, deepseek, local, openrouter）
- 专用 SDK（anthropic, google, dashscope-aliyun）
"""

import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from .config import get_model_config
from .exceptions import ConfigError
from .logging import get_logger

logger = get_logger("nezha.model")

# OpenAI 兼容厂商的默认 base_url
OPENAI_COMPAT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "minimax": "https://api.minimax.chat/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "local": "http://localhost:1234/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "dashscope-aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def get_config_value(value: str) -> str:
    """获取配置值，支持 ${ENV_VAR} 格式的环境变量"""
    if not value:
        return value
    if value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        val = os.getenv(env_key, "")
        if not val:
            raise ConfigError(f"环境变量 {env_key} 未设置或值为空")
        return val
    return value


def get_api_key(config: dict) -> str:
    api_key = config.get("api_key", "")
    if not api_key:
        raise ConfigError("api_key 未设置或配置为空")
    return get_config_value(api_key)


def get_base_url(config: dict, default: str = None) -> str:
    base_url = config.get("base_url", default)
    if not base_url or base_url.lower() == "null":
        return default
    return get_config_value(base_url)


def load_model():
    config = get_model_config()
    if not config:
        raise ConfigError("config.yaml 缺少 model 配置项")
    provider = config.get("provider")
    if not provider:
        raise ConfigError("model.yaml 缺少 provider 配置项")
    api_key = get_api_key(config)
    base_url = get_base_url(config)
    logger.info(f"初始化模型 provider={provider}, model={config.get('model')}, base_url={base_url}")

    # OpenAI 兼容厂商
    if provider in OPENAI_COMPAT_BASE_URLS:
        final_base_url = base_url or OPENAI_COMPAT_BASE_URLS[provider]
        # enable_thinking 仅对明确支持的 provider 启用
        supported_thinking = {"deepseek", "openai"}
        model_kwargs = {"extra_body": {"enable_thinking": False}} if provider not in supported_thinking else {}
        return ChatOpenAI(
            model=config["model"],
            api_key=api_key,
            base_url=final_base_url,
            **model_kwargs,
        )

    # 专用 SDK
    elif provider == "anthropic":
        return ChatAnthropic(
            model=config["model"],
            api_key=api_key,
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=config["model"],
            api_key=api_key,
        )

    raise ValueError(f"未知模型提供商: {provider}")


# 延迟初始化模型，避免 import 时因配置错误导致应用崩溃
_model_instance = None


def get_model() -> ChatOpenAI:
    """获取模型实例（延迟初始化）"""
    global _model_instance
    if _model_instance is None:
        _model_instance = load_model()
    return _model_instance


class LazyModel:
    """延迟加载的模型代理类"""
    def __call__(self, *args, **kwargs):
        return get_model()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_model(), name)


MODEL = LazyModel()