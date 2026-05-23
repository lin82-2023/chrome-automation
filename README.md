# Chrome Agent Workspace

基于 Chrome DevTools Protocol (CDP) 的浏览器自动化 + AI Agent 框架。
仓库为 **uv workspace monorepo**，包含两个可独立发布的包：

| 包名 | 作用 | CLI |
| :--- | :--- | :--- |
| [`chrome-agent-core`](packages/core) | CDP 自动化引擎 + LLM/Tool/AgentSession 框架 | `chrome-agent` |
| [`chrome-research`](packages/research) | 基于 core 的多步深度调研 Agent（plan → execute → synthesize） | `chrome-research` |

## 目录结构

```
chrome-automation/
├── pyproject.toml                # workspace 根（uv workspace + ruff/mypy/pytest）
├── packages/
│   ├── core/                     # chrome-agent-core
│   │   ├── pyproject.toml
│   │   ├── src/chrome_agent_core/
│   │   │   ├── cdp/              # CDP 引擎（连接 / 导航 / 元素 / 输入 / Tab / 窗口 / 事件）
│   │   │   ├── browser/          # Chrome 启动与生命周期
│   │   │   ├── stealth/          # 反指纹 / 反检测
│   │   │   ├── session/          # 登录 / Cookie 持久化
│   │   │   ├── llm/              # LLM Provider（百炼/OpenAI/Anthropic/DeepSeek/Kimi/智谱/OpenRouter/Groq/Ollama）
│   │   │   ├── tools/            # 内置工具（浏览器 + Session）
│   │   │   ├── agent/            # AgentSession / ToolRegistry / Message / Compaction
│   │   │   ├── config.py         # dataclass 配置 + TOML 加载
│   │   │   ├── errors.py         # ChromeAgentError 体系
│   │   │   ├── logging.py        # setup_logging / get_logger
│   │   │   └── cli.py            # chrome-agent 入口
│   │   └── tests/
│   └── research/                 # chrome-research
│       ├── pyproject.toml
│       ├── src/chrome_research/
│       │   ├── types.py          # SubTask / ResearchPlan / TaskStatus
│       │   ├── prompts.py        # 规划 / 执行 / 摘要提示词
│       │   ├── plan.py           # generate_plan
│       │   ├── execute.py        # execute_task / fallback
│       │   ├── synthesize.py     # 报告生成
│       │   ├── agent.py          # ResearchAgent
│       │   └── cli.py            # chrome-research 入口
│       └── tests/
├── examples/
│   ├── quickstart.py             # chrome-agent-core 示例
│   └── research_demo.py          # chrome-research 示例
└── .github/workflows/
    ├── tests.yml                 # CI（matrix py3.10/3.11/3.12）
    └── publish.yml               # PyPI 发布（按 v*.*.* tag 触发）
```

## 快速开始

### 1. 启动 Chrome 远程调试

```bash
# macOS
open -a "Google Chrome" --args --remote-debugging-port=9222 --remote-allow-origins=*

# Linux
google-chrome --remote-debugging-port=9222 --remote-allow-origins=*

# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" \
    --remote-debugging-port=9222 --remote-allow-origins=*
```

### 2. 安装（uv workspace）

```bash
# 安装 uv：https://docs.astral.sh/uv/
uv sync --all-packages --group dev
```

`uv sync` 会以 editable 方式同时安装 `chrome-agent-core` 与 `chrome-research`。

### 3. 配置 API Key

`chrome-agent-core` 内置多 Provider 支持。默认 Provider 为 `bailian`，可通过环境变量 `CHROME_AGENT_PROVIDER` 切换；
每个 Provider 默认从对应专属环境变量读取 API Key（也可统一用 `CHROME_AGENT_API_KEY` 兜底）。

> **注意**：API Key 必须为纯 ASCII 字符串。复制粘贴时如果混入了中文引号 / 全角空格 / BOM 等，运行会立即抛 `LLMError: API Key 含非 ASCII 字符...` 并提示位置，请重新 `export`。

