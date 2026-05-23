"""CDP 连接与底层执行

提供与 Chrome DevTools Protocol 的连接和 JS 执行能力。
"""
from ._engine import (
    cdp_execute,
    get_cdp_connection,
)

__all__ = [
    "get_cdp_connection",
    "cdp_execute",
]
