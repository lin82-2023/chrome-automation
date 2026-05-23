"""
chrome-agent-core 快速上手示例

演示：
1. 检查/启动 Chrome（远程调试模式）
2. 注册内置工具到 ToolRegistry
3. 通过 create_llm 工厂选择任意 Provider，让 LLM 通过 function-calling 驱动浏览器

依赖：
    uv sync --all-packages --group dev

支持的 Provider 与对应环境变量：
    bailian   → DASHSCOPE_API_KEY    （阿里云百炼，默认）
    openai    → OPENAI_API_KEY
    anthropic → ANTHROPIC_API_KEY
    deepseek  → DEEPSEEK_API_KEY
    moonshot  → MOONSHOT_API_KEY     （Kimi）
    zhipu     → ZHIPU_API_KEY        （GLM）
    openrouter→ OPENROUTER_API_KEY
    groq      → GROQ_API_KEY
    ollama    → 本地无需 key

运行（示例）：
    DASHSCOPE_API_KEY=sk-xxx uv run python examples/quickstart.py
    CHROME_AGENT_PROVIDER=openai OPENAI_API_KEY=sk-xxx uv run python examples/quickstart.py
"""
from __future__ import annotations

import asyncio
import sys

from chrome_agent_core import (
    AgentSession,
    ToolRegistry,
    create_llm,
    get_config,
    setup_logging,
    validate_config,
)
from chrome_agent_core.browser import ensure_chrome
from chrome_agent_core.tools import register_all_tools


async def main() -> None:
    setup_logging(level="INFO")

    valid, msg = validate_config()
    if not valid:
        print(f"配置错误: {msg}")
        print("请先设置对应 Provider 的 API Key 环境变量（或 CHROME_AGENT_API_KEY）")
        sys.exit(2)

    # 1. 确认 Chrome 已就绪（必要时提示用户用 --remote-debugging-port=9222 启动）
    ensure_chrome()

    # 2. 注册内置工具（浏览器 + Session）
    register_all_tools()
    tools = ToolRegistry.list_tools()
    print(f"已注册工具数量: {len(tools)}")

    # 3. 通过工厂创建 LLM；provider 由 CHROME_AGENT_PROVIDER 控制（默认 bailian）
    config = get_config()
    print(f"使用 Provider: {config.provider} | 模型: {config.model}")
    llm = create_llm(
        provider=config.provider,
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url or None,
    )
    agent = AgentSession(llm=llm, tools=tools)

    # 4. 用自然语言驱动多步任务
    user_goal = (
        "打开 https://www.bing.com，搜索 'chrome devtools protocol'，"
        "返回首条结果的标题与链接。"
    )
    print(f"\n[Goal] {user_goal}\n")
    result = await agent.run(user_goal)
    print("\n=== Agent Result ===\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
