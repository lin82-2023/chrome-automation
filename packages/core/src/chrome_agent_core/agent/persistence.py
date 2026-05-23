#!/usr/bin/env python3
"""
Session - 会话持久化（JSONL格式）

每条记录一行，方便追加
"""
import json
import time
from pathlib import Path

from .message import Message, Session


class ChatSessionStore:
    """对话会话存储（JSONL 格式持久化）

    与 chrome_agent_core.session.SessionManager（浏览器登录持久化）区别：
    - ChatSessionStore: 保存 LLM 对话历史到磁盘
    - SessionManager: 保存浏览器 cookie / localStorage
    """

    def __init__(self, session_dir: Path = None):
        if session_dir is None:
            from ..config import get_config
            config = get_config()
            session_dir = config.session_dir

        self.session_dir = Path(session_dir).expanduser()
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: Session) -> Path:
        """
        保存会话到JSONL文件

        每条消息一行，方便追加
        """
        session_path = self.session_dir / f"{session.id}.jsonl"

        # 追加会话元数据（如果文件不存在）
        if not session_path.exists():
            meta = {
                "type": "session",
                "id": session.id,
                "cwd": session.cwd,
                "created_at": session.created_at,
                "parent_id": session.parent_id
            }
            with open(session_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")

        # 追加消息
        with open(session_path, "a", encoding="utf-8") as f:
            for msg in session.messages[-20:]:  # 只保存最近的20条
                entry = {
                    "type": "message",
                    "id": f"{session.id}_{int(time.time()*1000)}",
                    "parent_id": session.id,
                    "timestamp": msg.timestamp,
                    "role": msg.role,
                    "content": msg.content
                }
                if msg.tool_call_id:
                    entry["tool_call_id"] = msg.tool_call_id
                if msg.tool_name:
                    entry["tool_name"] = msg.tool_name

                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return session_path

    def load_session(self, session_id: str) -> Session:
        """
        从JSONL文件加载会话
        """
        session_path = self.session_dir / f"{session_id}.jsonl"
        if not session_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        messages = []
        session_meta = None

        with open(session_path, encoding="utf-8") as f:
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
            raise ValueError(f"Invalid session file: {session_path}")

        return Session(
            id=session_meta["id"],
            cwd=session_meta.get("cwd", "."),
            created_at=session_meta.get("created_at", time.time()),
            parent_id=session_meta.get("parent_id"),
            messages=messages
        )

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        sessions = []
        for path in self.session_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline()
                    if first_line:
                        meta = json.loads(first_line.strip())
                        if meta.get("type") == "session":
                            sessions.append({
                                "id": meta.get("id"),
                                "cwd": meta.get("cwd", "."),
                                "created_at": meta.get("created_at"),
                                "parent_id": meta.get("parent_id")
                            })
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("created_at", 0), reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        session_path = self.session_dir / f"{session_id}.jsonl"
        if session_path.exists():
            session_path.unlink()
            return True
        return False

    def fork_session(self, session_id: str, new_session_id: str = None) -> Session:
        """
        创建会话分支
        """
        original = self.load_session(session_id)

        if new_session_id is None:
            import uuid
            new_session_id = uuid.uuid4().hex

        new_session = Session(
            id=new_session_id,
            cwd=original.cwd,
            parent_id=original.id,
            messages=original.messages.copy()
        )

        return new_session
