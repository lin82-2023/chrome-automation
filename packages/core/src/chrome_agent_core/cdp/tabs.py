"""Tab 管理：列出 / 切换 / 创建 / 关闭"""
from ._engine import (
    close_extra_tabs,
    close_tab,
    create_tab,
    get_all_tabs,
    get_created_tab_ids,
    switch_tab,
)

__all__ = [
    "get_all_tabs",
    "switch_tab",
    "create_tab",
    "close_tab",
    "close_extra_tabs",
    "get_created_tab_ids",
]
