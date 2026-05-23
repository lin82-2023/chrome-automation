#!/usr/bin/env python3
"""
Browser Tools - Browser operation tools for the agent framework
"""
import asyncio

from ..agent.tool import BaseTool, ToolResult
from ..agent.tool_registry import ToolRegistry


def _import_from_core():
    """延迟导入，避免循环依赖"""
    from ..cdp import (
        cdp_execute,
        cdp_navigate,
        click_element,
        close_tab,
        create_tab,
        find_element,
        get_all_tabs,
        get_elements,
        get_page_info,
        input_text,
        submit_form,
        switch_tab,
    )
    return {
        'cdp_navigate': cdp_navigate,
        'get_page_info': get_page_info,
        'get_elements': get_elements,
        'find_element': find_element,
        'click_element': click_element,
        'input_text': input_text,
        'submit_form': submit_form,
        'get_all_tabs': get_all_tabs,
        'switch_tab': switch_tab,
        'create_tab': create_tab,
        'close_tab': close_tab,
        'cdp_execute': cdp_execute
    }


class NavigateTool(BaseTool):
    """导航到指定URL"""
    name = "navigate"
    label = "导航"
    description = "导航到指定URL，加载页面"
    parameters = {
        "url": {"type": "string", "description": "目标URL", "required": True},
        "use_stealth": {"type": "boolean", "description": "是否应用Stealth防检测", "default": True}
    }

    async def execute(self, url: str, use_stealth: bool = True, **kwargs) -> ToolResult:
        core = _import_from_core()
        success = core['cdp_navigate'](url, wait_load=3)
        if success:
            info = core['get_page_info']()
            return ToolResult(
                success=True,
                content=f"已导航到 {url}",
                details=info
            )
        else:
            return ToolResult(
                success=False,
                content=f"导航失败: {url}",
                details={'error': 'CDP连接不可用'}
            )


class ClickTool(BaseTool):
    """点击包含指定文本的元素"""
    name = "click"
    label = "点击"
    description = "点击页面中包含指定文本的元素（支持模糊匹配）"
    parameters = {
        "text": {"type": "string", "description": "要点击的元素的文本（支持部分匹配）", "required": True},
        "tag": {"type": "string", "description": "限定标签类型（如a、button）", "required": False}
    }

    async def execute(self, text: str, tag: str = None, **kwargs) -> ToolResult:
        core = _import_from_core()

        # 先尝试精确匹配
        success = core['click_element'](text=text, tag=tag)

        if not success:
            # 失败时尝试更短的关键字
            # 取前10个字符作为模糊匹配
            short_text = text[:10] if len(text) > 10 else text
            if short_text != text:
                success = core['click_element'](text=short_text, tag=tag)
                if success:
                    return ToolResult(
                        success=True,
                        content=f"成功点击（模糊匹配）: {short_text}... (原文: {text})"
                    )

        return ToolResult(
            success=success,
            content=f"{'成功' if success else '失败'}点击: {text}"
        )


class InputTool(BaseTool):
    """向输入框输入文本"""
    name = "input"
    label = "输入"
    description = "向页面中的输入框输入文本"
    parameters = {
        "text": {"type": "string", "description": "要输入的文本", "required": True},
        "selector": {"type": "string", "description": "CSS选择器", "default": "#kw"}
    }

    async def execute(self, text: str, selector: str = "#kw", **kwargs) -> ToolResult:
        core = _import_from_core()
        success = core['input_text'](text, selector=selector)
        return ToolResult(
            success=success,
            content=f"{'成功' if success else '失败'}输入: {text} 到 {selector}"
        )


class SubmitTool(BaseTool):
    """提交表单"""
    name = "submit"
    label = "提交表单"
    description = "提交页面中的表单"
    parameters = {
        "selector": {"type": "string", "description": "表单CSS选择器", "default": "form"}
    }

    async def execute(self, selector: str = "form", **kwargs) -> ToolResult:
        core = _import_from_core()
        success = core['submit_form'](selector=selector)
        return ToolResult(
            success=success,
            content=f"{'成功' if success else '失败'}提交表单: {selector}"
        )


class GetPageInfoTool(BaseTool):
    """获取当前页面信息"""
    name = "get_page_info"
    label = "页面信息"
    description = "获取当前页面的URL和标题"
    parameters = {}

    async def execute(self, **kwargs) -> ToolResult:
        core = _import_from_core()
        info = core['get_page_info']()
        return ToolResult(
            success=bool(info),
            content=f"{info.get('title', 'Unknown')} - {info.get('url', 'Unknown')}",
            details=info
        )


