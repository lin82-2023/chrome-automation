"""chrome-agent-core 工具集合

提供：
- 浏览器自动化工具（导航、点击、输入、Tab 管理等）
- Session 管理工具（登录持久化、状态检查等）

使用方式：
    from chrome_agent_core.tools import register_all_tools
    register_all_tools()  # 注册所有内置工具到 ToolRegistry
"""
from .browser_tools import register_browser_tools
from .session_tools import register_session_tools


def register_all_tools() -> None:
    """注册所有内置工具（浏览器 + Session）到 ToolRegistry。幂等。"""
    register_browser_tools()
    register_session_tools()


__all__ = [
    "register_browser_tools",
    "register_session_tools",
    "register_all_tools",
]
