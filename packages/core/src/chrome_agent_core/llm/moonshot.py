"""Moonshot (Kimi) LLM Provider（OpenAI 兼容）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class MoonshotLLM(OpenAICompatLLM):
    """Moonshot Kimi 开放平台

    环境变量：``MOONSHOT_API_KEY``
    支持模型：moonshot-v1-8k / moonshot-v1-32k / moonshot-v1-128k 等。
    """

    provider_name = "moonshot"
    default_base_url = "https://api.moonshot.cn/v1"
    default_model = "moonshot-v1-8k"
    env_var = "MOONSHOT_API_KEY"


__all__ = ["MoonshotLLM"]
