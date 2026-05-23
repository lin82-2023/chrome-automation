"""chrome-agent-core - Chrome 浏览器自动化与 AI Agent SDK

模块组织：
- cdp:      CDP 底层（连接、导航、元素、输入、Tab、窗口、事件）
- session:  浏览器登录/Cookie 持久化
- stealth:  反指纹 / 反检测
- browser:  Chrome 启动与生命周期
- llm:      LLM Provider（百炼）
- tools:    内置工具集（浏览器 + Session）
- agent:    Agent 框架（工具协议、注册表、消息、AgentSession）
- config:   配置加载

快捷导入示例：
    from chrome_agent_core import AgentSession, BailianLLM, ToolRegistry
    from chrome_agent_core.tools import register_all_tools
    from chrome_agent_core.cdp import cdp_navigate, click_element
    from chrome_agent_core.browser import ensure_chrome
    from chrome_agent_core.session import SessionManager
"""

__version__ = "0.1.0"

from .agent import (
    AgentSession,
    BaseTool,
    ChatSessionStore,
    Message,
    Session,
    ToolCall,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    build_system_prompt,
    compact_if_needed,
    create_session,
)
from .config import get_config, validate_config
from .errors import (
    BrowserLaunchError,
    CDPConnectionError,
    CDPError,
    ChromeAgentError,
    ConfigError,
    ElementNotFoundError,
    LLMError,
    LLMTimeoutError,
    NavigationError,
    SessionError,
    ToolError,
    ToolNotFoundError,
    ToolTimeoutError,
)
from .llm import (
    AnthropicLLM,
    BailianLLM,
    BaseLLM,
    DeepSeekLLM,
    GroqLLM,
    MoonshotLLM,
    OllamaLLM,
    OpenAICompatLLM,
    OpenAILLM,
    OpenRouterLLM,
    ZhipuLLM,
    create_llm,
    list_providers,
)
from .logging import get_logger, setup_logging

__all__ = [
    "__version__",
    # Agent 框架
    "AgentSession",
    "BaseTool",
    "ChatSessionStore",
    "Message",
    "Session",
    "ToolCall",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    "build_system_prompt",
    "compact_if_needed",
    "create_session",
    # LLM
    "BaseLLM",
    "OpenAICompatLLM",
    "BailianLLM",
    "OpenAILLM",
    "AnthropicLLM",
    "DeepSeekLLM",
    "MoonshotLLM",
    "ZhipuLLM",
    "OpenRouterLLM",
    "GroqLLM",
    "OllamaLLM",
    "create_llm",
    "list_providers",
    # 配置
    "get_config",
    "validate_config",
    # 日志
    "setup_logging",
    "get_logger",
    # 错误体系
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
