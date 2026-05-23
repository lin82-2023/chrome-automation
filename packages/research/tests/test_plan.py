"""调研规划测试（mock LLM）"""
import json

import pytest
from chrome_research.plan import default_plan, generate_plan


class _FakeLLM:
    """带可注入响应的假 LLM"""

    def __init__(self, response_content: str):
        self._content = response_content
        self.calls = []

    async def chat(self, messages, tools=None, **kwargs):
        self.calls.append((messages, tools))
        return {"content": self._content}


def test_default_plan_basic():
    plan = default_plan("AI Agent 调研", num=3)
    assert plan.goal == "AI Agent 调研"
    assert len(plan.sub_tasks) == 3
    for t in plan.sub_tasks:
        assert t.url.startswith("http")
        assert t.website


@pytest.mark.asyncio
async def test_generate_plan_parses_json():
    llm = _FakeLLM(json.dumps({
        "goal": "AI Agent",
        "websites": [
            {
                "website": "知乎",
                "url": "https://www.zhihu.com",
                "focus": "讨论",
                "fallback": {"website": "CSDN", "url": "https://www.csdn.net"},
            },
            {
                "website": "GitHub",
                "url": "https://github.com",
                "focus": "项目",
            },
        ],
    }))
    plan = await generate_plan(llm, "AI Agent", num_websites=2)
    assert plan.goal == "AI Agent"
    assert len(plan.sub_tasks) == 2
    assert plan.sub_tasks[0].website == "知乎"
    assert plan.sub_tasks[0].fallback_url == "https://www.csdn.net"
    assert plan.sub_tasks[1].fallback_url is None


@pytest.mark.asyncio
async def test_generate_plan_falls_back_on_invalid_json():
    llm = _FakeLLM("not json content")
    plan = await generate_plan(llm, "X", num_websites=4)
    # 解析失败应回退到默认计划
    assert plan.goal == "X"
    assert len(plan.sub_tasks) == 4
