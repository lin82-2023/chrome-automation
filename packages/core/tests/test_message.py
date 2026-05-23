"""Message / Session 数据模型测试"""
from chrome_agent_core import Session, create_session


def test_create_session():
    s = create_session(cwd="/tmp")
    assert s.cwd == "/tmp"
    assert s.id and len(s.id) > 0
    assert s.messages == []


def test_session_message_helpers():
    s = create_session()
    s.add_user_message("hello")
    s.add_assistant_message("hi", tool_calls=[{"id": "c1", "name": "n", "arguments": {}}])
    s.add_tool_message(tool_call_id="c1", content="ok", tool_name="n")
    s.add_system_message("you are helpful")
    assert [m.role for m in s.messages] == ["user", "assistant", "tool", "system"]


def test_to_messages_for_llm():
    s = create_session()
    s.add_user_message("hi")
    s.add_assistant_message("hello")
    out = s.to_messages_for_llm()
    assert out[0] == {"role": "user", "content": "hi"}
    assert out[1] == {"role": "assistant", "content": "hello"}


def test_session_roundtrip_dict():
    s = create_session(cwd="/x")
    s.add_user_message("hello")
    d = s.to_dict()
    s2 = Session.from_dict(d)
    assert s2.id == s.id
    assert s2.messages[0].content == "hello"


def test_session_fork():
    s = create_session()
    s.add_user_message("x")
    forked = s.fork()
    assert forked.parent_id == s.id
    assert forked.id != s.id
    assert len(forked.messages) == len(s.messages)
