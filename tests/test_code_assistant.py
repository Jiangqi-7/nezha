"""代码助手工作流测试"""
import pytest


class TestCodeAssistant:
    """代码助手工作流测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from workflows.code_assistant import code_assistant_invoke
        assert callable(code_assistant_invoke)

    def test_simple_code_generation(self):
        """测试简单代码生成"""
        from workflows.code_assistant import code_assistant_invoke

        result = code_assistant_invoke("写一个函数反转字符串")
        assert result["error"] == "no"
        assert result["iterations"] == 1
        assert "code" in result["generation"]
        assert "reverse" in result["generation"]["code"]

    def test_code_with_imports(self):
        """测试带导入的代码生成"""
        from workflows.code_assistant import code_assistant_invoke

        result = code_assistant_invoke("写一个函数计算斐波那契数列")
        assert result["error"] == "no"
        assert "code" in result["generation"]
        assert "fibonacci" in result["generation"]["code"].lower() or "fib" in result["generation"]["code"].lower()

    def test_reflect_on_error(self):
        """测试错误时的反思流程"""
        from workflows.code_assistant import code_assistant_invoke

        result = code_assistant_invoke("请写一个函数，故意写一个会引发 NameError 的代码")
        # 应该能达到 max_iterations，error=yes
        assert result["iterations"] == 3
        assert result["error"] == "yes"
        # messages 应该包含用户输入、生成结果、反思内容
        assert len(result["messages"]) > 2

    def test_generation_has_prefix(self):
        """测试生成结果包含 prefix"""
        from workflows.code_assistant import code_assistant_invoke

        result = code_assistant_invoke("写一个函数计算列表元素之和")
        assert "prefix" in result["generation"]
        assert len(result["generation"]["prefix"]) > 0


class TestModelConfig:
    """模型配置测试"""

    def test_model_config_loads(self):
        """测试模型配置可正常加载"""
        from utils.config import get_model_config

        config = get_model_config()
        assert "provider" in config
        assert "model" in config
        assert config["provider"] == "dashscope-aliyun"

    def test_code_assistant_config(self):
        """测试代码助手配置"""
        from utils.config import get_code_assistant_config

        config = get_code_assistant_config()
        assert "max_iterations" in config
        assert "prompt_file" in config
        assert config["max_iterations"] == 3