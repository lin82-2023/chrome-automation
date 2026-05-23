"""结果综合：将多源调研结果合成为最终报告"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .prompts import final_synthesis_prompt, per_source_summary_prompt

if TYPE_CHECKING:
    from chrome_agent_core import BaseLLM

logger = logging.getLogger(__name__)

LLM_SUMMARY_TIMEOUT = 60.0


async def _llm_chat(llm: BaseLLM, prompt: str, timeout: float) -> str:
    response = await asyncio.wait_for(
        llm.chat(messages=[{"role": "user", "content": prompt}], tools=[]),
        timeout=timeout,
    )
    return response.get("content", "")


async def synthesize(
    llm: BaseLLM,
    final_results: list[dict],
    goal: str | None = None,
) -> str:
    """生成最终调研报告

    策略：
    1. 全部失败 → 直接返回结构化失败报告，不调用 LLM
    2. 部分成功 → 仅对成功结果调用 LLM 总结，失败站点以附录形式追加
    3. LLM 综合失败 → 降级为各来源摘要拼接
    """
    research_goal = goal or "（未提供研究目标）"

    success = [r for r in final_results if r.get("status") == "completed"]
    failed = [r for r in final_results if r.get("status") != "completed"]
    logger.info("📈 数据统计: %d 成功, %d 失败", len(success), len(failed))

    if not success:
        return _failure_report(final_results, failed)

    # 1. 各来源单独摘要
    summaries = []
    for i, r in enumerate(success):
        try:
            logger.info("  → 总结来源 %d/%d: %s", i + 1, len(success), r["website"])
            text = await _llm_chat(
                llm,
                per_source_summary_prompt(r["website"], r["status"], r["result"]),
                LLM_SUMMARY_TIMEOUT,
            )
            summaries.append({"website": r["website"], "summary": text or r["result"][:500]})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("    ⚠️  总结失败，使用原始数据: %s", e)
            summaries.append({"website": r["website"], "summary": r["result"][:500]})

    # 2. 失败附录
    failed_section = ""
    if failed:
        failed_section = "\n\n## 未能完成的站点\n\n"
        for r in failed:
            failed_section += f"- **{r['website']}**：{r['result'][:150]}\n"

    # 3. 综合
    summaries_text = "\n\n".join(
        f"### {s['website']}\n{s['summary']}" for s in summaries
    )
    try:
        final = await _llm_chat(
            llm,
            final_synthesis_prompt(research_goal, summaries_text),
            LLM_SUMMARY_TIMEOUT,
        )
        return final + failed_section
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning("综合失败，返回简化报告: %s", e)
        return f"# 调研报告（简化版）\n\n{summaries_text}{failed_section}"


def _failure_report(final_results: list[dict], failed: list[dict]) -> str:
    lines = [
        "# 调研报告：数据收集失败\n",
        "## 失败概述\n",
        f"本次调研共尝试 {len(final_results)} 个网站，全部失败。\n",
        "## 失败详情\n",
    ]
    for r in failed:
        lines.append(f"### {r['website']}\n")
        lines.append(f"- 状态: {r['status']}\n")
        lines.append(f"- 原因: {r['result'][:200]}\n\n")
    lines += [
        "## 建议\n",
        "1. 检查网络连接\n",
        "2. 尝试手动访问上述网站确认可用性\n",
        "3. 检查浏览器是否正常启动\n",
        "4. 考虑使用备选网站或调整搜索关键词\n",
    ]
    return "".join(lines)
