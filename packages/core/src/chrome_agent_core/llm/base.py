"""LLM 抽象基类

所有 Provider 都继承 :class:`BaseLLM`，对外暴露统一的 ``chat`` / ``stream_chat`` 方法。
返回值统一为：

    {"content": str, "tool_calls": [{"id": str, "name": str, "arguments": dict}, ...]}

当 LLM 没有产生工具调用时，``tool_calls`` 字段缺省。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ..agent.tool import ToolDefinition


class BaseLLM(ABC):
    """所有 LLM Provider 的统一接口"""

    #: 用于日志/调试的 Provider 名（如 "bailian" / "openai" / "anthropic"）
    provider_name: str = "base"

    #: 当前使用的模型名
    model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """单轮（非流式）补全。

        Returns:
            ``{"content": str}`` 或 ``{"content": str, "tool_calls": [...]}``。
        """

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式补全，逐 chunk 产出文本片段。"""

    def __repr__(self) -> str:  # pragma: no cover - 调试便利
        return f"<{self.__class__.__name__} provider={self.provider_name} model={self.model}>"


__all__ = ["BaseLLM"]