class GetElementsTool(BaseTool):
    """获取页面所有DOM元素"""
    name = "get_elements"
    label = "获取元素"
    description = "获取页面所有DOM元素及其属性"
    parameters = {
        "use_stealth": {"type": "boolean", "description": "是否使用Stealth模式", "default": False},
        "limit": {"type": "integer", "description": "限制返回数量", "default": 500}
    }

    async def execute(self, use_stealth: bool = False, limit: int = 500, **kwargs) -> ToolResult:
        core = _import_from_core()
        elements, source = core['get_elements'](limit=limit, use_stealth=use_stealth)
        return ToolResult(
            success=True,
            content=f"获取到 {len(elements)} 个元素",
            details={"count": len(elements), "source": source}
        )


class FindElementTool(BaseTool):
    """查找包含特定文本的元素"""
    name = "find_element"
    label = "查找元素"
    description = "在页面中查找包含指定文本的元素"
    parameters = {
        "text": {"type": "string", "description": "要查找的文本", "required": True},
        "tag": {"type": "string", "description": "限定标签类型", "required": False}
    }

    async def execute(self, text: str, tag: str = None, **kwargs) -> ToolResult:
        core = _import_from_core()
        elements, _ = core['get_elements']()
        elem = core['find_element'](elements, text=text, tag=tag)
        if elem:
            return ToolResult(
                success=True,
                content=f"找到元素: {elem.get('tag', '')} - {elem.get('text', '')[:50]}",
                details=elem
            )
        return ToolResult(success=False, content=f"未找到元素: {text}")


class EvalJsTool(BaseTool):
    """在页面执行JavaScript代码"""
    name = "eval_js"
    label = "执行JS"
    description = "在当前页面执行JavaScript代码并返回结果"
    parameters = {
        "code": {"type": "string", "description": "JavaScript代码", "required": True}
    }

    async def execute(self, code: str, **kwargs) -> ToolResult:
        core = _import_from_core()
        result = core['cdp_execute'](code)

        # 改进错误提示
        if result is None:
            return ToolResult(
                success=False,
                content="无返回值（可能原因：1.页面未加载完 2.选择器错误 3.元素不存在）",
                details={"code_preview": code[:100]}
            )

        # 检查是否是空结果
        if result == "" or result == [] or result == {}:
            return ToolResult(
                success=True,
                content=f"执行成功但结果为空: {result}（可能页面结构不匹配）",
                details={"code_preview": code[:100]}
            )

        return ToolResult(
            success=True,
            content=str(result)[:500],
            details={"result": result}
        )


class ListTabsTool(BaseTool):
    """列出所有标签页"""
    name = "list_tabs"
    label = "标签页列表"
    description = "列出浏览器中所有打开的标签页"
    parameters = {}

    async def execute(self, **kwargs) -> ToolResult:
        core = _import_from_core()
        tabs = core['get_all_tabs']()
        tab_info = [{"index": t.get('index'), "title": t.get('title', '')[:30], "url": t.get('url', '')[:50]} for t in tabs]
        return ToolResult(
            success=True,
            content=f"共 {len(tabs)} 个标签页",
            details={"tabs": tab_info}
        )


class SwitchTabTool(BaseTool):
    """切换到指定标签页"""
    name = "switch_tab"
    label = "切换标签"
    description = "切换到指定索引的标签页"
    parameters = {
        "index": {"type": "integer", "description": "标签页索引", "required": True}
    }

    async def execute(self, index: int, **kwargs) -> ToolResult:
        core = _import_from_core()
        success = core['switch_tab'](index)
        return ToolResult(
            success=success,
            content=f"{'成功' if success else '失败'}切换到标签页 {index}"
        )


class NewTabTool(BaseTool):
    """创建新标签页"""
    name = "new_tab"
    label = "新建标签"
    description = "创建新的空白标签页或导航到指定URL"
    parameters = {
        "url": {"type": "string", "description": "新标签页URL", "default": "about:blank"}
    }

    async def execute(self, url: str = "about:blank", **kwargs) -> ToolResult:
        core = _import_from_core()
        success = core['create_tab'](url)
        return ToolResult(
            success=success,
            content=f"{'成功' if success else '失败'}创建新标签页: {url}"
        )


