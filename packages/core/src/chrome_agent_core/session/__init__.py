"""Session 持久化与登录管理

提供：
- SessionManager: cookie/localStorage 持久化
- 登录状态检测：detect_login_state、need_manual_login
- 等待手动登录：wait_for_manual_login
- 全局 session 操作：save_session / load_session / list_sessions / delete_session
- Cookie 工具：save_cookies / load_cookies
"""
from ..cdp._engine import (
    SessionManager,
    delete_session,
    detect_login_state,
    list_sessions,
    load_cookies,
    load_session,
    need_manual_login,
    save_cookies,
    save_session,
    wait_for_manual_login,
)

__all__ = [
    "SessionManager",
    "detect_login_state",
    "wait_for_manual_login",
    "need_manual_login",
    "save_session",
    "load_session",
    "list_sessions",
    "delete_session",
    "save_cookies",
    "load_cookies",
]
