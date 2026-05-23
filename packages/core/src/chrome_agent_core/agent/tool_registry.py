#!/usr/bin/env python3
"""
Tool Registry - Global tool registration and lookup
"""
from threading import Lock

from .tool import ToolDefinition


class ToolRegistry:
    """
    全局工具注册表

    所有工具通过此类注册和查找
    """
    _tools: dict[str, ToolDefinition] = {}
    _lock = Lock()

    @classmethod
    def register(cls, tool: ToolDefinition):
        """
        注册一个工具

        Args:
            tool: ToolDefinition实例
        """
        with cls._lock:
            cls._tools[tool.name] = tool

    @classmethod
    def register_tool(cls, name: str, label: str, description: str,
                      execute: callable, parameters: dict = None):
        """
        直接注册一个工具函数

        Args:
            name: 工具名
            label: 显示名
            description: 描述
            execute: 执行函数
            parameters: 参数定义
        """
        definition = ToolDefinition(
            name=name,
            label=label,
            description=description,
            parameters=parameters or {},
            execute=execute
        )
        cls.register(definition)

    @classmethod
    def get(cls, name: str) -> ToolDefinition | None:
        """
        根据名字获取工具

        Args:
            name: 工具名

        Returns:
            ToolDefinition或None
        """
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list[ToolDefinition]:
        """
        列出所有已注册工具

        Returns:
            工具定义列表
        """
        return list(cls._tools.values())

    @classmethod
    def list_tool_names(cls) -> list[str]:
        """
        列出所有工具名

        Returns:
            工具名列表
        """
        return list(cls._tools.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        注销一个工具

        Args:
            name: 工具名

        Returns:
            是否成功注销
        """
        with cls._lock:
            if name in cls._tools:
                del cls._tools[name]
                return True
            return False

    @classmethod
    def clear(cls):
        """清空所有工具"""
        with cls._lock:
            cls._tools.clear()

    @classmethod
    def count(cls) -> int:
        """获取工具数量"""
        return len(cls._tools)


def register_tool(name: str, label: str, description: str,
                  parameters: dict = None):
    """
    装饰器：注册一个工具

    Usage:
        @register_tool("my_tool", "My Tool", "Does something")
        async def my_tool(**kwargs):
            return ToolResult(success=True, content="done")
    """
    def decorator(func):
        ToolRegistry.register_tool(
            name=name,
            label=label,
            description=description,
            execute=func,
            parameters=parameters
        )
        return func
    return decorator
