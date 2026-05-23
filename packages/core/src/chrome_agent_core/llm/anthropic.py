"""Anthropic Claude LLM Provider（独立 Messages API）

Anthropic 不兼容 OpenAI 协议，需要单独 adapter：
- 路径：``POST /v1/messages``
- 请求头：``x-api-key`` + ``anthropic-version: 2023-06-01``
- ``system`` 是 top-level 字段，不出现在 ``messages`` 数组中
- 工具使用 ``input_schema`` 而非 ``parameters``
- 响应是 ``content: [{type: "text"|"tool_use", ...}]`` 数组

文档：https://docs.anthropic.com/claude/reference/messages_post
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..agent.tool import ToolDefinition
from ..errors import LLMError, LLMTimeoutError
from .base import BaseLLM


class AnthropicLLM(BaseLLM):
    """Anthropic Claude（Messages API）

    环境变量：``ANTHROPIC_API_KEY``
    支持模型：claude-3-5-sonnet-20241022 / claude-3-5-haiku-20241022 / claude-opus-4 等。
    """

    provider_name = "anthropic"
    default_base_url = "https://api.anthropic.com/v1"
    default_model = "claude-3-5-haiku-20241022"
    env_var = "ANTHROPIC_API_KEY"
    api_version = "2023-06-01"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_tokens: int = 4096,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        import os

        self.api_key = api_key or os.environ.get(self.env_var, "")
        self.model = model or self.default_model
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.extra_headers = extra_headers or {}

        if not self.api_key:
            raise LLMError(
                f"anthropic API Key 未设置，请通过参数传入或设置环境变量 {self.env_var}"
            )

    # ── 请求构造 ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }
        h.update(self.extra_headers)
        return h

    @staticmethod
    def _split_system_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """从消息列表中拆出 system，并把其余消息转换为 Anthropic 期望的 ``user/assistant`` 形态"""
        system_parts: list[str] = []
        out: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                content = msg.get("content", "")
                if content:
                    system_parts.append(content)
            elif role == "tool":
                # OpenAI 风格的 tool 角色 → Anthropic 通过 user 消息中的 tool_result 块表达
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": msg.get("content", ""),
                            }
                        ],
                    }
                )
            elif role == "assistant":
                blocks: list[dict] = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg.get("tool_calls") or []:
                    func = tc.get("function") or {}
                    args = func.get("arguments") or tc.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name") or tc.get("name", ""),
                            "input": args,
                        }
                    )
                out.append({"role": "assistant", "content": blocks or msg.get("content", "")})
            else:  # user / 其他
                out.append({"role": "user", "content": msg.get("content", "")})
        return "\n\n".join(system_parts), out

    @staticmethod
    def _build_tools_spec(tools: list[ToolDefinition]) -> list[dict]:
        result: list[dict] = []
        for t in tools:
            schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
            for name, spec in (t.parameters or {}).items():
                schema["properties"][name] = {
                    "type": spec.get("type", "string"),
                    "description": spec.get("description", ""),
                }
                if spec.get("required"):
                    schema["required"].append(name)
            result.append(
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": schema,
                }
            )
        return result

    @staticmethod
    def _parse_response(result: dict) -> dict[str, Any]:
        content_text_parts: list[str] = []
        tool_calls: list[dict] = []
        for block in result.get("content", []) or []:
            btype = block.get("type")
            if btype == "text":
                content_text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id", f"call_{int(time.time() * 1000)}"),
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}) or {},
                    }
                )
        out: dict[str, Any] = {"content": "".join(content_text_parts)}
        if tool_calls:
            out["tool_calls"] = tool_calls
        return out

    # ── 公共 API ────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> dict[str, Any]:
        system, anth_messages = self._split_system_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
            "temperature": temperature,
            "messages": anth_messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = self._build_tools_spec(tools)
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"anthropic 请求超时: {e}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"anthropic 网络错误: {e}") from e

        if response.status_code != 200:
            try:
                err = response.json().get("error", {})
                msg = err.get("message") or response.text
            except Exception:
                msg = response.text
            raise LLMError(f"anthropic API 调用失败: {response.status_code} - {msg}")

        return self._parse_response(response.json())

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        system, anth_messages = self._split_system_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
            "temperature": temperature,
            "messages": anth_messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = self._build_tools_spec(tools)
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        evt = json.loads(data)
                    except Exception:
                        continue
                    if evt.get("type") == "content_block_delta":
                        delta = evt.get("delta", {}) or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield text


__all__ = ["AnthropicLLM"]
