"""ChatSessionStore（对话持久化）单元测试"""
import pytest
from chrome_agent_core.agent import (
    ChatSessionStore,
    Message,
    create_session,
)


def test_save_and_load_roundtrip(tmp_path):
    store = ChatSessionStore(session_dir=tmp_path)
    session = create_session(cwd="/tmp")
    session.messages.append(Message(role="user", content="hello"))
    session.messages.append(Message(role="assistant", content="hi"))

    path = store.save_session(session)
    assert path.exists()

    loaded = store.load_session(session.id)
    assert loaded.id == session.id
    assert len(loaded.messages) == 2
    assert loaded.messages[0].role == "user"
    assert loaded.messages[0].content == "hello"


def test_list_sessions(tmp_path):
    store = ChatSessionStore(session_dir=tmp_path)
    s1 = create_session()
    s1.messages.append(Message(role="user", content="x"))
    s2 = create_session()
    s2.messages.append(Message(role="user", content="y"))
    store.save_session(s1)
    store.save_session(s2)

    sessions = store.list_sessions()
    assert len(sessions) == 2
    assert {s["id"] for s in sessions} == {s1.id, s2.id}


def test_delete_session(tmp_path):
    store = ChatSessionStore(session_dir=tmp_path)
    s = create_session()
    s.messages.append(Message(role="user", content="x"))
    store.save_session(s)
    assert store.delete_session(s.id) is True
    assert store.delete_session(s.id) is False


def test_load_missing_session(tmp_path):
    store = ChatSessionStore(session_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load_session("no-such-id")