class CloseTabTool(BaseTool):
    """关闭标签页"""
    name = "close_tab"
    label = "关闭标签"
    description = "关闭指定索引的标签页"
    parameters = {
        "index": {"type": "integer", "description": "标签页索引", "required": False}
    }

    async def execute(self, index: int = None, **kwargs) -> ToolResult:
        core = _import_from_core()
        success = core['close_tab'](index)
        return ToolResult(
            success=success,
            content=f"{'成功' if success else '失败'}关闭标签页"
        )


class LaunchBrowserTool(BaseTool):
    """启动干净的Chrome浏览器"""
    name = "launch_browser"
    label = "启动浏览器"
    description = "启动一个干净的Chrome浏览器实例（未登录状态），使用独立的临时用户数据目录"
    parameters = {
        "port": {"type": "integer", "description": "远程调试端口", "default": 9222}
    }

    async def execute(self, port: int = 9222, **kwargs) -> ToolResult:
        import platform
        import socket
        import subprocess
        import tempfile
        import urllib.request

        try:
            # 先检查端口是否已监听
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            port_in_use = sock.connect_ex(('localhost', port)) == 0
            sock.close()

            if port_in_use:
                # 验证是否真的是Chrome的CDP端口
                try:
                    resp = urllib.request.urlopen(f'http://localhost:{port}/json', timeout=2)
                    if resp.status == 200:
                        import json
                        tabs = json.loads(resp.read())
                        page_tabs = [t for t in tabs if t.get('type') == 'page']
                        return ToolResult(
                            success=True,
                            content=f"Chrome浏览器已连接（端口 {port}），共 {len(page_tabs)} 个页面标签"
                        )
                except:
                    pass

            # 创建临时用户数据目录（干净的、未登录的状态）
            temp_profile = tempfile.mkdtemp(prefix='chrome_agent_')

            # 根据操作系统查找Chrome路径
            system = platform.system()
            if system == "Darwin":  # macOS
                chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            elif system == "Windows":
                chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            else:  # Linux
                chrome_path = "google-chrome"

            # 启动Chrome，使用临时用户数据目录（干净状态）
            cmd = [
                chrome_path,
                f'--remote-debugging-port={port}',
                '--remote-allow-origins=*',
                f'--user-data-dir={temp_profile}',  # 使用临时目录，避免使用已登录状态
                '--no-first-run',
                '--no-default-browser-check',
                'about:blank'
            ]

            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

            # 等待浏览器完全启动并建立CDP连接
            for i in range(15):
                await asyncio.sleep(1)
                try:
                    resp = urllib.request.urlopen(f'http://localhost:{port}/json', timeout=2)
                    if resp.status == 200:
                        return ToolResult(
                            success=True,
                            content=f"已启动干净的Chrome浏览器（端口 {port}），未登录状态，临时配置: {temp_profile}"
                        )
                except:
                    pass

            return ToolResult(
                success=False,
                content=f"启动浏览器失败，请手动运行:\n{chrome_path} --remote-debugging-port={port} --user-data-dir=/tmp/chrome_test"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content=f"启动浏览器失败: {str(e)}"
            )


class SearchTool(BaseTool):
    """执行搜索流程（输入+提交）"""
    name = "browser_search"
    label = "搜索"
    description = "在搜索框输入关键词并提交搜索"
    parameters = {
        "keyword": {"type": "string", "description": "搜索关键词", "required": True},
        "input_selector": {"type": "string", "description": "输入框选择器", "default": "#kw"},
        "search_button": {"type": "string", "description": "搜索按钮文本", "required": False}
    }

    async def execute(self, keyword: str, input_selector: str = "#kw",
                     search_button: str = None, **kwargs) -> ToolResult:
        core = _import_from_core()
        # 输入
        core['input_text'](keyword, selector=input_selector)
        # 点击搜索按钮或提交表单
        if search_button:
            success = core['click_element'](text=search_button)
        else:
            success = core['submit_form'](form_selector='form')
        return ToolResult(
            success=success,
            content=f"搜索: {keyword}",
            details={"keyword": keyword}
        )


# 注册所有工具的函数
def register_browser_tools():
    """注册所有浏览器工具到 ToolRegistry。幂等。"""
    tools = [
        LaunchBrowserTool(),
        NavigateTool(),
        ClickTool(),
        InputTool(),
        SubmitTool(),
        GetPageInfoTool(),
        GetElementsTool(),
        FindElementTool(),
        EvalJsTool(),
        ListTabsTool(),
        SwitchTabTool(),
        NewTabTool(),
        CloseTabTool(),
        SearchTool(),
    ]
    for tool in tools:
        ToolRegistry.register(tool.get_definition())
