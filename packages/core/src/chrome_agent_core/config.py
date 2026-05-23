#!/usr/bin/env python3
"""chrome-agent-core 配置加载

配置来源（优先级从高到低）：
1. 环境变量
   - ``CHROME_AGENT_PROVIDER`` / ``CHROME_AGENT_MODEL`` / ``CHROME_AGENT_BASE_URL``
   - ``CHROME_AGENT_API_KEY``（统一 fallback）
   - 各 Provider 专用 Key：``DASHSCOPE_API_KEY`` / ``OPENAI_API_KEY`` /
     ``ANTHROPIC_API_KEY`` / ``DEEPSEEK_API_KEY`` / ``MOONSHOT_API_KEY`` /
     ``ZHIPU_API_KEY`` / ``OPENROUTER_API_KEY`` / ``GROQ_API_KEY`` 等
   - ``BAILIAN_MODEL``（向后兼容）/ ``AGENT_SESSION_DIR``
2. 项目根 ``.chrome-agent.toml`` / 用户主目录 ``~/.chrome-agent/config.toml``
3. 内置默认值
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib  # type: ignore
else:
    import tomli as tomllib  # type: ignore


# ── Provider / 模型 元数据 ──────────────────────────────────────────────


#: provider → 该 provider 的默认 env_var
PROVIDER_ENV_VARS: dict[str, str] = {
    "bailian": "DASHSCOPE_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "glm": "ZHIPU_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}

#: 已知 provider 的默认模型（仅作 validate 提示，不做强校验）
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "bailian": "qwen-plus",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "deepseek": "deepseek-chat",
    "moonshot": "moonshot-v1-8k",
    "zhipu": "glm-4-flash",
    "openrouter": "openai/gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.2",
}

#: 百炼模型清单（旧 API，仅在 provider == bailian 时启用模型严格校验）
BAILIAN_MODELS = {
    "qwen-turbo": {"description": "快速、便宜，适合简单任务", "max_tokens": 8000},
    "qwen-plus":  {"description": "平衡，推荐", "max_tokens": 32000},
    "qwen-max":   {"description": "最强，复杂任务", "max_tokens": 128000},
    "qwen-long":  {"description": "长文本", "max_tokens": 1000000},
}

DEFAULT_PROVIDER = "bailian"
DEFAULT_MODEL = "qwen-long"
DEFAULT_SESSION_DIR = "~/.chrome-agent/sessions"

CONFIG_LOCATIONS = [
    Path.cwd() / ".chrome-agent.toml",
    Path.home() / ".chrome-agent" / "config.toml",
]


# ── Config 数据类 ────────────────────────────────────────────────────────


@dataclass
class Config:
    """运行时配置"""
    provider: str = DEFAULT_PROVIDER
    api_key: str = ""
    model: str = DEFAULT_MODEL
    base_url: str = ""  # 空字符串表示使用 Provider 默认 base_url
    session_dir: Path = field(default_factory=lambda: Path(DEFAULT_SESSION_DIR).expanduser())
    max_iterations: int = 20
    compact_threshold: int = 6000

    def ensure_session_dir(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> tuple[bool, str]:
        prov = (self.provider or "").lower().strip()
        if prov not in PROVIDER_ENV_VARS and prov != "ollama":
            return False, (
                f"未知 provider: {self.provider!r}（可选: "
                f"{sorted(set(PROVIDER_ENV_VARS))})"
            )

        # Ollama 默认无鉴权；其它 Provider 必须有 key
        if prov != "ollama" and not self.api_key:
            env_var = PROVIDER_ENV_VARS.get(prov, "API_KEY")
            return False, f"{env_var} 未设置（provider={self.provider}）"

        # 仅在 provider==bailian 时校验 model 是否在已知列表
        if prov in {"bailian", "dashscope"} and self.model not in BAILIAN_MODELS:
            return False, f"未知模型: {self.model}（可选: {sorted(BAILIAN_MODELS)}）"

        return True, "OK"


# ── 配置加载 ─────────────────────────────────────────────────────────────


def _load_toml() -> dict:
    """读取首个存在的配置文件并返回 dict（无文件返回空 dict）"""
    for path in CONFIG_LOCATIONS:
        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                return data.get("agent", data) if isinstance(data, dict) else {}
            except Exception:
                continue
    return {}


def _resolve_api_key(provider: str, file_cfg: dict) -> str:
    """按优先级解析 api_key：provider 专用 env_var > CHROME_AGENT_API_KEY > toml api_key"""
    # 1. 各 provider 专用环境变量（最精确）
    env_var = PROVIDER_ENV_VARS.get(provider.lower())
    if env_var:
        key = os.environ.get(env_var, "")
        if key:
            return key
    # 2. 通用 fallback
    key = os.environ.get("CHROME_AGENT_API_KEY", "")
    if key:
        return key
    # 3. 配置文件
    return file_cfg.get("api_key", "")


def _resolve_model(provider: str, file_cfg: dict) -> str:
    # 显式覆盖
    explicit = os.environ.get("CHROME_AGENT_MODEL") or file_cfg.get("model")
    if explicit:
        return explicit
    # 向后兼容：BAILIAN_MODEL
    legacy = os.environ.get("BAILIAN_MODEL")
    if legacy:
        return legacy
    return PROVIDER_DEFAULT_MODELS.get(provider.lower(), DEFAULT_MODEL)


def _build_config() -> Config:
    file_cfg = _load_toml()

    provider = (
        os.environ.get("CHROME_AGENT_PROVIDER")
        or file_cfg.get("provider")
        or DEFAULT_PROVIDER
    ).lower()

    api_key = _resolve_api_key(provider, file_cfg)
    model = _resolve_model(provider, file_cfg)
    base_url = os.environ.get("CHROME_AGENT_BASE_URL", file_cfg.get("base_url", ""))

    session_dir = Path(
        os.environ.get(
            "AGENT_SESSION_DIR",
            file_cfg.get("session_dir", DEFAULT_SESSION_DIR),
        )
    ).expanduser()
    max_iterations = int(file_cfg.get("max_iterations", 20))
    compact_threshold = int(file_cfg.get("compact_threshold", 6000))

    return Config(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        session_dir=session_dir,
        max_iterations=max_iterations,
        compact_threshold=compact_threshold,
    )


_config: Config | None = None


def get_config() -> Config:
    """获取全局配置（单例）"""
    global _config
    if _config is None:
        _config = _build_config()
    return _config


def reset_config() -> None:
    """重置配置缓存（用于测试）"""
    global _config
    _config = None


def validate_config() -> tuple[bool, str]:
    """验证配置完整性"""
    return get_config().validate()


__all__ = [
    "Config",
    "BAILIAN_MODELS",
    "PROVIDER_ENV_VARS",
    "PROVIDER_DEFAULT_MODELS",
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL",
    "get_config",
    "reset_config",
    "validate_config",
]
