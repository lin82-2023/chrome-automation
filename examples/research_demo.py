"""
chrome-research 深度调研示例

演示：
1. 给定调研目标
2. ResearchAgent 自动 plan → execute → synthesize
3. 输出 Markdown 调研报告

依赖：
    uv sync --all-packages --group dev
环境变量：
    DASHSCOPE_API_KEY=sk-xxx
"""
from __future__ import annotations

import asyncio
import os

from chrome_agent_core import setup_logging
from chrome_research import create_research_agent


async def main() -> None:
    setup_logging(level="INFO")

    if not os.getenv("DASHSCOPE_API_KEY"):
        raise SystemExit("请先设置环境变量 DASHSCOPE_API_KEY")

    agent = await create_research_agent()

    goal = "调研 2026 年最值得关注的 5 个开源 AI Agent 框架，给出对比与推荐"
    report = await agent.run(goal, num_websites=5)

    print("\n=== Research Report ===\n")
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