| Provider           | 默认模型                       | 默认 base_url                              | API Key 环境变量          |
| :----------------- | :----------------------------- | :----------------------------------------- | :------------------------ |
| `bailian`（默认）  | `qwen-long`                    | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `DASHSCOPE_API_KEY`       |
| `openai`           | `gpt-4o-mini`                  | `https://api.openai.com/v1`                | `OPENAI_API_KEY`          |
| `anthropic`        | `claude-3-5-haiku-20241022`    | `https://api.anthropic.com/v1`             | `ANTHROPIC_API_KEY`       |
| `deepseek`         | `deepseek-chat`                | `https://api.deepseek.com/v1`              | `DEEPSEEK_API_KEY`        |
| `moonshot` (`kimi`)| `moonshot-v1-8k`               | `https://api.moonshot.cn/v1`               | `MOONSHOT_API_KEY`        |
| `zhipu` (`glm`)    | `glm-4-flash`                  | `https://open.bigmodel.cn/api/paas/v4`     | `ZHIPU_API_KEY`           |
| `openrouter`       | `openai/gpt-4o-mini`           | `https://openrouter.ai/api/v1`             | `OPENROUTER_API_KEY`      |
| `groq`             | `llama-3.1-8b-instant`         | `https://api.groq.com/openai/v1`           | `GROQ_API_KEY`            |
| `ollama`           | `llama3.1`                     | `http://localhost:11434/v1`                | （本地无需 key）          |

```bash
# 示例 1：默认百炼
export DASHSCOPE_API_KEY="sk-xxxxxxxx"

# 示例 2：切换到 OpenAI
export CHROME_AGENT_PROVIDER=openai
export OPENAI_API_KEY="sk-xxxxxxxx"

# 示例 3：切换到 Anthropic
export CHROME_AGENT_PROVIDER=anthropic
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxx"
export CHROME_AGENT_MODEL="claude-3-5-sonnet-20241022"   # 可选

# 示例 4：自部署 / 代理
export CHROME_AGENT_BASE_URL="https://your-proxy/v1"

# 也可写入 .chrome-agent.toml / ~/.chrome-agent/config.toml
```

### 4. 命令行用法

```bash
# 单工具调用
uv run chrome-agent navigate url=https://www.baidu.com
uv run chrome-agent click text=百度一下
uv run chrome-agent --list-tools

# 自然语言对话（function calling）
uv run chrome-agent --chat "打开百度并搜索 LLM"

# 切换 Provider（CLI 标志覆盖环境变量）
uv run chrome-agent --chat "总结一下 OpenAI 官网的产品" --provider openai --model gpt-4o-mini
uv run chrome-research "对比开源 LLM Agent 框架" --provider anthropic --model claude-3-5-sonnet-20241022

# 深度调研
uv run chrome-research "调研 2026 年开源 AI Agent 框架"
```

### 5. Python API 用法

```python
import asyncio
from chrome_agent_core import AgentSession, ToolRegistry, create_llm, get_config
from chrome_agent_core.tools import register_all_tools
from chrome_agent_core.browser import ensure_chrome

async def main():
    ensure_chrome()
    register_all_tools()
    cfg = get_config()
    # 用工厂创建 LLM，provider 由 CHROME_AGENT_PROVIDER 控制（默认 bailian）
    llm = create_llm(
        provider=cfg.provider,
        api_key=cfg.api_key,
        model=cfg.model,
        base_url=cfg.base_url or None,
    )
    agent = AgentSession(llm=llm, tools=ToolRegistry.list_tools())
    print(await agent.run("打开 bing 搜索 chrome devtools protocol"))

asyncio.run(main())
```

也可直接构造任意 Provider 实例：

```python
from chrome_agent_core import AnthropicLLM, OpenAILLM

llm = OpenAILLM(api_key="sk-xxx", model="gpt-4o-mini")
# 或
llm = AnthropicLLM(api_key="sk-ant-xxx", model="claude-3-5-sonnet-20241022")
```

完整示例见 [`examples/quickstart.py`](examples/quickstart.py) 与 [`examples/research_demo.py`](examples/research_demo.py)。

## 核心特性

