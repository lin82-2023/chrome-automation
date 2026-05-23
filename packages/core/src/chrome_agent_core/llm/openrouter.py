"""OpenRouter 聚合网关 LLM Provider（OpenAI 兼容）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class OpenRouterLLM(OpenAICompatLLM):
    """OpenRouter（聚合 OpenAI / Anthropic / Google / Meta 等数百模型）

    环境变量：``OPENROUTER_API_KEY``
    模型名遵循 ``vendor/model`` 格式，例如：
        - openai/gpt-4o-mini
        - anthropic/claude-3.5-sonnet
        - google/gemini-2.0-flash-001
        - meta-llama/llama-3.3-70b-instruct
    """

    provider_name = "openrouter"
    default_base_url = "https://openrouter.ai/api/v1"
    default_model = "openai/gpt-4o-mini"
    env_var = "OPENROUTER_API_KEY"


__all__ = ["OpenRouterLLM"]
