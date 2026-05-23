"""OpenAI / Azure OpenAI LLM Provider"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class OpenAILLM(OpenAICompatLLM):
    """OpenAI 官方 API

    环境变量：``OPENAI_API_KEY``
    支持模型：gpt-4o / gpt-4o-mini / gpt-4.1 / o3-mini 等。
    可通过 ``base_url`` 指向 Azure OpenAI 或代理网关。
    """

    provider_name = "openai"
    default_base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o-mini"
    env_var = "OPENAI_API_KEY"


__all__ = ["OpenAILLM"]
