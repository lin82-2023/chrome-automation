"""OpenAI 兼容协议的通用实现

支持任何遵循 OpenAI Chat Completions 协议的 Provider：
- 阿里百炼 DashScope（compatible-mode）
- OpenAI / Azure OpenAI
- DeepSeek
- Moonshot (Kimi)
- 智谱 GLM (open.bigmodel.cn)
- OpenRouter
- Groq
- Together / SiliconFlow / Ollama 等

子类只需在 ``__init__`` 中提供：``base_url`` / ``default_model`` / ``env_var``。
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


class OpenAICompatLLM(BaseLLM):
    """OpenAI Chat Completions 兼容协议的通用客户端"""

    #: 默认 base_url（子类覆盖）
    default_base_url: str = "https://api.openai.com/v1"
    #: 默认模型（子类覆盖）
    default_model: str = "gpt-4o-mini"
    #: 该 Provider 默认读取的环境变量名
    env_var: str = "OPENAI_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key or self._read_env_key()
        self.model = model or self.default_model
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

        if not self.api_key:
            raise LLMError(
                f"{self.provider_name} API Key 未设置，请通过参数传入或设置环境变量 {self.env_var}"
            )
        # 提早拦截非 ASCII 的 key（粘贴时混入中文引号/全角空格/BOM 等），
        # 否则会在 HTTP 层抛 "'ascii' codec can't encode" 这种隐晦错误。
        self.api_key = self.api_key.strip()
        try:
            self.api_key.encode("ascii")
        except UnicodeEncodeError as e:
            bad = [(i, c, hex(ord(c))) for i, c in enumerate(self.api_key) if ord(c) > 127]
            raise LLMError(
                f"{self.provider_name} API Key 含非 ASCII 字符（可能是复制时混入了中文引号/全角空格/BOM）。"
                f"位置: {bad[:5]}（仅显示前 5 个）。请在终端重新设置 {self.env_var}。"
            ) from e

    # ── 子类钩子 ────────────────────────────────────────────────────────

    def _read_env_key(self) -> str:
        import os

        return os.environ.get(self.env_var, "")

    # ── 协议构建 ────────────────────────────────────────────────────────

    @staticmethod
    def _build_tools_spec(tools: list[ToolDefinition]) -> list[dict]:
        """ToolDefinition → OpenAI function tools schema"""
        result: list[dict] = []
        for t in tools:
            params: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
            for name, spec in (t.parameters or {}).items():
                params["properties"][name] = {
                    "type": spec.get("type", "string"),
                    "description": spec.get("description", ""),
                }
                if spec.get("required"):
                    params["required"].append(name)
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": params,
                    },
                }
            )
        return result

    @staticmethod
    def _make_messages(messages: list[dict]) -> list[dict]:
        """规范化为 OpenAI 兼容消息格式"""
        result: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                result.append({"role": "system", "content": msg.get("content", "")})
            elif role == "user":
                result.append({"role": "user", "content": msg.get("content", "")})
            elif role == "assistant":
                item: dict[str, Any] = {"role": "assistant", "content": msg.get("content", "")}
                if msg.get("tool_calls"):
                    # 内部扁平格式 {"id", "name", "arguments"} → OpenAI 标准格式
                    openai_tool_calls = []
                    for tc in msg["tool_calls"]:
                        # 如果已经是 OpenAI 格式则直通
                        if "function" in tc:
                            openai_tool_calls.append(tc)
                        else:
                            name = tc.get("name", "")
                            arguments = tc.get("arguments", {})
                            if isinstance(arguments, dict):
                                arguments = json.dumps(arguments, ensure_ascii=False)
                            openai_tool_calls.append(
                                {
                                    "id": tc.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": arguments,
                                    },
                                }
                            )
                    item["tool_calls"] = openai_tool_calls
                result.append(item)
            elif role == "tool":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id"),
                        "content": msg.get("content", ""),
                    }
                )
        return result

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        h.update(self.extra_headers)
        return h

    @classmethod
    def _parse_response(cls, result: dict) -> dict[str, Any]:
        choices = result.get("choices") or []
        if not choices:
            return {"content": str(result)}

        message = choices[0].get("message", {}) or {}
        content = message.get("content", "") or ""

        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = []
            for tc in message["tool_calls"]:
                func = tc.get("function", {}) or {}
                name = func.get("name") or tc.get("function_name", "")
                arguments = func.get("arguments", "{}")
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except Exception:
                        arguments = {}
                tool_calls.append(
                    {
                        "id": tc.get("id", f"call_{int(time.time() * 1000)}"),
                        "name": name,
                        "arguments": arguments,
                    }
                )
            return {"content": content, "tool_calls": tool_calls}

        return {"content": content}

    # ── 公共 API ────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._make_messages(messages),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = self._build_tools_spec(tools)
        # 透传额外参数（如 max_tokens / top_p / response_format ...）
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"{self.provider_name} 请求超时: {e}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"{self.provider_name} 网络错误: {e}") from e

        if response.status_code != 200:
            try:
                err = response.json().get("error", {})
                msg = err.get("message") or response.text
            except Exception:
                msg = response.text
            raise LLMError(f"{self.provider_name} API 调用失败: {response.status_code} - {msg}")

        return self._parse_response(response.json())

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._make_messages(messages),
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = self._build_tools_spec(tools)
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                    except Exception:
                        continue
                    choices = parsed.get("choices", [])
                    if not choices:
                        continue
                    # OpenAI 流式：delta.content；少数 Provider：message.content
                    delta = (
                        choices[0].get("delta", {}).get("content")
                        or choices[0].get("message", {}).get("content")
                        or ""
                    )
                    if delta:
                        yield delta


__all__ = ["OpenAICompatLLM"]
