"""配置加载测试"""

import pytest
from chrome_agent_core.config import (
    BAILIAN_MODELS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    PROVIDER_ENV_VARS,
    Config,
    get_config,
    reset_config,
    validate_config,
)


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """每个测试前后重置配置缓存，并清掉所有可能干扰的 LLM 环境变量"""
    for var in {
        "CHROME_AGENT_PROVIDER", "CHROME_AGENT_MODEL",
        "CHROME_AGENT_BASE_URL", "CHROME_AGENT_API_KEY",
        "BAILIAN_MODEL",
        *PROVIDER_ENV_VARS.values(),
    }:
        monkeypatch.delenv(var, raising=False)
    reset_config()
    yield
    reset_config()


def test_default_model_in_models():
    assert DEFAULT_MODEL in BAILIAN_MODELS


def test_default_provider_is_bailian():
    assert DEFAULT_PROVIDER == "bailian"


def test_validate_without_api_key(monkeypatch):
    monkeypatch.chdir("/tmp")  # 避免读到项目根 .chrome-agent.toml
    monkeypatch.setattr(
        "chrome_agent_core.config.CONFIG_LOCATIONS",
        [],
    )
    reset_config()
    ok, msg = validate_config()
    assert not ok
    assert "API_KEY" in msg or "DASHSCOPE" in msg


def test_validate_with_api_key(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    ok, msg = validate_config()
    assert ok, msg


def test_unknown_model(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")
    monkeypatch.setenv("BAILIAN_MODEL", "no-such-model")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    ok, msg = validate_config()
    assert not ok
    assert "未知模型" in msg


def test_get_config_singleton(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2
    assert isinstance(c1, Config)


def test_provider_switch_via_env(monkeypatch):
    """切换 provider 后，应使用对应的环境变量取 api_key"""
    monkeypatch.setenv("CHROME_AGENT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    cfg = get_config()
    assert cfg.provider == "openai"
    assert cfg.api_key == "sk-openai"
    ok, _ = cfg.validate()
    assert ok  # OpenAI 不强校验 model


def test_chrome_agent_api_key_fallback(monkeypatch):
    """CHROME_AGENT_API_KEY 应作为通用兜底（在 provider 专用 env_var 缺失时）"""
    monkeypatch.setenv("CHROME_AGENT_PROVIDER", "deepseek")
    monkeypatch.setenv("CHROME_AGENT_API_KEY", "fallback-key")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    cfg = get_config()
    assert cfg.provider == "deepseek"
    assert cfg.api_key == "fallback-key"


def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("CHROME_AGENT_PROVIDER", "no-such-provider")
    monkeypatch.setenv("CHROME_AGENT_API_KEY", "x")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    ok, msg = validate_config()
    assert not ok
    assert "未知 provider" in msg


def test_ollama_does_not_require_api_key(monkeypatch):
    monkeypatch.setenv("CHROME_AGENT_PROVIDER", "ollama")
    monkeypatch.setattr("chrome_agent_core.config.CONFIG_LOCATIONS", [])
    reset_config()
    ok, msg = validate_config()
    assert ok, msg
