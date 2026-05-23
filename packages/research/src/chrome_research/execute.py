"""单任务执行：在浏览器中按计划深度调研"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .prompts import execute_prompt, extract_prompt
from .types import SubTask, TaskStatus

if TYPE_CHECKING:
    from chrome_agent_core import BaseLLM

logger = logging.getLogger(__name__)

LLM_EXEC_TIMEOUT = 90.0
LLM_EXTRACT_TIMEOUT = 60.0
TOOL_NAVIGATE_TIMEOUT = 20.0
TOOL_DEFAULT_TIMEOUT = 15.0

# 登录墙处理模式：
#   auto - 检测到登录墙后自动暂停，等用户在浏览器里完成登录（超时则走 fallback）【默认】
#   ask  - 弹出终端 prompt 让用户三选一（[L]ogin / [s]kip / [a]bort）
#   skip - 直接跳过，走 fallback（不等待登录）
_LOGIN_MODE = os.environ.get("CHROME_RESEARCH_LOGIN_MODE", "auto").strip().lower()
# 向后兼容：CHROME_RESEARCH_INTERACTIVE_LOGIN=0 等价于 skip 模式
if os.environ.get("CHROME_RESEARCH_INTERACTIVE_LOGIN", "1").strip().lower() in (
    "0", "false", "no", "off"
):
    _LOGIN_MODE = "skip"

_LOGIN_WAIT_TIMEOUT = int(os.environ.get("CHROME_RESEARCH_LOGIN_TIMEOUT", "300"))
_ASK_TIMEOUT = int(os.environ.get("CHROME_RESEARCH_ASK_TIMEOUT", "30"))

# 本次进程内永久跳过的域名集合（用户选 [a] 时写入）
_PERMANENTLY_SKIPPED: set[str] = set()

# 登录墙特征：URL 片段、页面标题/正文关键词
_LOGIN_WALL_URL_PATTERNS = (
    "/signin", "/login", "/passport", "/auth/", "/sso/", "/account/login",
    "accounts.", "passport.", "login.",
)
_LOGIN_WALL_TEXT_PATTERNS = (
    "请登录", "立即登录", "登录后查看", "登录后继续", "未登录",
    "sign in to", "log in to", "please sign in", "please log in",
)


def _detect_login_wall_text(page_info: str) -> str:
    """根据 get_page_info 返回内容检测登录墙；命中返回原因字符串，否则空串"""
    if not page_info:
        return ""
    low = page_info.lower()
    for p in _LOGIN_WALL_URL_PATTERNS:
        if p in low:
            return f"URL 命中登录墙特征 '{p}'"
    for p in _LOGIN_WALL_TEXT_PATTERNS:
        if p.lower() in low:
            return f"页面文本命中登录墙特征 '{p}'"
    return ""


async def _probe_login_wall(tools: dict) -> str:
    """主动调用 get_page_info 探测当前页是否为登录墙；返回原因字符串或空串"""
    info_tool = tools.get("get_page_info")
    if not info_tool:
        return ""
    try:
        result = await asyncio.wait_for(info_tool.execute(), timeout=5.0)
    except Exception:
        return ""
    return _detect_login_wall_text(getattr(result, "content", "") or "")


def _domain_of(url: str) -> str:
    """从 URL 提取主域，例如 https://www.zhihu.com/xxx → zhihu.com"""
    try:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return ""
        # 去掉 www./m. 前缀，保留主域两段
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:
        return ""


async def _try_load_existing_session(domain: str) -> bool:
    """如有本地保存的有效 session，则注入 cookies；返回是否复用成功"""
    if not domain:
        return False
    try:
        from chrome_agent_core.session import SessionManager, load_session
        sm = SessionManager(domain)
        if not sm.exists() or sm.is_expired(days=30):
            return False
        ok = await asyncio.to_thread(load_session, domain)
        if ok:
            logger.info("  🔓 已复用 %s 的本地登录态", domain)
        return bool(ok)
    except Exception as e:
        logger.debug("load_session(%s) 失败: %s", domain, e)
        return False


