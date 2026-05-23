#!/usr/bin/env python3
"""chrome-research CLI

用法：
    chrome-research "AI Agent 框架对比" --num 5
    chrome-research "Cursor vs Claude Code" -o report.md
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from chrome_agent_core.browser import ensure_chrome
from chrome_agent_core.logging import setup_logging

from .agent import create_research_agent


def _setup_logging(verbose: bool) -> None:
    setup_logging(level="DEBUG" if verbose else "INFO")


async def _run(
    goal: str,
    num: int,
    output: Path | None,
    api_key: str | None,
    provider: str | None,
    model: str | None,
    base_url: str | None,
) -> None:
    # 确保 Chrome 远程调试端口就绪（未就绪时会自动启动一个干净实例）
    if not ensure_chrome():
        print("无法启动 Chrome 远程调试，请手动确保 9222 端口可用")
        sys.exit(3)

    agent = await create_research_agent(
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
    )
    report = await agent.run(goal, num_websites=num)

    if output:
        output.write_text(report, encoding="utf-8")
        print(f"\n📄 报告已保存到: {output}")
    else:
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chrome-research",
        description="多网站深度调研 Agent（基于 chrome-agent-core）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  chrome-research "AI Agent 框架对比"
  chrome-research "RAG 最新研究" --num 6 -o report.md
  chrome-research "对比开源 LLM" --provider openai --model gpt-4o-mini
  chrome-research "AGI 评测" --provider anthropic --model claude-3-5-sonnet-20241022
""",
    )
    parser.add_argument("goal", help="研究目标")
    parser.add_argument("--num", "-n", type=int, default=5, help="调研网站数量（默认 5）")
    parser.add_argument("--output", "-o", type=Path, help="输出报告文件路径，默认打印到 stdout")
    parser.add_argument(
        "--provider",
        help="LLM Provider（bailian/openai/anthropic/deepseek/moonshot/zhipu/openrouter/groq/ollama）",
    )
    parser.add_argument("--model", help="模型名（默认使用所选 Provider 的默认模型）")
    parser.add_argument("--base-url", help="自定义 API base_url（用于代理或自部署）")
    parser.add_argument("--api-key", help="API Key（默认从对应 Provider 环境变量读取）")
    parser.add_argument("--verbose", "-v", action="store_true", help="开启 DEBUG 日志")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    try:
        asyncio.run(
            _run(
                args.goal,
                args.num,
                args.output,
                args.api_key,
                args.provider,
                args.model,
                args.base_url,
            )
        )
    except KeyboardInterrupt:
        print("\n用户取消")
        sys.exit(130)


if __name__ == "__main__":
    main()
