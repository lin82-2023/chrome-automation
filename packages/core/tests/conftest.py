"""共享 pytest fixtures"""
import pytest
from chrome_agent_core import ToolRegistry


@pytest.fixture(autouse=False)
def clean_registry():
    """需要干净 ToolRegistry 的测试请显式声明此 fixture"""
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()
