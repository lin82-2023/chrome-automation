"""DeepSeek LLM Provider（OpenAI 兼容）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class DeepSeekLLM(OpenAICompatLLM):
    """DeepSeek 平台 API

    环境变量：``DEEPSEEK_API_KEY``
    支持模型：deepseek-chat / deepseek-reasoner 等。
    """

    provider_name = "deepseek"
    default_base_url = "https://api.deepseek.com/v1"
    default_model = "deepseek-chat"
    env_var = "DEEPSEEK_API_KEY"


__all__ = ["DeepSeekLLM"]