- **CDP 原生** - 直连 Chrome DevTools Protocol，零浏览器驱动依赖
- **反检测** - Stealth 脚本注入（Canvas/WebGL/Fingerprint 等）
- **会话持久化** - Cookies + localStorage + sessionStorage 全量保存/恢复
- **AgentSession 编排** - LLM ↔ 工具循环、消息压缩、流式输出
- **多 LLM Provider** - 内置 9 种 Provider（百炼/OpenAI/Anthropic/DeepSeek/Kimi/智谱/OpenRouter/Groq/Ollama），支持 `create_llm` 工厂 + 别名（`dashscope`/`claude`/`kimi`/`glm`）+ 自定义 base_url
- **工具协议** - `BaseTool` / `ToolRegistry` 装饰器风格注册
- **配置统一** - dataclass + TOML（`.chrome-agent.toml` / `~/.chrome-agent/config.toml`）
- **错误体系** - 分层异常（`CDPError` / `LLMError` / `ToolError` 等）
- **Research 模式** - plan → 并行 execute → fallback → 摘要合成

## 登录墙处理（chrome-research）

调研任务遇到需要登录的站点（知乎/微博/小红书/Twitter/LinkedIn 等）时，系统会自动检测登录墙并按下面的策略处理。**默认模式：`auto` —— 暂停脚本，等你在受控 Chrome 里登录，登录态自动落盘到 `~/.chrome-automation/sessions/<domain>/`，下次运行同域名直接复用。**

### 三种模式（环境变量 `CHROME_RESEARCH_LOGIN_MODE`）

| 模式 | 行为 | 适用场景 |
|---|---|---|
| `auto`（**默认**）| 检测到登录墙 → 终端打印提示 → 阻塞等你在浏览器登录 → 自动检测登录完成 → save_session → reload 抓内容；**等待超时则放弃当前任务，走 fallback** | 本人在场操作 |
| `ask`            | 弹出终端三选一：`[L]` 登录 / `[s]` 跳过本任务 / `[a]` 永久跳过该域名；30s 不响应按 skip | 想细粒度控制每次 |
| `skip`           | 直接判定为不可达，立即走 fallback 不等待登录                                     | CI / 无人值守 |

### 相关环境变量

```bash
CHROME_RESEARCH_LOGIN_MODE=auto       # auto | ask | skip，默认 auto
CHROME_RESEARCH_LOGIN_TIMEOUT=300     # auto 模式下等待用户登录的最长秒数（默认 300s = 5 分钟）
CHROME_RESEARCH_ASK_TIMEOUT=30        # ask 模式下三选一提示的响应超时（默认 30s）
CHROME_RESEARCH_INTERACTIVE_LOGIN=0   # 等价于 LOGIN_MODE=skip（向后兼容旧用法）
```

### 完整生命周期

```
任务开始
  ├─ 自动尝试 load_session(domain) → 命中即跳过登录墙
  └─ navigate URL
       ├─ _probe_login_wall 未命中 → 直接抓内容
       └─ 命中（URL/标题含 signin/login，或正文含登录关键词）
            ├─ auto  → 提示「请在浏览器登录」→ wait_for_manual_login
            │           ├─ 登录成功 → save_session → reload → 继续
            │           └─ 超时 / 失败 → 抛 LOGIN_WALL → fallback
            ├─ ask   → 终端三选一（L/s/a）
            └─ skip  → 立即抛 LOGIN_WALL → fallback
```

非 TTY 环境（CI/nohup/管道）下 `ask` 自动退化为 `skip`，避免脚本永远卡住。

### 落盘的 session 文件

```
~/.chrome-automation/sessions/<domain>/
├── cookies.json          # CDP Network.getAllCookies 全量
├── localStorage.json     # 当前域 localStorage
├── sessionStorage.json   # 当前域 sessionStorage
└── metadata.json         # 保存时间戳，30 天自动判定过期
```

## 开发

```bash
# 跑单元测试（默认跳过 integration）
uv run pytest -v

# 跑集成测试（需要真实 Chrome + API Key）
uv run pytest -m integration -v

# Lint
uv run ruff check packages/

# Type check
uv run mypy packages/core/src packages/research/src
```

## 许可证

MIT
