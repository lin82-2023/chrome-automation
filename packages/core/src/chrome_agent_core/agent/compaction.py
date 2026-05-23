#!/usr/bin/env python3
"""
Compaction - 上下文压缩

当会话过长时，压缩历史消息以节省token
"""
from typing import Any

from .message import Message, Session


async def compact_if_needed(session: Session, max_tokens: int = 6000) -> bool:
    """
    检查是否需要压缩上下文

    Args:
        session: 会话
        max_tokens: token阈值（简单估算：1 token ≈ 2 字符）

    Returns:
        是否进行了压缩
    """
    # 估算当前消息总长度
    total_chars = 0
    for msg in session.messages:
        total_chars += len(msg.content)

    # 简单token估算
    estimated_tokens = total_chars // 2

    if estimated_tokens < max_tokens:
        return False

    # 需要压缩：保留system消息 + 最近消息 + 摘要中间部分
    return await _compact_session(session)


async def _compact_session(session: Session) -> bool:
    """
    执行压缩

    策略：
    1. 保留system消息
    2. 保留最近10条消息
    3. 对中间消息生成摘要
    """
    system_msgs = [msg for msg in session.messages if msg.role == "system"]
    other_msgs = [msg for msg in session.messages if msg.role != "system"]

    if len(other_msgs) <= 10:
        return False

    # 保留最近10条
    recent = other_msgs[-10:]
    middle = other_msgs[:-10]

    # 生成摘要
    summary_content = _summarize_messages(middle)

    # 构建新消息列表
    new_messages = system_msgs + [
        Message(role="system", content=f"[历史摘要] 之前的{len(middle)}条消息已压缩: {summary_content}")
    ] + recent

    session.messages = new_messages
    return True


def _summarize_messages(messages: list[Message]) -> str:
    """
    生成消息摘要

    简单实现：提取关键信息
    """
    if not messages:
        return "无"

    # 统计工具调用
    tool_calls = []
    for msg in messages:
        if msg.tool_name:
            tool_calls.append(msg.tool_name)

    if tool_calls:
        unique_tools = list(set(tool_calls))
        return f"执行了工具: {', '.join(unique_tools)}"

    return f"共{len(messages)}条消息"


def compact_history(messages: list[dict[str, Any]], max_messages: int = 20) -> list[dict[str, Any]]:
    """
    压缩历史消息（同步版本，用于非async场景）

    Args:
        messages: 消息列表
        max_messages: 保留的最大消息数

    Returns:
        压缩后的消息列表
    """
    if len(messages) <= max_messages:
        return messages

    # 保留前几条（通常包含system）
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    if len(other_msgs) <= max_messages:
        return messages

    # 保留最近的消息
    recent = other_msgs[-max_messages:]
    middle_count = len(other_msgs) - max_messages

    # 生成摘要消息
    summary = {
        "role": "system",
        "content": f"[{middle_count}条历史消息已压缩]"
    }

    return system_msgs + [summary] + recent