async def _interactive_login_and_resume(domain: str, target_url: str) -> bool:
    """阻塞等待用户在浏览器中完成登录，成功则保存 session 并 reload 原 URL"""
    try:
        from chrome_agent_core.cdp import cdp_navigate
        from chrome_agent_core.session import save_session, wait_for_manual_login
    except Exception as e:
        logger.warning("交互登录所需模块不可用: %s", e)
        return False

    logger.warning("=" * 60)
    logger.warning("🔐 检测到 %s 登录墙 — 请在浏览器中完成登录", domain or "目标站")
    logger.warning("    脚本将自动检测登录完成（最长等待 %ds）", _LOGIN_WAIT_TIMEOUT)
    logger.warning("=" * 60)

    try:
        ok = await asyncio.to_thread(
            wait_for_manual_login, target_url, _LOGIN_WAIT_TIMEOUT
        )
    except Exception as e:
        logger.warning("wait_for_manual_login 异常: %s", e)
        return False

    if not ok:
        logger.warning("  ⏱️  登录等待超时或失败")
        return False

    if domain:
        try:
            await asyncio.to_thread(save_session, domain)
            logger.info("  💾 已保存 %s 的登录状态到 ~/.chrome-automation/sessions/", domain)
        except Exception as e:
            logger.warning("save_session(%s) 失败: %s", domain, e)

    # 重新加载原 URL，让登录态在目标页生效
    try:
        await asyncio.to_thread(cdp_navigate, target_url, 2)
    except Exception as e:
        logger.warning("登录后 reload 失败: %s", e)
        return False

    return True


