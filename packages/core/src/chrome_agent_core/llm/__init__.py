"""LLM 集成层

统一接口 :class:`BaseLLM`，同时内置多个主流 Provider：

OpenAI 兼容协议（共享 :class:`OpenAICompatLLM` 基类）：
    - :class:`BailianLLM`     阿里百炼 / DashScope
    - :class:`OpenAILLM`      OpenAI / Azure OpenAI / 任意 OpenAI 兼容代理
    - :class:`DeepSeekLLM`    DeepSeek
    - :class:`MoonshotLLM`    Moonshot Kimi
    - :class:`ZhipuLLM`       智谱 GLM
    - :class:`OpenRouterLLM`  OpenRouter 聚合网关
    - :class:`GroqLLM`        Groq 高速推理
    - :class:`OllamaLLM`      本地 Ollama

独立协议：
    - :class:`AnthropicLLM`   Anthropic Claude（Messages API）

便捷工厂：
    - :func:`create_llm`      按名字实例化任意 Provider
    - :data:`PROVIDER_REGISTRY` 名称 → 类的映射

例：
    >>> from chrome_agent_core.llm import create_llm
    >>> llm = create_llm("openai", model="gpt-4o-mini")
    >>> llm = create_llm("anthropic", model="claude-3-5-sonnet-20241022")
    >>> llm = create_llm("ollama", model="qwen2.5", base_url="http://localhost:11434/v1")
"""
from .anthropic import AnthropicLLM
from .bailian import BailianLLM
from .base import BaseLLM
from .deepseek import DeepSeekLLM
from .factory import PROVIDER_REGISTRY, create_llm, list_providers
from .groq import GroqLLM
from .moonshot import MoonshotLLM
from .ollama import OllamaLLM
from .openai import OpenAILLM
from .openai_compat import OpenAICompatLLM
from .openrouter import OpenRouterLLM
from .zhipu import ZhipuLLM

__all__ = [
    # 抽象
    "BaseLLM",
    "OpenAICompatLLM",
    # OpenAI 兼容协议 Provider
    "BailianLLM",
    "OpenAILLM",
    "DeepSeekLLM",
    "MoonshotLLM",
    "ZhipuLLM",
    "OpenRouterLLM",
    "GroqLLM",
    "OllamaLLM",
    # 独立协议
    "AnthropicLLM",
    # 工厂
    "create_llm",
    "list_providers",
    "PROVIDER_REGISTRY",
]
