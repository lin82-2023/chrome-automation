#!/usr/bin/env python3
"""
Message - 消息和会话数据模型
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def uuid4_hex() -> str:
    """生成UUID字符串"""
    return uuid.uuid4().hex


@dataclass
class Message:
    """消息基类"""
    role: str           # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_call_id: str | None = None
    tool_name: str | None = None
    name: str | None = None
    tool_calls: list[dict] | None = None  # For assistant messages with tool calls
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_call_id=d.get("tool_call_id"),
            tool_name=d.get("tool_name"),
            name=d.get("name"),
            timestamp=d.get("timestamp", time.time())
        )


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments
        }


@dataclass
class Session:
    """
    会话

    支持分支、会话持久化
    """
    id: str = field(default_factory=uuid4_hex)
    cwd: str = "."
    created_at: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    parent_id: str | None = None  # 用于分支

    def add_message(self, msg: Message):
        """添加消息"""
        self.messages.append(msg)

    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str, tool_calls: list[dict] = None):
        """添加助手消息"""
        self.messages.append(Message(role="assistant", content=content, tool_calls=tool_calls))

    def add_tool_message(self, tool_call_id: str, content: str, tool_name: str = None):
        """添加工具结果消息"""
        self.messages.append(Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name
        ))

    def add_system_message(self, content: str):
        """添加系统消息"""
        self.messages.append(Message(role="system", content=content))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cwd": self.cwd,
            "created_at": self.created_at,
            "parent_id": self.parent_id,
            "messages": [m.to_dict() for m in self.messages]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        messages = [Message.from_dict(m) for m in d.get("messages", [])]
        return cls(
            id=d["id"],
            cwd=d.get("cwd", "."),
            created_at=d.get("created_at", time.time()),
            parent_id=d.get("parent_id"),
            messages=messages
        )

    def to_messages_for_llm(self) -> list[dict[str, Any]]:
        """转换为LLM需要的消息格式"""
        result = []
        for msg in self.messages:
            if msg.role == "system":
                result.append({"role": "system", "content": msg.content})
            elif msg.role == "user":
                result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                item = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    item["tool_calls"] = msg.tool_calls
                result.append(item)
            elif msg.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content
                })
        return result

    def fork(self) -> "Session":
        """创建分支"""
        new_session = Session(
            id=uuid4_hex(),
            cwd=self.cwd,
            parent_id=self.id
        )
        # 复制消息（浅拷贝）
        new_session.messages = self.messages.copy()
        return new_session


def create_session(cwd: str = ".") -> Session:
    """创建新会话"""
    return Session(cwd=cwd)
