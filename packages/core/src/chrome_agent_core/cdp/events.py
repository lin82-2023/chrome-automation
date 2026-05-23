"""事件 watchdog：health 监控、事件管道、emit_event"""
from ._engine import (
    EventTypes,
    OverflowPolicy,
    browser_operation,
    emit_event,
    emit_failure,
    emit_success,
    get_browser_health,
    get_watchdog_pipe,
    init_watchdog_pipe,
    reset_browser_state,
    set_overflow_policy,
    start_watchdog_monitor,
)

__all__ = [
    "EventTypes",
    "OverflowPolicy",
    "init_watchdog_pipe",
    "get_watchdog_pipe",
    "set_overflow_policy",
    "emit_event",
    "emit_success",
    "emit_failure",
    "get_browser_health",
    "reset_browser_state",
    "start_watchdog_monitor",
    "browser_operation",
]
