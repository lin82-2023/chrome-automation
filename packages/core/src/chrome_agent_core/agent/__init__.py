"""Agent 框架核心

提供：
- ToolDefinition / ToolResult / BaseTool: 工具定义协议
- ToolRegistry: 工具注册表
- Message / Session / ToolCall: 对话数据结构
- ChatSessionStore: 对话会话持久化
- AgentSession: 通用 function calling 编排循环
- build_system_prompt: 系统提示词构建
- compact_if_needed: 长会话压缩
"""
from .compaction import compact_if_needed
from .message import Message, Session, ToolCall, create_session
from .persistence import ChatSessionStore
from .session import AgentSession
from .system_prompt import build_system_prompt
from .tool import BaseTool, ToolDefinition, ToolResult
from .tool_registry import ToolRegistry

__all__ = [
    "ToolDefinition",
    "ToolResult",
    "BaseTool",
    "ToolRegistry",
    "Message",
    "Session",
    "ToolCall",
    "create_session",
    "build_system_prompt",
    "compact_if_needed",
    "ChatSessionStore",
    "AgentSession",
]
