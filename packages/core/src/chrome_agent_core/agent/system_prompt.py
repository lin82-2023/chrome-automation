#!/usr/bin/env python3
"""
System Prompt - 构建给LLM的系统提示词
"""

from .tool import ToolDefinition

SYSTEM_PROMPT_TEMPLATE = """你是一个专业的浏览器自动化助手。

你的职责：
1. 理解用户的自然语言指令
2. 规划任务步骤
3. 使用工具执行操作
4. 反馈执行结果

可用工具：
{tools_spec}

工作流程：
1. 理解用户想要什么
2. 确定需要的步骤
3. 调用合适的工具（一次只调用一个）
4. 根据结果决定下一步
5. 直到完成用户的需求

重要规则：
- 每个步骤只能调用一个工具
- **不要重复调用已经执行过的工具**
- 当工具返回 success=true 时，表示该操作已完成，不要再次调用相同工具
- 如果工具执行失败（success=false），说明原因并尝试替代方案
- 始终用中文回复用户
- 页面加载需要等待，使用navigate后稍等片刻再操作
- 搜索使用browser_search工具，不需要手动input+click
- 只有在确认上一步操作未成功时才重试相同工具
"""


def build_tools_spec(tools: list[ToolDefinition]) -> str:
    """构建工具列表描述"""
    lines = []
    for t in tools:
        # 基础描述
        desc = f"- **{t.name}**: {t.description}"
        if t.parameters:
            params = []
            for pname, pspec in t.parameters.items():
                required = "（必填）" if pspec.get("required") else "（可选）"
                ptype = pspec.get("type", "string")
                pdesc = pspec.get("description", "")
                params.append(f"  - {pname} {required}: {ptype} - {pdesc}")
            if params:
                desc += "\n" + "\n".join(params)
        lines.append(desc)
    return "\n".join(lines)


def build_system_prompt(tools: list[ToolDefinition]) -> str:
    """构建完整的系统提示词"""
    tools_spec = build_tools_spec(tools)
    return SYSTEM_PROMPT_TEMPLATE.format(tools_spec=tools_spec)


def get_default_system_prompt() -> str:
    """获取默认系统提示词（不含工具）"""
    return """你是一个专业的浏览器自动化助手。

你的职责是帮助用户完成浏览器相关的自动化任务，包括：
- 网页导航和搜索
- 填写表单和点击按钮
- 提取网页信息
- 管理多个标签页

请始终用中文回复用户。"""
