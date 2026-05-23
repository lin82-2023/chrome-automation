"""页面导航与页面信息"""
from ._engine import (
    async_cdp_navigate,
    async_get_page_info,
    cdp_navigate,
    get_page_info,
)

__all__ = [
    "cdp_navigate",
    "async_cdp_navigate",
    "get_page_info",
    "async_get_page_info",
]
