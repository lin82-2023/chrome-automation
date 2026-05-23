# Chrome Agent Workspace — 开发指南（CLAUDE.md）

> 给 AI 协作者（含 Claude / Qoder / Codex 等）阅读的项目规范。
> 仓库为 **uv workspace monorepo**，包含 `chrome-agent-core` 与 `chrome-research` 两个独立可发布的包。

## 1. 项目定位

- **chrome-agent-core**：基于 Chrome DevTools Protocol (CDP) 的浏览器自动化引擎 + LLM/Tool/AgentSession 框架。
- **chrome-research**：建立在 core 之上的多步深度调研 Agent（plan → execute → synthesize）。

## 2. 技术栈

- Python `>=3.10`
- 包管理与构建：[uv](https://docs.astral.sh/uv/) workspace + `hatchling`
- CDP 通信：`websockets` + `httpx`
- LLM Provider：内置 9 种（`bailian` / `openai` / `anthropic` / `deepseek` / `moonshot` / `zhipu` / `openrouter` / `groq` / `ollama`），通过 `BaseLLM` 抽象 + `OpenAICompatLLM`（OpenAI Chat Completions 兼容协议）+ 独立 `AnthropicLLM`（Messages API）实现，统一用 `httpx` 异步发起请求
- Lint / Format / Type / Test：`ruff` / `mypy` / `pytest`（asyncio_mode=auto）+ `pytest-asyncio` + `pytest-mock`
- CI：GitHub Actions（`tests.yml` matrix py3.10/3.11/3.12，`publish.yml` 按 `v*.*.*` tag 发布）

## 3. 仓库布局

```
.
├── pyproject.toml                # workspace 根：uv workspace + ruff/mypy/pytest 全局配置
├── uv.lock
├── packages/
│   ├── core/                     # chrome-agent-core
│   │   ├── pyproject.toml
│   │   ├── src/chrome_agent_core/
│   │   │   ├── cdp/              # CDP 引擎（_engine 连接 / navigation / element / input / tab / window / events）
│   │   │   ├── browser/          # Chrome 启动/检测（ensure_chrome / check_chrome_installed）
│   │   │   ├── stealth/          # 反指纹、反检测脚本
│   │   │   ├── session/          # SessionManager / save_session / load_session / wait_for_manual_login
│   │   │   ├── llm/              # base / openai_compat / anthropic / bailian / openai / deepseek / moonshot / zhipu / openrouter / groq / ollama / factory
│   │   │   ├── tools/            # browser_tools / session_tools / register_all_tools
│   │   │   ├── agent/            # tool / tool_registry / message / session(AgentSession) / compaction / system_prompt / persistence
│   │   │   ├── config.py         # @dataclass Config + TOML 加载 + reset_config()
│   │   │   ├── errors.py         # ChromeAgentError 异常体系
│   │   │   ├── logging.py        # setup_logging / get_logger（读 CHROME_AGENT_LOG_LEVEL）
│   │   │   └── cli.py            # chrome-agent CLI
│   │   └── tests/                # 单元 + integration（默认跳过）
│   └── research/                 # chrome-research
│       ├── pyproject.toml
│       ├── src/chrome_research/  # types / prompts / plan / execute / synthesize / agent / cli
│       └── tests/
├── examples/
│   ├── quickstart.py
│   └── research_demo.py
└── .github/workflows/
    ├── tests.yml
    └── publish.yml
```

## 4. 包公共 API

### chrome_agent_core 顶层导入

```python
from chrome_agent_core import (
    AgentSession, ToolRegistry,
    # LLM 抽象与具体 Provider
    BaseLLM, OpenAICompatLLM,
    BailianLLM, OpenAILLM, AnthropicLLM,
    DeepSeekLLM, MoonshotLLM, ZhipuLLM,
    OpenRouterLLM, GroqLLM, OllamaLLM,
    create_llm, list_providers,
    BaseTool, ToolDefinition, ToolResult, ToolCall,
    Message, Session, ChatSessionStore,
    build_system_prompt, compact_if_needed, create_session,
    get_config, validate_config,
    setup_logging, get_logger,
    ChromeAgentError, ConfigError,
    CDPError, CDPConnectionError, BrowserLaunchError,
    NavigationError, ElementNotFoundError,
    SessionError, LLMError, LLMTimeoutError,
    ToolError, ToolNotFoundError, ToolTimeoutError,
)

from chrome_agent_core.browser import ensure_chrome, check_chrome_installed
from chrome_agent_core.tools import register_all_tools, register_browser_tools, register_session_tools
from chrome_agent_core.cdp import cdp_navigate, click_element, input_text, get_elements
from chrome_agent_core.session import SessionManager, save_session, load_session
```

#### LLM 工厂与 Provider 矩阵

| Provider 名             | 类             | 默认模型                       | 默认 base_url                                       | API Key 环境变量      |
| :---------------------- | :------------- | :----------------------------- | :-------------------------------------------------- | :-------------------- |
| `bailian` / `dashscope` | `BailianLLM`   | `qwen-long`                    | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `DASHSCOPE_API_KEY`   |
| `openai`                | `OpenAILLM`    | `gpt-4o-mini`                  | `https://api.openai.com/v1`                         | `OPENAI_API_KEY`      |
| `anthropic` / `claude`  | `AnthropicLLM` | `claude-3-5-haiku-20241022`    | `https://api.anthropic.com/v1`                      | `ANTHROPIC_API_KEY`   |
| `deepseek`              | `DeepSeekLLM`  | `deepseek-chat`                | `https://api.deepseek.com/v1`                       | `DEEPSEEK_API_KEY`    |
| `moonshot` / `kimi`     | `MoonshotLLM`  | `moonshot-v1-8k`               | `https://api.moonshot.cn/v1`                        | `MOONSHOT_API_KEY`    |
| `zhipu` / `glm`         | `ZhipuLLM`     | `glm-4-flash`                  | `https://open.bigmodel.cn/api/paas/v4`              | `ZHIPU_API_KEY`       |
| `openrouter`            | `OpenRouterLLM`| `openai/gpt-4o-mini`           | `https://openrouter.ai/api/v1`                      | `OPENROUTER_API_KEY`  |
| `groq`                  | `GroqLLM`      | `llama-3.1-8b-instant`         | `https://api.groq.com/openai/v1`                    | `GROQ_API_KEY`        |
| `ollama`                | `OllamaLLM`    | `llama3.1`                     | `http://localhost:11434/v1`                         | （本地无需 key）      |

```python
from chrome_agent_core import create_llm

llm = create_llm(provider="anthropic", model="claude-3-5-sonnet-20241022")  # 显式指定
llm = create_llm()  # 不传 provider 时回退到 Config.provider（默认 bailian）
```

`create_llm` 支持以下参数：`provider`（缺省读 `Config.provider`）/ `api_key`（缺省走 Provider env_var → `CHROME_AGENT_API_KEY` → toml）/ `model`（缺省用 `PROVIDER_DEFAULT_MODELS[provider]`）/ `base_url`（缺省用各 Provider 默认）。

抽象层契约：所有 Provider 实现 `BaseLLM`：

```python
class BaseLLM(ABC):
    provider_name: str
    model: str
    async def chat(self, messages, tools=None, temperature=0.7, **kwargs) -> dict[str, Any]: ...
    def stream_chat(self, messages, tools=None, temperature=0.7, **kwargs) -> AsyncIterator[str]: ...
```

`chat` 返回 `{"content": str, "tool_calls"?: [{"id", "name", "arguments"}, ...]}`。

### chrome_research 顶层导入

```python
from chrome_research import (
    ResearchAgent,
    create_research_agent,
    SubTask, ResearchPlan, TaskStatus,
)
```

## 5. CLI 入口

| 命令 | 入口 | 用途 |
| :--- | :--- | :--- |
| `chrome-agent` | `chrome_agent_core.cli:main` | 单工具调用 / `--list-tools` / `--interactive` / `--chat` |
| `chrome-research` | `chrome_research.cli:main` | 深度调研：`run "<目标>"` |

均通过 `[project.scripts]` 在各自 `pyproject.toml` 中声明。

## 6. 开发流程

```bash
# 安装
uv sync --all-packages --group dev

# 运行测试（单元）
uv run pytest -v

# 集成测试（需要真实 Chrome + API Key）
uv run pytest -m integration -v

# Lint
uv run ruff check packages/

# Type check
uv run mypy packages/core/src packages/research/src

# CLI 冒烟
uv run chrome-agent --help
uv run chrome-research --help
```

## 7. 编码规范

- **公共 API** 必须在各自包 `__init__.py` 显式 `__all__` 导出；新增模块需同步更新 `__init__.py` 与本文件第 4 节。
- **导入路径** 全部使用 **包内相对导入**（`from ..agent.tool import ...`），不允许 `sys.path.insert` 等副作用。
- **工具注册** 通过 `chrome_agent_core.tools.register_all_tools()` 幂等触发，不允许在模块顶层执行注册副作用。
- **配置** 优先从 `Config` dataclass 读取（`get_config()`）；测试中要 patch 行为请用 `reset_config()`。
- **错误** 统一抛出 `errors.py` 中定义的层级异常，不要直接抛 `Exception`。
- **日志** 全部走 `setup_logging()` / `get_logger(__name__)`；环境变量 `CHROME_AGENT_LOG_LEVEL` 可覆盖等级。
- **类型注解** 新代码必须有完整类型注解；Python 3.10+，可使用 `X | None` 与 `from __future__ import annotations`。
- **行宽** 100；ruff 规则 `["E", "F", "W", "I", "B", "UP"]`，忽略 `E501`。
- **测试**：
  - 默认 `addopts = "-m 'not integration' -ra"`，集成测试需 `pytest -m integration` 显式触发。
  - 单元测试不允许真实联网或启动 Chrome；LLM 必须 mock。
  - 工具注册在测试间须幂等：用 `conftest.py` 的 `clean_registry` fixture 清理 `ToolRegistry`。
  - 测试模块名跨包不要重名（已用 `test_research_imports.py` 区分），且 `tests/` 不放 `__init__.py`。

## 8. 配置文件

按以下顺序加载（后者覆盖前者）：

1. 内置默认值（`config.py` 中的 `DEFAULT_*` / `DEFAULT_PROVIDER` / `PROVIDER_DEFAULT_MODELS`）
2. `~/.chrome-agent/config.toml`
3. `./.chrome-agent.toml`（仓库当前工作目录）
4. 环境变量：
   - `CHROME_AGENT_PROVIDER`：Provider 名（不区分大小写，支持别名 `dashscope`/`claude`/`kimi`/`glm`）
   - `CHROME_AGENT_MODEL`：模型名（兼容旧的 `BAILIAN_MODEL`）
   - `CHROME_AGENT_BASE_URL`：自定义 base_url
   - `CHROME_AGENT_API_KEY`：跨 Provider 的统一 API Key 兜底
   - 各 Provider 专属 env vars（优先级最高）：`DASHSCOPE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` / `ZHIPU_API_KEY` / `OPENROUTER_API_KEY` / `GROQ_API_KEY`
   - `CHROME_AGENT_LOG_LEVEL`：日志等级

API Key 解析优先级：**Provider 专属 env_var > `CHROME_AGENT_API_KEY` > toml `api_key`**。

最小示例：

```toml
# .chrome-agent.toml
provider = "openai"          # 可省，默认 bailian
model    = "gpt-4o-mini"     # 可省，按 provider 取默认
base_url = ""                # 可省，按 provider 取默认
api_key  = "sk-xxxx"
log_level = "INFO"
```

## 9. 发布

`v*.*.*` tag 推送会触发 `.github/workflows/publish.yml`：

1. 矩阵构建 `chrome-agent-core` 与 `chrome-research`（`uv build`）
2. 通过 PyPI Trusted Publishing（OIDC）发布

需在 PyPI 项目侧绑定 GitHub Actions Trusted Publisher，否则改用 `PYPI_API_TOKEN` 模式（见 publish.yml 注释）。

## 10. 给 AI 协作者的注意事项

- 修改公共 API 时，同步更新：`__init__.py` `__all__`、CLI、本 `CLAUDE.md`、`README.md`、相关测试。
- 不要重新引入根目录的旧 `agent/`、`core/`、`utils/`、`tests/`、`chrome_agent.py`、`cli_old.py`、`requirements.txt` —— 这些已在重构方案 C 中删除，所有代码必须放进 `packages/{core,research}/src/`。
- 子包之间只允许 `chrome_research` 依赖 `chrome_agent_core`，禁止反向依赖。
- 任何新工具：实现 `BaseTool` 子类或用 `@register_tool` 装饰器，并加入 `tools/__init__.py` 的 `register_all_tools` 流程。
- 测试要写：单元测试 mock 一切外部 IO；只有真实端到端验证才打 `@pytest.mark.integration`。
