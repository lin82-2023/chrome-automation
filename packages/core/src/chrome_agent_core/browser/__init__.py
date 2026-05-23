"""Chrome 浏览器安装检查与启动辅助

提供：
- check_chrome_installed: 是否已安装 Chrome
- ensure_chrome: 检查并提示用户启动调试模式
"""
from ..cdp._engine import (
    check_chrome_installed,
    ensure_chrome,
)

__all__ = [
    "check_chrome_installed",
    "ensure_chrome",
]
