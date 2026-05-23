"""chrome-research - 多网站深度调研 Agent

基于 chrome-agent-core 的 CDP 工具集，提供：
- 任务规划（plan）
- 子任务执行（execute）
- 结果综合（synthesize）

使用方式：
    from chrome_research import ResearchAgent, create_research_agent
    agent = await create_research_agent(api_key="...")
    report = await agent.run("AI Agent 框架对比", num_websites=5)
"""

__version__ = "0.1.0"

from .agent import ResearchAgent, create_research_agent
from .types import ResearchPlan, SubTask, TaskStatus

__all__ = [
    "__version__",
    "ResearchAgent",
    "create_research_agent",
    "ResearchPlan",
    "SubTask",
    "TaskStatus",
]
