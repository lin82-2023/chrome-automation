"""阿里百炼 / DashScope LLM Provider（OpenAI 兼容模式）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class BailianLLM(OpenAICompatLLM):
    """阿里云百炼 / DashScope（OpenAI 兼容模式）

    环境变量：``DASHSCOPE_API_KEY``
    支持模型：qwen-turbo / qwen-plus / qwen-max / qwen-long 等。
    """

    provider_name = "bailian"
    default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    default_model = "qwen-plus"
    env_var = "DASHSCOPE_API_KEY"


__all__ = ["BailianLLM"]