def _parse_json_lenient(content: str) -> dict:
    """容忍 markdown 包裹与首尾噪声的 JSON 解析"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    start, end = content.find("{"), content.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(content[start:end])
    raise ValueError(f"响应中未找到 JSON: {content[:200]}")


async def _llm_chat(llm: BaseLLM, messages: list[dict], timeout: float) -> dict:
    try:
        return await asyncio.wait_for(llm.chat(messages=messages, tools=[]), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise RuntimeError(f"LLM 调用超时（{timeout:.0f}s）") from e


async def _tool_execute(tool_def, timeout: float, **tool_args):
    try:
        return await asyncio.wait_for(tool_def.execute(**tool_args), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise RuntimeError(f"工具 {tool_def.name} 执行超时（{timeout:.0f}s）") from e


async def execute_task(
    llm: BaseLLM,
    tools: dict,
    task: SubTask,
) -> SubTask:
    """执行单个调研子任务（含重试）"""
    task.status = TaskStatus.RUNNING
    logger.info("📋 执行任务: %s", task.description)

    # 任务开始前尝试复用本地保存的登录态（仅注入 cookies，不导航）
    task_domain = _domain_of(task.url)
    if task_domain:
        await _try_load_existing_session(task_domain)

    for attempt in range(task.max_retries + 1):
        try:
            if attempt > 0:
                task.status = TaskStatus.RETRYING
                logger.info("  🔄 第 %d 次重试...", attempt)
                await asyncio.sleep(2)

            # 1. 让 LLM 生成执行计划
            exec_response = await _llm_chat(
                llm,
                [{"role": "user", "content": execute_prompt(task.website, task.url, task.description)}],
                LLM_EXEC_TIMEOUT,
            )
            content = exec_response.get("content", "{}")
            try:
                exec_data = _parse_json_lenient(content)
            except Exception as e:
                raise RuntimeError(f"JSON 解析失败: {e}")

            steps = exec_data.get("steps", [])
            if not steps:
                raise RuntimeError("执行计划为空")

            used_tools = {s.get("tool") for s in steps}
            missing = {"eval_js", "get_elements"} - used_tools
            if missing:
                raise RuntimeError(f"执行计划缺少关键工具 {missing}")

            # 2. 顺序执行步骤
            observations = []
            for step in steps:
                tool_name = step.get("tool")
                tool_args = step.get("args", {}) or {}
                tool_def = tools.get(tool_name)
                if not tool_def:
                    logger.warning("  ⚠️  工具不存在: %s", tool_name)
                    continue

                logger.info("  → %s(%s)", tool_name, tool_args)
                try:
                    t = TOOL_NAVIGATE_TIMEOUT if tool_name == "navigate" else TOOL_DEFAULT_TIMEOUT
                    result = await _tool_execute(tool_def, t, **tool_args)
                    obs = f"{tool_name}: {'✅' if result.success else '❌'} {result.content[:100]}"
                    observations.append(obs)
                    logger.info("    %s", obs)
                    if not result.success and tool_name == "navigate":
                        raise RuntimeError(f"导航失败: {result.content}")
                    # navigate 成功后立即探测登录墙
                    if tool_name == "navigate" and result.success:
                        wall = await _probe_login_wall(tools)
                        if wall:
                            logger.warning("    🔒 登录墙检测命中: %s", wall)
                            navigated_url = tool_args.get("url") or task.url
                            handled = await _handle_login_wall(
                                domain=_domain_of(navigated_url) or task_domain,
                                target_url=navigated_url,
                            )
                            if handled:
                                observations.append(
                                    f"login: ✅ 用户已完成登录并自动 reload {navigated_url}"
                                )
                                # 登录后再次探测，仍是登录墙才放弃
                                wall2 = await _probe_login_wall(tools)
                                if wall2:
                                    raise RuntimeError(f"LOGIN_WALL: 登录后仍命中 {wall2}")
                            else:
                                raise RuntimeError(f"LOGIN_WALL: {wall}")
                    # get_page_info 直接返回页面信息，也顺手检测一次登录墙
                    if tool_name == "get_page_info" and result.success:
                        wall = _detect_login_wall_text(result.content or "")
                        if wall:
                            logger.warning("    🔒 登录墙检测命中: %s", wall)
                            handled = await _handle_login_wall(
                                domain=task_domain,
                                target_url=task.url,
                            )
                            if handled:
                                observations.append(
                                    f"login: ✅ 用户已完成登录并自动 reload {task.url}"
                                )
                                wall2 = await _probe_login_wall(tools)
                                if wall2:
                                    raise RuntimeError(f"LOGIN_WALL: 登录后仍命中 {wall2}")
                            else:
                                raise RuntimeError(f"LOGIN_WALL: {wall}")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    obs = f"{tool_name}: ❌ 执行错误 - {e}"
                    observations.append(obs)
                    logger.warning("    %s", obs)
                    # 登录墙触发整个任务失败，避免 LLM 继续在登录页死循环
                    if "LOGIN_WALL" in str(e):
                        raise

            # 3. 让 LLM 提取报告
            extract_response = await _llm_chat(
                llm,
                [{"role": "user", "content": extract_prompt(task.description, "\n".join(observations))}],
                LLM_EXTRACT_TIMEOUT,
            )
            task.result = extract_response.get("content", "")
            task.status = TaskStatus.COMPLETED
            logger.info("  ✅ 任务完成")
            return task

        except asyncio.CancelledError:
            logger.warning("  🚫 任务被取消: %s", task.description)
            task.status = TaskStatus.CANCELLED
            task.result = "任务被取消"
            raise
        except Exception as e:
            task.error = str(e)
            task.retry_count = attempt + 1
            logger.warning("  ❌ 失败: %s", e)
            # 登录墙是结构性失败，重试无意义，直接终止当前任务交给 fallback
            if "LOGIN_WALL" in str(e):
                task.status = TaskStatus.FAILED
                task.result = f"LOGIN_WALL: 该站需要登录才能访问，已跳过 ({e})"
                return task
            if attempt >= task.max_retries:
                task.status = TaskStatus.FAILED
                task.result = f"任务失败（重试{task.max_retries}次）: {e}"
                return task
    return task


async def _ask_user_login_choice(domain: str, target_url: str) -> str:
    """终端交互式询问用户：登录 / 跳过 / 永久跳过。返回 'login' | 'skip' | 'abort'

    在非交互（非 TTY）环境下退化为 'skip'，避免 CI/nohup 场景永远卡住。
    """
    if not sys.stdin.isatty():
        logger.info("  ⚠️  非交互终端，登录墙自动跳过（设 CHROME_RESEARCH_LOGIN_MODE=auto 可强制等待登录）")
        return "skip"

    prompt = (
        f"\n{'=' * 60}\n"
        f"🔐 检测到登录墙：{domain or target_url}\n"
        f"   目标 URL: {target_url}\n"
        f"   请选择如何处理：\n"
        f"     [L] 登录后继续（你在浏览器中登录，最长等待 {_LOGIN_WAIT_TIMEOUT}s）\n"
        f"     [s] 跳过本任务（走 fallback 站点）\n"
        f"     [a] 永久跳过该域名（本次进程内不再询问）\n"
        f"   你的选择 [L/s/a]（默认 L，{_ASK_TIMEOUT}s 内未响应按 s 跳过）: "
    )

    def _read() -> str:
        # 先把 prompt flush 到 stdout，避免被 line-buffering 吞掉
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return input("").strip().lower()

    try:
        choice = await asyncio.wait_for(
            asyncio.to_thread(_read),
            timeout=_ASK_TIMEOUT,
        )
    except asyncio.TimeoutError:
        print(f"\n  ⏱️  {_ASK_TIMEOUT}s 内未响应，按跳过处理")
        return "skip"
    except (EOFError, KeyboardInterrupt):
        print()
        return "skip"

    if choice in ("", "l", "y", "yes", "login"):
        return "login"
    if choice in ("a", "abort", "block"):
        return "abort"
    return "skip"


async def _handle_login_wall(domain: str, target_url: str) -> bool:
    """登录墙处理统一入口。返回 True=已登录可继续；False=放弃当前任务走 fallback"""
    # 进程内已选"永久跳过"的域名直接返回 False
    if domain and domain in _PERMANENTLY_SKIPPED:
        logger.info("  🚫 域名 %s 已被永久跳过，直接走 fallback", domain)
        return False

    if _LOGIN_MODE == "skip":
        return False
    if _LOGIN_MODE == "auto":
        return await _interactive_login_and_resume(domain, target_url)

    # 默认 ask 模式：先问用户
    choice = await _ask_user_login_choice(domain, target_url)
    if choice == "login":
        return await _interactive_login_and_resume(domain, target_url)
    if choice == "abort":
        if domain:
            _PERMANENTLY_SKIPPED.add(domain)
            logger.info("  🚫 已将 %s 加入本次进程的永久跳过列表", domain)
        return False
    # skip
    return False


async def execute_with_fallback(
    llm: BaseLLM,
    tools: dict,
    task: SubTask,
) -> SubTask:
    """执行任务并在主站失败时自动切换到备选网站"""
    result = await execute_task(llm, tools, task)

    if result.status == TaskStatus.COMPLETED and result.result:
        error_signals = [
            "LOGIN_WALL", "需要登录", "请登录",
            "任务失败（重试", "无法访问此网站", "该网页无法显示", "连接已被重置",
            "ERR_CONNECTION", "ERR_NAME_NOT_RESOLVED",
            "404 Not Found", "502 Bad Gateway", "503 Service Unavailable",
        ]
        has_error = any(s in result.result for s in error_signals)
        too_short = len(result.result.strip()) < 50
        if not has_error and not too_short:
            return result

    # 失败任务（含登录墙）也走 fallback
    if result.status == TaskStatus.FAILED and "LOGIN_WALL" in (result.result or ""):
        logger.info("  🔒 登录墙触发 fallback: %s → %s", task.website, task.fallback_website or task.fallback_url)

    if task.fallback_url:
        logger.info("  🔄 主站失败，切换备选: %s", task.fallback_website or task.fallback_url)
        fb_site = task.fallback_website or "备选网站"
        # 重写 description，避免原描述里的主站名诱导 LLM 又访问主站
        fb_desc = (
            f"[备选 {fb_site}] 主站「{task.website}」不可达，"
            f"请改在 {fb_site}（{task.fallback_url}）上完成同等调研：{task.description}。"
            f"必须使用 navigate 工具访问 {task.fallback_url}，不要重新尝试主站。"
        )
        fallback = SubTask(
            id=f"{task.id}_fallback",
            description=fb_desc,
            website=fb_site,
            url=task.fallback_url,
            max_retries=1,
        )
        return await execute_task(llm, tools, fallback)

    return result
