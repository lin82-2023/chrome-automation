"""本地 Ollama LLM Provider（OpenAI 兼容）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class OllamaLLM(OpenAICompatLLM):
    """本地 Ollama（OpenAI 兼容端点）

    环境变量：``OLLAMA_API_KEY``（一般留空，Ollama 默认无鉴权 → 内部填写占位 ``ollama``）
    默认 base_url：``http://localhost:11434/v1``。
    支持模型：llama3.2 / qwen2.5 / mistral / phi4 等本地模型。
    """

    provider_name = "ollama"
    default_base_url = "http://localhost:11434/v1"
    default_model = "llama3.2"
    env_var = "OLLAMA_API_KEY"

    def _read_env_key(self) -> str:
        import os

        # Ollama 默认无鉴权；提供一个非空占位以满足基类校验
        return os.environ.get(self.env_var, "ollama")


__all__ = ["OllamaLLM"]
