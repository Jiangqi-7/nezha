"""neZha 异常类定义

异常层次：
- NezhaError: 基础异常，所有 neZha 异常的父类
  - RoleNotFoundError: 角色不存在
  - ConfigError: 配置错误
    - PromptFileNotFoundError: 提示词文件不存在
    - PromptReadError: 提示词文件读取失败
  - ModelInvokeError: 模型调用失败
  - EmptyResponseError: 模型返回空内容
"""


class NezhaError(Exception):
    """基础异常"""
    code = 500
    message = "服务器内部错误"

    def __init__(self, message=None, detail=None):
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)


class RoleNotFoundError(NezhaError):
    """角色不存在，校验角色配置时抛出"""
    code = 404
    message = "角色不存在"


class ConfigError(NezhaError):
    """配置错误，配置项缺失或无效时抛出"""
    code = 500
    message = "配置错误"


class PromptFileNotFoundError(ConfigError):
    """提示词文件不存在，启动时校验配置时抛出"""
    code = 500
    message = "提示词文件不存在"


class PromptReadError(ConfigError):
    """提示词文件读取失败，运行时读取文件异常时抛出"""
    code = 500
    message = "提示词文件读取失败"


class ModelInvokeError(NezhaError):
    """模型调用失败，LLM API 调用异常时抛出"""
    code = 500
    message = "模型调用失败"


class EmptyResponseError(NezhaError):
    """模型返回空内容，LLM 返回内容为空时抛出"""
    code = 500
    message = "模型返回空内容"