"""Stealth 防检测工具 - 模拟真人操作行为

包括：
- 随机延迟（页面加载、操作前后）
- 鼠标加速曲线
- 模拟人类点击/输入/滚动节奏
- Stealth 配置档（low / medium / high）
- 浏览器指纹防检测（apply_stealth_fingerprint 在 cdp._engine 中）
"""
# 浏览器指纹相关从 CDP 引擎重新导出
from ..cdp._engine import (
    apply_stealth_fingerprint,
    get_human_user_agent,
)
from ._impl import (
    STEALTH_CONFIGS,
    after_action_delay,
    apply_stealth,
    before_action_delay,
    human_click,
    human_scroll,
    human_typing,
    page_load_delay,
    random_delay,
    random_mouse_move,
    random_scroll_page,
)

__all__ = [
    "random_delay",
    "random_mouse_move",
    "human_click",
    "human_typing",
    "human_scroll",
    "random_scroll_page",
    "page_load_delay",
    "before_action_delay",
    "after_action_delay",
    "apply_stealth",
    "STEALTH_CONFIGS",
    "apply_stealth_fingerprint",
    "get_human_user_agent",
]
