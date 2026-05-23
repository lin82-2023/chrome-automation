"""LLM Provider 单元测试

通过 mock httpx 验证：
1. OpenAICompatLLM 协议构造与响应解析
2. AnthropicLLM 协议构造与响应解析
3. create_llm 工厂行为
4. tool 调用 → 返回值标准化
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from chrome_agent_core.agent.tool import ToolDefinition
from chrome_agent_core.errors import LLMError
from chrome_agent_core.llm import (
    AnthropicLLM,
    BailianLLM,
    BaseLLM,
    DeepSeekLLM,
    GroqLLM,
    MoonshotLLM,
    OllamaLLM,
    OpenAICompatLLM,
    OpenAILLM,
    OpenRouterLLM,
    ZhipuLLM,
    create_llm,
    list_providers,
)

# ── 工厂与注册表 ───────────────────────────────────────────────────────


def test_list_providers_contains_main_vendors():
    names = set(list_providers())
    assert {
        "bailian", "openai", "anthropic", "deepseek",
        "moonshot", "zhipu", "openrouter", "groq", "ollama",
    } <= names


@pytest.mark.parametrize(
    "provider, env_var, cls",
    [
        ("bailian", "DASHSCOPE_API_KEY", BailianLLM),
        ("openai", "OPENAI_API_KEY", OpenAILLM),
        ("anthropic", "ANTHROPIC_API_KEY", AnthropicLLM),
        ("deepseek", "DEEPSEEK_API_KEY", DeepSeekLLM),
        ("moonshot", "MOONSHOT_API_KEY", MoonshotLLM),
        ("zhipu", "ZHIPU_API_KEY", ZhipuLLM),
        ("openrouter", "OPENROUTER_API_KEY", OpenRouterLLM),
        ("groq", "GROQ_API_KEY", GroqLLM),
    ],
)
def test_create_llm_picks_correct_class_and_env(monkeypatch, provider, env_var, cls):
    monkeypatch.setenv(env_var, "test-key")
    llm = create_llm(provider)
    assert isinstance(llm, cls)
    assert isinstance(llm, BaseLLM)
    assert llm.api_key == "test-key"


def test_create_llm_aliases(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("MOONSHOT_API_KEY", "k")
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k")
    assert isinstance(create_llm("claude"), AnthropicLLM)
    assert isinstance(create_llm("kimi"), MoonshotLLM)
    assert isinstance(create_llm("glm"), ZhipuLLM)
    assert isinstance(create_llm("dashscope"), BailianLLM)


def test_create_llm_unknown_raises():
    with pytest.raises(LLMError):
        create_llm("not-a-provider", api_key="x")


def test_ollama_does_not_require_key(monkeypatch):
    # 显式删除可能存在的环境变量
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    llm = create_llm("ollama")
    assert isinstance(llm, OllamaLLM)
    assert llm.api_key  # 占位 "ollama" 非空


def test_provider_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHROME_AGENT_API_KEY", raising=False)
    with pytest.raises(LLMError):
        create_llm("openai")


# ── OpenAICompatLLM 协议 ────────────────────────────────────────────────


def _mock_response(json_payload: dict, status: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://example.invalid/chat/completions")
    return httpx.Response(status, json=json_payload, request=request)


@pytest.mark.asyncio
async def test_openai_compat_chat_text_only(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_post(self, url, headers=None, json=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _mock_response(
            {"choices": [{"message": {"content": "hello world"}}]}
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    llm = OpenAILLM(api_key="sk-test", model="gpt-4o-mini")
    out = await llm.chat([{"role": "user", "content": "hi"}], temperature=0.3)

    assert out == {"content": "hello world"}
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"]["model"] == "gpt-4o-mini"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["json"]["temperature"] == 0.3


@pytest.mark.asyncio
async def test_openai_compat_chat_with_tool_calls(monkeypatch):
    async def fake_post(self, url, headers=None, json=None, **kwargs):
        return _mock_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "navigate",
                                        "arguments": '{"url": "https://x.com"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    tools = [
        ToolDefinition(
            name="navigate",
            label="Navigate",
            description="Go to a URL",
            parameters={"url": {"type": "string", "required": True}},
            execute=lambda **k: None,
        )
    ]
    llm = DeepSeekLLM(api_key="dsk-x")
    out = await llm.chat([{"role": "user", "content": "open x"}], tools=tools)
    assert out["content"] == ""
    assert out["tool_calls"] == [
        {"id": "call_1", "name": "navigate", "arguments": {"url": "https://x.com"}}
    ]


@pytest.mark.asyncio
async def test_openai_compat_error_raises(monkeypatch):
    async def fake_post(self, url, headers=None, json=None, **kwargs):
        return _mock_response({"error": {"message": "bad request"}}, status=400)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    llm = OpenAILLM(api_key="x")
    with pytest.raises(LLMError, match="bad request"):
        await llm.chat([{"role": "user", "content": "hi"}])


def test_openai_compat_build_tools_spec_shape():
    tools = [
        ToolDefinition(
            name="click",
            label="Click",
            description="Click an element",
            parameters={
                "selector": {"type": "string", "required": True, "description": "css"},
                "timeout": {"type": "integer"},
            },
            execute=lambda **k: None,
        )
    ]
    spec = OpenAICompatLLM._build_tools_spec(tools)
    assert spec[0]["type"] == "function"
    fn = spec[0]["function"]
    assert fn["name"] == "click"
    assert fn["parameters"]["properties"]["selector"]["type"] == "string"
    assert "selector" in fn["parameters"]["required"]
    assert "timeout" not in fn["parameters"]["required"]


def test_openai_compat_message_normalization():
    messages = [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "1", "function": {"name": "f", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "1", "content": "ok"},
    ]
    out = OpenAICompatLLM._make_messages(messages)
    assert out[0]["role"] == "system"
    assert out[2]["tool_calls"][0]["id"] == "1"
    assert out[3] == {"role": "tool", "tool_call_id": "1", "content": "ok"}


# ── AnthropicLLM 协议 ──────────────────────────────────────────────────


def test_anthropic_split_system_messages():
    messages = [
        {"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "calling tool",
            "tool_calls": [{"id": "tu_1", "function": {"name": "f", "arguments": "{\"a\": 1}"}}],
        },
        {"role": "tool", "tool_call_id": "tu_1", "content": "result"},
    ]
    system, anth = AnthropicLLM._split_system_messages(messages)
    assert system == "you are helpful"
    assert anth[0] == {"role": "user", "content": "hello"}
    assert anth[1]["role"] == "assistant"
    blocks = anth[1]["content"]
    assert blocks[0] == {"type": "text", "text": "calling tool"}
    assert blocks[1] == {"type": "tool_use", "id": "tu_1", "name": "f", "input": {"a": 1}}
    # tool 角色 → user 中的 tool_result
    assert anth[2]["role"] == "user"
    assert anth[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tu_1",
        "content": "result",
    }


def test_anthropic_build_tools_spec_uses_input_schema():
    tools = [
        ToolDefinition(
            name="click",
            label="Click",
            description="Click an element",
            parameters={"selector": {"type": "string", "required": True}},
            execute=lambda **k: None,
        )
    ]
    spec = AnthropicLLM._build_tools_spec(tools)
    assert spec[0]["name"] == "click"
    # Anthropic 用 input_schema，不是 parameters
    assert "input_schema" in spec[0]
    assert spec[0]["input_schema"]["properties"]["selector"]["type"] == "string"
    assert "selector" in spec[0]["input_schema"]["required"]


def test_anthropic_parse_response_text_and_tool_use():
    raw = {
        "content": [
            {"type": "text", "text": "thinking..."},
            {"type": "tool_use", "id": "tu_1", "name": "navigate", "input": {"url": "https://x"}},
        ]
    }
    out = AnthropicLLM._parse_response(raw)
    assert out["content"] == "thinking..."
    assert out["tool_calls"] == [
        {"id": "tu_1", "name": "navigate", "arguments": {"url": "https://x"}}
    ]


@pytest.mark.asyncio
async def test_anthropic_chat_request_shape(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_post(self, url, headers=None, json=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _mock_response(
            {"content": [{"type": "text", "text": "ok"}]}
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    llm = AnthropicLLM(api_key="ant-key", model="claude-3-5-haiku-20241022")
    out = await llm.chat(
        [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
        ]
    )
    assert out == {"content": "ok"}
    assert captured["url"].endswith("/messages")
    assert captured["headers"]["x-api-key"] == "ant-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["model"] == "claude-3-5-haiku-20241022"
    assert captured["json"]["system"] == "be brief"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["json"]["max_tokens"] >= 1
