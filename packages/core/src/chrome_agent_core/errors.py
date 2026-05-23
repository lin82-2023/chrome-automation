"""chrome-agent-core 异常体系

设计原则：
- 所有可预期错误都继承自 ChromeAgentError
- 子类按错误源分类，便于上层捕获
- 不替换标准库已有异常（如 TimeoutError、ValueError）的语义，仅做补充包装
"""


class ChromeAgentError(Exception):
    """所有 chrome-agent-core 自定义异常的基类"""


class ConfigError(ChromeAgentError):
    """配置错误（缺少 API Key、未知模型等）"""


class CDPError(ChromeAgentError):
    """CDP 协议层错误（连接失败、调用失败）"""


class CDPConnectionError(CDPError):
    """无法连接到 Chrome（websocket 握手失败、Chrome 未启动）"""


class BrowserLaunchError(ChromeAgentError):
    """无法启动 Chrome 浏览器"""


class NavigationError(ChromeAgentError):
    """导航失败（无法访问网站、404 等）"""


class ElementNotFoundError(ChromeAgentError):
    """元素未找到"""


class SessionError(ChromeAgentError):
    """登录/Cookie 持久化错误"""


class LLMError(ChromeAgentError):
    """LLM 调用错误"""


class LLMTimeoutError(LLMError):
    """LLM 调用超时"""


class ToolError(ChromeAgentError):
    """工具执行错误"""


class ToolNotFoundError(ToolError):
    """请求的工具不存在"""


class ToolTimeoutError(ToolError):
    """工具执行超时"""


__all__ = [
    "ChromeAgentError",
    "ConfigError",
    "CDPError",
    "CDPConnectionError",
    "BrowserLaunchError",
    "NavigationError",
    "ElementNotFoundError",
    "SessionError",
    "LLMError",
    "LLMTimeoutError",
    "ToolError",
    "ToolNotFoundError",
    "ToolTimeoutError",
]
