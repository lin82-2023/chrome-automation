#!/usr/bin/env python3
"""
AgentSession - 核心编排层

参考PI-mono的AgentSession设计
负责：LLM调用编排、工具执行循环、会话持久化
"""
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from ..llm.bailian import BailianLLM
from .compaction import compact_if_needed
from .message import Message, Session, create_session
from .system_prompt import build_system_prompt
from .tool import ToolDefinition, ToolResult


class AgentSession:
    """
    核心编排层

    工作流程：
    1. 用户输入 → 添加到消息
    2. 调用LLM → 判断是否需要工具
    3. 如果需要工具 → 执行工具 → 添加结果 → 回到步骤2
    4. 如果不需要工具 → 返回结果给用户
    """

    def __init__(
        self,
        llm: BailianLLM,
        tools: list[ToolDefinition],
        session_id: str = None,
        cwd: str = "."
    ):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.session = create_session(cwd=cwd)
        if session_id:
            self.session.id = session_id

        # 添加系统提示词
        system_prompt = build_system_prompt(tools)
        self.session.add_system_message(system_prompt)

        # 迭代控制
        self.max_iterations = 20
        self.compact_threshold = 6000  # 超过这个token数就压缩

    async def run(self, user_input: str) -> str:
        """
        执行用户指令

        Args:
            user_input: 用户输入

        Returns:
            最终回复文本
        """
        # 添加用户消息
        self.session.add_user_message(user_input)

        # Turn循环
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            # 调用LLM
            messages = self.session.to_messages_for_llm()
            response = await self.llm.chat(
                messages=messages,
                tools=list(self.tools.values())
            )

            # 检查是否有tool_calls
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                # 无工具调用，这是最终回复
                content = response.get("content", "")
                if content:
                    self.session.add_assistant_message(content)
                    return content
                # 空回复，继续循环
                continue

            # 关键修复: 先添加包含 tool_calls 的 assistant 消息
            # 这样 tool 结果才能正确跟在 assistant 之后
            self.session.add_assistant_message(
                content=response.get("content", ""),
                tool_calls=tool_calls
            )

            # 执行工具
            tool_results = []
            for tool_call in tool_calls:
                name = tool_call.get("name", "")
                args = tool_call.get("arguments", {})
                tool_id = tool_call.get("id", f"call_{int(time.time()*1000)}")

                # 查找并执行工具
                tool = self.tools.get(name)
                if not tool:
                    result = ToolResult(
                        success=False,
                        content=f"错误：未知工具 '{name}'"
                    )
                else:
                    try:
                        result = await tool.execute(**args)
                    except Exception as e:
                        result = ToolResult(
                            success=False,
                            content=f"工具执行错误: {str(e)}"
                        )

                tool_results.append({
                    'tool_call_id': tool_id,
                    'tool_name': name,
                    'result': result
                })

            # 添加所有 tool 结果 (紧跟在 assistant 消息之后)
            for r in tool_results:
                result_text = json.dumps(r['result'].to_dict(), ensure_ascii=False)
                self.session.add_tool_message(r['tool_call_id'], result_text, tool_name=r['tool_name'])

            # 检查是否需要压缩上下文（暂时禁用）
            # await compact_if_needed(self.session, self.compact_threshold)

            # 智能判断: 是否继续调用 LLM
            # 如果只调用了一个工具且成功,检查是否需要继续
            if len(tool_results) == 1 and tool_results[0]['result'].success:
                tool_name = tool_results[0]['tool_name']

                # 对于导航、点击、输入等单次操作,工具成功后应该让 LLM 给出最终回复
                # 而不是继续循环
                single_action_tools = {'navigate', 'click', 'input', 'submit', 'get_page_info',
                                      'list_tabs', 'switch_tab', 'new_tab', 'close_tab',
                                      'browser_search', 'get_elements', 'find_element', 'eval_js'}

                if tool_name in single_action_tools:
                    # 直接返回工具结果,避免百炼 API 的 500 错误
                    # 注意: 对于多步骤任务,用户需要分多次调用
                    result = tool_results[0]['result']
                    final_content = f"{result.content}"
                    if result.details:
                        for key, value in result.details.items():
                            if value:
                                final_content += f"\n{key}: {value}"
                    return final_content

            # 继续循环，让 LLM 根据工具结果决定下一步
            # 注意: 不再添加额外的 assistant 消息,保持正确的消息序列
            continue

        # 超过最大迭代次数
        return "抱歉，任务执行时间过长，请重试。"

    async def run_stream(self, user_input: str) -> AsyncIterator[str]:
        """
        流式执行

        Yields:
            各个阶段的输出
        """
        yield f"[用户] {user_input}\n\n"

        self.session.add_user_message(user_input)
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            yield f"[思考] 第 {iteration} 轮...\n"

            messages = self.session.to_messages_for_llm()
            response = await self.llm.chat(
                messages=messages,
                tools=list(self.tools.values())
            )

            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                content = response.get("content", "")
                self.session.add_assistant_message(content)
                yield f"[助手] {content}\n"
                return

            # 关键修复: 先添加包含 tool_calls 的 assistant 消息
            self.session.add_assistant_message(
                content=response.get("content", ""),
                tool_calls=tool_calls
            )

            for tool_call in tool_calls:
                name = tool_call.get("name", "")
                args = tool_call.get("arguments", {})
                tool_id = tool_call.get("id", f"call_{int(time.time()*1000)}")

                yield f"[工具] {name}({args})\n"

                tool = self.tools.get(name)
                if not tool:
                    result = ToolResult(success=False, content=f"未知工具: {name}")
                else:
                    try:
                        result = await tool.execute(**args)
                    except Exception as e:
                        result = ToolResult(success=False, content=str(e))

                yield f"[结果] {result.content}\n"

                result_text = json.dumps(result.to_dict(), ensure_ascii=False)
                self.session.add_tool_message(tool_id, result_text, tool_name=name)

            await compact_if_needed(self.session, self.compact_threshold)

        yield "[完成] 任务执行超时\n"

    def save(self, session_dir: Path):
        """
        保存会话到JSONL文件

        每条消息一行，方便追加
        """
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"{self.session.id}.jsonl"

        # 追加会话元数据
        meta = {
            "type": "session",
            "id": self.session.id,
            "cwd": self.session.cwd,
            "created_at": self.session.created_at,
            "parent_id": self.session.parent_id
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")

        # 追加消息
        for msg in self.session.messages:
            entry = {
                "type": "message",
                "id": f"{self.session.id}_{len(self.session.messages)}",
                "parent_id": self.session.id,
                "timestamp": msg.timestamp,
                "role": msg.role,
                "content": msg.content
            }
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_name:
                entry["tool_name"] = msg.tool_name

            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, session_id: str, session_dir: Path, llm: BailianLLM,
             tools: list[ToolDefinition]) -> "AgentSession":
        """从JSONL文件加载会话"""
        path = session_dir / f"{session_id}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        messages = []
        session_meta = None

        with open(path, encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("type") == "session":
                    session_meta = entry
                elif entry.get("type") == "message":
                    messages.append(Message(
                        role=entry["role"],
                        content=entry.get("content", ""),
                        tool_call_id=entry.get("tool_call_id"),
                        tool_name=entry.get("tool_name"),
                        timestamp=entry.get("timestamp", time.time())
                    ))

        if not session_meta:
            raise ValueError(f"Invalid session file: {path}")

        session = Session(
            id=session_meta["id"],
            cwd=session_meta.get("cwd", "."),
            created_at=session_meta.get("created_at", time.time()),
            parent_id=session_meta.get("parent_id"),
            messages=messages
        )

        agent = cls(llm=llm, tools=tools, cwd=session.cwd)
        agent.session = session
        return agent


async def create_agent_session(
    tools: list[ToolDefinition],
    session_id: str = None,
    cwd: str = "."
) -> AgentSession:
    """
    创建Agent会话（便捷函数）

    自动创建LLM客户端
    """
    from .config import get_config
    from .llm import BailianLLM

    config = get_config()
    llm = BailianLLM(api_key=config.api_key, model=config.model)

    return AgentSession(
        llm=llm,
        tools=tools,
        session_id=session_id,
        cwd=cwd
    )
