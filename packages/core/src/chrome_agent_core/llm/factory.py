"""Provider 注册表与 ``create_llm`` 工厂"""
from __future__ import annotations

from typing import Any

from ..errors import LLMError
from .anthropic import AnthropicLLM
from .bailian import BailianLLM
from .base import BaseLLM
from .deepseek import DeepSeekLLM
from .groq import GroqLLM
from .moonshot import MoonshotLLM
from .ollama import OllamaLLM
from .openai import OpenAILLM
from .openrouter import OpenRouterLLM
from .zhipu import ZhipuLLM

#: provider 名 → Provider 类
PROVIDER_REGISTRY: dict[str, type[BaseLLM]] = {
    "bailian": BailianLLM,
    "dashscope": BailianLLM,  # 别名
    "openai": OpenAILLM,
    "anthropic": AnthropicLLM,
    "claude": AnthropicLLM,  # 别名
    "deepseek": DeepSeekLLM,
    "moonshot": MoonshotLLM,
    "kimi": MoonshotLLM,  # 别名
    "zhipu": ZhipuLLM,
    "glm": ZhipuLLM,  # 别名
    "openrouter": OpenRouterLLM,
    "groq": GroqLLM,
    "ollama": OllamaLLM,
}


def list_providers() -> list[str]:
    """返回主键列表（去除别名，按字母序）"""
    primary = {
        "bailian", "openai", "anthropic", "deepseek",
        "moonshot", "zhipu", "openrouter", "groq", "ollama",
    }
    return sorted(primary)


def create_llm(
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> BaseLLM:
    """根据名称创建 LLM 客户端

    Args:
        provider: ``bailian`` / ``openai`` / ``anthropic`` / ``deepseek`` /
                  ``moonshot`` / ``zhipu`` / ``openrouter`` / ``groq`` / ``ollama``。
                  为 ``None`` 时回退到全局配置（``Config.provider``）。
        api_key:  覆盖 API Key；为空时从该 Provider 默认环境变量读取。
        model:    覆盖模型名；为空时使用各 Provider ``default_model``。
        base_url: 覆盖请求基址；为空时使用各 Provider ``default_base_url``。
        **kwargs: 透传给 Provider 构造器（如 ``timeout``/``extra_headers``/``max_tokens``）。

    Raises:
        LLMError: 未知的 provider 名。
    """
    if provider is None:
        # 延迟导入避免循环依赖
        from ..config import get_config

        provider = get_config().provider

    key = (provider or "").strip().lower()
    cls = PROVIDER_REGISTRY.get(key)
    if cls is None:
        raise LLMError(
            f"未知的 LLM provider: {provider!r}。"
            f"可选: {list_providers()}"
        )
    return cls(api_key=api_key, model=model, base_url=base_url, **kwargs)


__all__ = [
    "PROVIDER_REGISTRY",
    "create_llm",
    "list_providers",
]
