"""CDP 子模块 - Chrome DevTools Protocol 操作

子模块按职责划分：
- connection: CDP 连接和 cdp_execute
- navigate: 页面导航与 page_info
- elements: DOM 查找
- input: 点击/输入/提交
- tabs: Tab 管理
- window: 窗口控制
- events: 事件 watchdog
- async_helpers: 异步包装工具

所有具体实现位于 _engine.py（暂为单体，后续可继续物理拆分）。
"""
from .async_helpers import exec_async, exec_async_with_callback
from .connection import cdp_execute, get_cdp_connection
from .elements import (
    async_get_elements,
    dump_elements,
    find_element,
    get_elements,
)
from .events import (
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
from .input import (
    async_click_element,
    async_input_text,
    async_submit_form,
    click_element,
    input_text,
    submit_form,
)
from .navigate import (
    async_cdp_navigate,
    async_get_page_info,
    cdp_navigate,
    get_page_info,
)
from .tabs import (
    close_extra_tabs,
    close_tab,
    create_tab,
    get_all_tabs,
    get_created_tab_ids,
    switch_tab,
)
from .window import (
    get_window_bounds,
    maximize_window,
    minimize_window,
    restore_window,
    set_window_bounds,
    set_window_position,
    set_window_size,
)

__all__ = [
    # connection
    "get_cdp_connection", "cdp_execute",
    # navigate
    "cdp_navigate", "async_cdp_navigate", "get_page_info", "async_get_page_info",
    # elements
    "get_elements", "find_element", "async_get_elements", "dump_elements",
    # input
    "click_element", "input_text", "submit_form",
    "async_click_element", "async_input_text", "async_submit_form",
    # tabs
    "get_all_tabs", "switch_tab", "create_tab", "close_tab",
    "close_extra_tabs", "get_created_tab_ids",
    # window
    "get_window_bounds", "set_window_bounds",
    "minimize_window", "maximize_window", "restore_window",
    "set_window_position", "set_window_size",
    # events
    "EventTypes", "OverflowPolicy",
    "init_watchdog_pipe", "get_watchdog_pipe", "set_overflow_policy",
    "emit_event", "emit_success", "emit_failure",
    "get_browser_health", "reset_browser_state", "start_watchdog_monitor",
    "browser_operation",
    # async helpers
    "exec_async", "exec_async_with_callback",
]
