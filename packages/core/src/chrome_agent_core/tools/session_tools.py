#!/usr/bin/env python3
"""Session 和登录管理工具"""
from ..agent.tool import BaseTool, ToolResult


class CheckLoginTool(BaseTool):
    """检查登录状态"""
    name = "check_login"
    label = "检查登录"
    description = "检查当前网站是否已登录"
    parameters = {
        "domain": {"type": "string", "description": "要检查的域名，如 zhihu.com", "required": True}
    }

    async def execute(self, domain: str, **kwargs) -> ToolResult:
        try:
            from ..session import SessionManager

            manager = SessionManager(domain)
            has_session = manager.exists()
            is_expired = manager.is_expired(days=30) if has_session else True

            if has_session and not is_expired:
                return ToolResult(success=True, content=f"已登录 {domain}，Session 有效")
            else:
                return ToolResult(success=False, content=f"未登录 {domain} 或 Session 已过期")
        except Exception as e:
            return ToolResult(success=False, content=f"检查登录状态失败: {str(e)}")


class SaveSessionTool(BaseTool):
    """保存登录状态"""
    name = "save_session"
    label = "保存登录"
    description = "保存当前登录状态（cookies、localStorage等）"
    parameters = {
        "domain": {"type": "string", "description": "要保存的域名", "required": True}
    }

    async def execute(self, domain: str, **kwargs) -> ToolResult:
        try:
            from ..session import save_session
            save_session(domain)
            return ToolResult(success=True, content=f"已保存 {domain} 的登录状态")
        except Exception as e:
            return ToolResult(success=False, content=f"保存登录状态失败: {str(e)}")


class LoadSessionTool(BaseTool):
    """加载登录状态"""
    name = "load_session"
    label = "加载登录"
    description = "加载之前保存的登录状态，并刷新页面使其生效"
    parameters = {
        "domain": {"type": "string", "description": "要加载的域名", "required": True},
        "url": {"type": "string", "description": "加载后导航到的URL（可选）", "default": None}
    }

    async def execute(self, domain: str, url: str = None, **kwargs) -> ToolResult:
        try:
            from ..cdp import cdp_navigate
            from ..session import load_session

            success = load_session(domain)
            if success:
                if url:
                    cdp_navigate(url, wait_load=2)
                return ToolResult(
                    success=True,
                    content=f"已加载 {domain} 的登录状态。登录状态需要刷新页面或导航后才能生效。"
                )
            else:
                return ToolResult(success=False, content=f"未找到 {domain} 的保存的登录状态")
        except Exception as e:
            return ToolResult(success=False, content=f"加载登录状态失败: {str(e)}")


class WaitForLoginTool(BaseTool):
    """等待用户手动登录"""
    name = "wait_for_login"
    label = "等待登录"
    description = "打开登录页面，等待用户手动登录"
    parameters = {
        "login_url": {"type": "string", "description": "登录页面URL", "required": True},
        "timeout": {"type": "integer", "description": "超时时间（秒）", "default": 300}
    }

    async def execute(self, login_url: str, timeout: int = 300, **kwargs) -> ToolResult:
        try:
            from ..cdp import cdp_navigate
            from ..session import wait_for_manual_login

            cdp_navigate(login_url, wait_load=3)
            print(f"\n⏳ 请在浏览器中完成登录（{timeout}秒内）...")
            wait_for_manual_login(login_url, timeout=timeout)

            return ToolResult(success=True, content="用户已完成登录")
        except Exception as e:
            return ToolResult(success=False, content=f"等待登录失败: {str(e)}")


def register_session_tools():
    """注册所有 Session 管理工具"""
    from ..agent.tool_registry import ToolRegistry

    tools = [
        CheckLoginTool(),
        SaveSessionTool(),
        LoadSessionTool(),
        WaitForLoginTool(),
    ]

    for tool in tools:
        ToolRegistry.register(tool.get_definition())
