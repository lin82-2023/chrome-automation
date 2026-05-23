"""任务规划：将研究目标分解为多网站子任务"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from .prompts import plan_prompt
from .types import ResearchPlan, SubTask

if TYPE_CHECKING:
    from chrome_agent_core import BaseLLM

logger = logging.getLogger(__name__)

LLM_PLAN_TIMEOUT = 60.0


async def generate_plan(
    llm: BaseLLM,
    user_goal: str,
    num_websites: int = 5,
) -> ResearchPlan:
    """调用 LLM 生成研究计划。失败时回退到默认计划。"""
    prompt = plan_prompt(user_goal, num_websites)
    try:
        response = await asyncio.wait_for(
            llm.chat(messages=[{"role": "user", "content": prompt}], tools=[]),
            timeout=LLM_PLAN_TIMEOUT,
        )
        content = response.get("content", "")
        plan_data = json.loads(content)

        plan = ResearchPlan(goal=user_goal)
        for i, site in enumerate(plan_data.get("websites", [])):
            fallback = site.get("fallback", {}) or {}
            task = SubTask(
                id=f"task_{i}",
                description=f"调研 {site['website']}: {site.get('focus', '')}",
                website=site["website"],
                url=site["url"],
                fallback_url=fallback.get("url"),
                fallback_website=fallback.get("website"),
            )
            plan.sub_tasks.append(task)
        return plan
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning("计划解析失败：%s，回退默认计划", e)
        return default_plan(user_goal, num_websites)


def default_plan(goal: str, num: int) -> ResearchPlan:
    """规划 LLM 失败时的降级方案"""
    plan = ResearchPlan(goal=goal)
    default_sites = [
        ("知乎", "https://www.zhihu.com", "技术讨论"),
        ("CSDN", "https://www.csdn.net", "技术博客"),
        ("arXiv", "https://arxiv.org", "论文预印本"),
        ("GitHub", "https://github.com", "开源项目"),
        ("百度学术", "https://xueshu.baidu.com", "中文学术"),
        ("掘金", "https://juejin.cn", "前沿技术"),
    ]
    for i, (name, url, focus) in enumerate(default_sites[:num]):
        plan.sub_tasks.append(
            SubTask(
                id=f"task_{i}",
                description=f"调研 {name}: {focus}",
                website=name,
                url=url,
            )
        )
    return plan
