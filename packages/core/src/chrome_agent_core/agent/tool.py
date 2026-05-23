#!/usr/bin/env python3
"""
Tool Definition - Core abstractions for the tool framework
"""
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolDefinition:
    """
    工具定义 - 描述一个工具的元数据

    Attributes:
        name: 工具名（LLM调用时使用）
        label: UI显示名
        description: 描述（供LLM理解工具用途）
        parameters: TypeBox风格参数schema
        execute: 异步执行函数
    """
    name: str
    label: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    execute: Callable | None = None


@dataclass
class ToolResult:
    """
    工具执行结果

    Attributes:
        success: 是否成功
        content: 返回内容
        details: 额外详情
    """
    success: bool
    content: Any = ""
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'content': self.content,
            'details': self.details
        }


class BaseTool(ABC):
    """
    工具基类

    子类只需定义类属性和实现execute方法
    """
    name: str = ""
    label: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Returns:
            ToolResult: 包含success/content/details
        """
        pass

    def get_definition(self) -> ToolDefinition:
        """
        获取工具定义

        Returns:
            ToolDefinition: 工具的定义信息
        """
        return ToolDefinition(
            name=self.name,
            label=self.label,
            description=self.description,
            parameters=self.parameters,
            execute=self.execute
        )

    async def run(self, **kwargs) -> ToolResult:
        """
        运行工具的便捷方法

        Returns:
            ToolResult: 执行结果
        """
        return await self.execute(**kwargs)
