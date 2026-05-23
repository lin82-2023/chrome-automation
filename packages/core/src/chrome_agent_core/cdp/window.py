"""窗口管理：位置、大小、最大化、最小化"""
from ._engine import (
    get_window_bounds,
    maximize_window,
    minimize_window,
    restore_window,
    set_window_bounds,
    set_window_position,
    set_window_size,
)

__all__ = [
    "get_window_bounds",
    "set_window_bounds",
    "minimize_window",
    "maximize_window",
    "restore_window",
    "set_window_position",
    "set_window_size",
]
