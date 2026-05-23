"""异步包装工具：把同步 CDP 调用转为 async"""
from ._engine import (
    exec_async,
    exec_async_with_callback,
)

__all__ = [
    "exec_async",
    "exec_async_with_callback",
]
