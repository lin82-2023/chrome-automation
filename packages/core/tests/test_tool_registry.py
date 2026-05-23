"""ToolRegistry 单元测试"""
import pytest
from chrome_agent_core import BaseTool, ToolDefinition, ToolRegistry, ToolResult


class _DummyTool(BaseTool):
    name = "dummy"
    label = "Dummy"
    description = "测试用工具"
    parameters = {"x": {"type": "string", "required": False}}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="ok")


def test_register_and_get(clean_registry):
    tool = _DummyTool().get_definition()
    ToolRegistry.register(tool)
    assert ToolRegistry.get("dummy") is tool
    assert "dummy" in ToolRegistry.list_tool_names()
    assert ToolRegistry.count() == 1


def test_register_overwrites(clean_registry):
    a = ToolDefinition(name="t", label="T", description="a", parameters={}, execute=None)
    b = ToolDefinition(name="t", label="T", description="b", parameters={}, execute=None)
    ToolRegistry.register(a)
    ToolRegistry.register(b)
    assert ToolRegistry.count() == 1
    assert ToolRegistry.get("t").description == "b"


def test_unregister(clean_registry):
    ToolRegistry.register(_DummyTool().get_definition())
    assert ToolRegistry.unregister("dummy") is True
    assert ToolRegistry.unregister("dummy") is False
    assert ToolRegistry.get("dummy") is None


def test_clear(clean_registry):
    for i in range(3):
        ToolRegistry.register(
            ToolDefinition(name=f"t{i}", label="", description="", parameters={}, execute=None)
        )
    assert ToolRegistry.count() == 3
    ToolRegistry.clear()
    assert ToolRegistry.count() == 0


def test_register_all_tools_idempotent(clean_registry):
    """tools.register_all_tools 应该是幂等的"""
    from chrome_agent_core.tools import register_all_tools

    register_all_tools()
    n = ToolRegistry.count()
    assert n > 0
    register_all_tools()
    assert ToolRegistry.count() == n


@pytest.mark.asyncio
async def test_dummy_tool_execute(clean_registry):
    tool = _DummyTool()
    result = await tool.execute(x="hello")
    assert result.success
    assert result.content == "ok"
