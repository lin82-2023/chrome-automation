#!/usr/bin/env python3
"""chrome-agent CLI

用法：
    chrome-agent navigate url=https://www.baidu.com
    chrome-agent click text=百度一下
    chrome-agent --list-tools
    chrome-agent --interactive
    chrome-agent --chat "打开百度并搜索 LLM"   # 自然语言模式（function calling）
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from . import AgentSession, ChatSessionStore, ToolRegistry, create_llm
from .browser import ensure_chrome
from .config import get_config, validate_config
from .logging import setup_logging
from .tools import register_all_tools

# ── 渲染辅助 ──────────────────────────────────────────────────────────────


def render_tool_call(name: str, args: dict) -> str:
    return f"[tool] {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})"


def render_result(result: dict) -> str:
    if result.get("success"):
        return f"[ok] {result.get('content', '')}"
    return f"[error] {result.get('content', '')}"


def render_tools_list(tools: list) -> str:
    lines = ["可用工具:"]
    for t in tools:
        lines.append(f"  {t.name:<20} - {t.description}")
    return "\n".join(lines)


def print_interactive_help() -> None:
    print(
        """
Chrome Agent 交互模式
======================
命令:
  /tools                列出所有工具
  /help                 显示帮助
  /exit                 退出
  <tool_name> k=v,...   执行工具

示例:
  navigate url=https://www.baidu.com
  click text=百度一下
  get_page_info
"""
    )


# ── 单工具调用模式 ────────────────────────────────────────────────────────


def parse_args_string(args_str: str | None) -> dict:
    args: dict = {}
    if not args_str:
        return args
    for part in args_str.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key, value = key.strip(), value.strip()
        low = value.lower()
        if low == "true":
            value = True
        elif low == "false":
            value = False
        elif low == "none":
            value = None
        else:
            try:
                if value.lstrip("-").isdigit():
                    value = int(value)
                elif value.replace(".", "", 1).lstrip("-").replace(".", "", 1).isdigit():
                    value = float(value)
            except Exception:
                pass
        args[key] = value
    return args


async def execute_tool(tool_name: str, args: dict) -> dict:
    tool = ToolRegistry.get(tool_name)
    if not tool:
        return {"success": False, "content": f"未知工具: {tool_name}"}
    if not tool.execute:
        return {"success": False, "content": f"工具 {tool_name} 未绑定执行函数"}
    try:
        result = await tool.execute(**args)
        return result.to_dict()
    except Exception as e:
        return {"success": False, "content": f"执行错误: {e}"}


async def run_single(tool_name: str, args: dict) -> None:
    print(render_tool_call(tool_name, args))
    result = await execute_tool(tool_name, args)
    print(render_result(result))


async def interactive() -> None:
    register_all_tools()
    print("Chrome Agent 交互模式（输入 /help 查看帮助）")
    while True:
        try:
            line = input("> ").strip()
            if not line:
                continue
            if line in ("/exit", "/quit", "quit", "exit"):
                print("再见!")
                break
            if line == "/help":
                print_interactive_help()
                continue
            if line == "/tools":
                print(render_tools_list(ToolRegistry.list_tools()))
                continue
            if line.startswith("/"):
                line = line[1:]
            parts = line.split(None, 1)
            tool_name = parts[0]
            args = parse_args_string(parts[1] if len(parts) > 1 else "")
            result = await execute_tool(tool_name, args)
            print(render_result(result))
        except KeyboardInterrupt:
            print("\n再见!")
            break
        except Exception as e:
            print(f"错误: {e}")


# ── 自然语言对话模式（function calling） ──────────────────────────────────


async def chat_mode(
    user_input: str,
    session_id: str | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> None:
    valid, msg = validate_config()
    if not valid and not (api_key or provider):
        print(f"配置错误: {msg}")
        print("请设置对应 Provider 的 API Key 环境变量，或通过 --api-key/--provider 指定")
        sys.exit(2)

    # 确保 Chrome 远程调试端口就绪（未就绪时会自动启动一个干净实例）
    if not ensure_chrome():
        print("无法启动 Chrome 远程调试，请手动确保 9222 端口可用")
        sys.exit(3)

    register_all_tools()
    tools = ToolRegistry.list_tools()

    config = get_config()
    llm = create_llm(
        provider=provider or config.provider,
        api_key=api_key or config.api_key,
        model=model or config.model,
        base_url=base_url or (config.base_url or None),
    )
    agent = AgentSession(llm=llm, tools=tools, session_id=session_id)

    print(f"[Agent] {user_input}")
    async for chunk in agent.run_stream(user_input):
        print(chunk, end="", flush=True)
    print()

    ChatSessionStore().save_session(agent.session)


# ── 入口 ──────────────────────────────────────────────────────────────────


def _setup_logging(verbose: bool) -> None:
    setup_logging(level="DEBUG" if verbose else "INFO")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chrome-agent",
        description="Chrome Agent SDK CLI（基于 CDP 的浏览器自动化）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  chrome-agent navigate url=https://www.baidu.com
  chrome-agent click text=百度一下
  chrome-agent --list-tools
  chrome-agent --interactive
  chrome-agent --chat "打开百度并搜索 LLM"
""",
    )
    parser.add_argument("--list-tools", "-l", action="store_true", help="列出所有可用工具")
    parser.add_argument("--interactive", "-i", action="store_true", help="进入工具调用交互模式")
    parser.add_argument("--chat", "-c", metavar="GOAL", help="自然语言对话模式（function calling）")
    parser.add_argument("--session-id", help="复用已有 session id")
    parser.add_argument(
        "--provider",
        help="LLM Provider（bailian/openai/anthropic/deepseek/moonshot/zhipu/openrouter/groq/ollama）",
    )
    parser.add_argument("--model", help="模型名（默认使用所选 Provider 的默认模型）")
    parser.add_argument("--base-url", dest="base_url", help="自定义 API base_url（用于代理或自部署）")
    parser.add_argument("--api-key", dest="api_key", help="API Key（默认从对应 Provider 环境变量读取）")
    parser.add_argument("--verbose", "-v", action="store_true", help="开启 DEBUG 日志")
    parser.add_argument("tool_name", nargs="?", help="单次调用的工具名")
    parser.add_argument("args", nargs="?", help="工具参数：key=value,key2=value2")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.list_tools:
        register_all_tools()
        print(render_tools_list(ToolRegistry.list_tools()))
        return
    if args.chat:
        asyncio.run(
            chat_mode(
                args.chat,
                session_id=args.session_id,
                provider=args.provider,
                model=args.model,
                base_url=args.base_url,
                api_key=args.api_key,
            )
        )
        return
    if args.interactive or (not args.tool_name and not args.args):
        asyncio.run(interactive())
        return
    if not args.tool_name:
        parser.print_help()
        return

    register_all_tools()
    asyncio.run(run_single(args.tool_name, parse_args_string(args.args)))


if __name__ == "__main__":
    main()
