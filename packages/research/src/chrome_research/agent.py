"""ResearchAgent: 顺序执行多网站调研并生成报告"""
from __future__ import annotations

import asyncio
import logging

from chrome_agent_core import BaseLLM, ToolRegistry, create_llm, get_config
from chrome_agent_core.tools import register_all_tools

from .execute import execute_with_fallback
from .plan import default_plan, generate_plan
from .synthesize import synthesize
from .types import ResearchPlan, TaskStatus

logger = logging.getLogger(__name__)


class ResearchAgent:
    """多网站深度调研 Agent

    流程：
    1. plan_research()    LLM 拆解为多网站子任务
    2. execute_research() 顺序执行每个子任务（共享单一 Chrome 实例）
    3. synthesize_results() 综合各来源结果生成最终报告

    注意事项：
    - 不支持跨请求复用：每次调研请通过 create_research_agent() 创建新实例
    - 进度查询：通过 get_progress() 实时获取执行状态
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.tools: dict = {t.name: t for t in ToolRegistry.list_tools()}
        self.plan: ResearchPlan | None = None
        self.results: list[dict] = []

    async def plan_research(self, user_goal: str, num_websites: int = 5) -> ResearchPlan:
        return await generate_plan(self.llm, user_goal, num_websites)

    async def execute_research(self, plan: ResearchPlan) -> list[dict]:
        """顺序执行所有子任务（浏览器单实例限制）"""
        plan.status = TaskStatus.RUNNING
        final_results: list[dict] = []
        logger.info("🚀 开始顺序调研（共 %d 个任务）", len(plan.sub_tasks))

        for i, task in enumerate(plan.sub_tasks):
            logger.info("[%d/%d] 处理: %s", i + 1, len(plan.sub_tasks), task.website)
            try:
                result = await execute_with_fallback(self.llm, self.tools, task)
                final_results.append({
                    "website": result.website,
                    "status": result.status.value,
                    "result": result.result or result.error or "无结果",
                })
            except asyncio.CancelledError:
                logger.warning("调研被取消，已完成 %d/%d", i, len(plan.sub_tasks))
                final_results.append({
                    "website": task.website,
                    "status": "cancelled",
                    "result": "调研被取消",
                })
                self.results = final_results
                raise
            except Exception as e:
                final_results.append({
                    "website": task.website,
                    "status": "error",
                    "result": f"执行异常: {e}",
                })
            plan.current_step = i + 1

        plan.status = TaskStatus.COMPLETED
        self.results = final_results
        return final_results

    async def synthesize_results(
        self,
        final_results: list[dict],
        goal: str | None = None,
    ) -> str:
        research_goal = goal or (self.plan.goal if self.plan else None)
        return await synthesize(self.llm, final_results, goal=research_goal)

    def get_progress(self) -> dict:
        if not self.plan:
            return {"status": "idle", "current_step": 0, "total": 0, "percent": 0}
        total = len(self.plan.sub_tasks)
        return {
            "status": self.plan.status.value,
            "current_step": self.plan.current_step,
            "total": total,
            "percent": int(self.plan.current_step / total * 100) if total else 0,
        }

    def get_last_run_state(self) -> dict:
        return {"plan": self.plan, "results": self.results}

    async def run(
        self,
        user_goal: str,
        num_websites: int = 5,
    ) -> str:
        """完整调研流程：规划 → 执行 → 综合"""
        logger.info("=" * 60)
        logger.info("🎯 研究目标: %s", user_goal)
        logger.info("=" * 60)

        try:
            self.plan = await self.plan_research(user_goal, num_websites)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("计划生成失败: %s，使用默认计划", e)
            self.plan = default_plan(user_goal, num_websites)

        logger.info("✅ 计划生成: %d 个调研任务", len(self.plan.sub_tasks))
        for i, task in enumerate(self.plan.sub_tasks, 1):
            logger.info("  %d. %s - %s", i, task.website, task.description)

        final_results = await self.execute_research(self.plan)
        report = await self.synthesize_results(final_results, goal=user_goal)
        logger.info("✅ 调研完成")
        return report


# 全局工具注册 guard
_tools_registered = False


async def create_research_agent(
    api_key: str | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    llm: BaseLLM | None = None,
) -> ResearchAgent:
    """创建 ResearchAgent。首次调用会注册全局工具。

    Args:
        api_key:  覆盖 API Key；为空时从对应 Provider 的环境变量读取。
        provider: ``bailian`` / ``openai`` / ``anthropic`` / ``deepseek`` /
                  ``moonshot`` / ``zhipu`` / ``openrouter`` / ``groq`` /
                  ``ollama``。为空时使用全局配置（``Config.provider``）。
        model:    覆盖模型名。
        base_url: 覆盖请求基址。
        llm:      已构造好的 LLM 实例。一旦传入则忽略上面其余 LLM 相关参数。
    """
    global _tools_registered
    if not _tools_registered:
        register_all_tools()
        _tools_registered = True

    if llm is None:
        config = get_config()
        llm = create_llm(
            provider=provider or config.provider,
            api_key=api_key,
            model=model or config.model,
            base_url=base_url or (config.base_url or None),
        )
    return ResearchAgent(llm=llm)
