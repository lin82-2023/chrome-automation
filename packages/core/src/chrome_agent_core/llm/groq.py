"""Groq 高速推理 LLM Provider（OpenAI 兼容）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class GroqLLM(OpenAICompatLLM):
    """Groq 高速推理云

    环境变量：``GROQ_API_KEY``
    支持模型：llama-3.3-70b-versatile / mixtral-8x7b-32768 等。
    """

    provider_name = "groq"
    default_base_url = "https://api.groq.com/openai/v1"
    default_model = "llama-3.3-70b-versatile"
    env_var = "GROQ_API_KEY"


__all__ = ["GroqLLM"]
