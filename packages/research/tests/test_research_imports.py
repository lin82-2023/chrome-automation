"""chrome_research 公开 API 导入测试"""


def test_top_level_imports():
    from chrome_research import (
        ResearchAgent,
        TaskStatus,
    )

    assert ResearchAgent is not None
    assert TaskStatus.PENDING.value == "pending"


def test_submodule_imports():
    from chrome_research import agent, execute, plan, prompts, synthesize, types

    assert hasattr(plan, "generate_plan")
    assert hasattr(execute, "execute_task")
    assert hasattr(synthesize, "synthesize")
    assert hasattr(prompts, "plan_prompt")
    assert hasattr(types, "SubTask")
    assert hasattr(agent, "ResearchAgent")
