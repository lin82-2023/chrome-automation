"""结果综合测试"""
import pytest
from chrome_research.synthesize import synthesize


class _FakeLLM:
    def __init__(self, response: str):
        self._response = response

    async def chat(self, messages, tools=None, **kwargs):
        return {"content": self._response}


@pytest.mark.asyncio
async def test_all_failed_returns_failure_report_without_llm():
    """全部失败时不调用 LLM，直接返回失败报告"""
    failed_results = [
        {"website": "X", "status": "failed", "result": "404 Not Found"},
        {"website": "Y", "status": "error", "result": "ERR_CONNECTION"},
    ]

    class _Sentinel:
        async def chat(self, *args, **kwargs):
            raise AssertionError("不应调用 LLM")

    report = await synthesize(_Sentinel(), failed_results, goal="X")
    assert "失败" in report
    assert "X" in report
    assert "Y" in report


@pytest.mark.asyncio
async def test_partial_success_uses_llm_summary():
    llm = _FakeLLM("已总结")
    results = [
        {"website": "知乎", "status": "completed", "result": "充分内容" * 50},
        {"website": "Y", "status": "failed", "result": "网络错误"},
    ]
    report = await synthesize(llm, results, goal="g")
    assert "未能完成的站点" in report
    assert "Y" in report


@pytest.mark.asyncio
async def test_synthesis_llm_failure_falls_back():
    """最终综合 LLM 抛错时降级为简化报告"""

    class _PartialLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, **kwargs):
            self.calls += 1
            # 第 N 次成功（per-source），最后一次（综合）失败
            if self.calls > 1:
                raise RuntimeError("综合失败")
            return {"content": "per-source 摘要"}

    results = [
        {"website": "A", "status": "completed", "result": "内容" * 30},
    ]
    report = await synthesize(_PartialLLM(), results, goal="g")
    assert "简化版" in report
