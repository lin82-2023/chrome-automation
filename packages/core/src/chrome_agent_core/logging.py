"""chrome-agent-core 日志体系

提供统一的日志配置入口。所有模块通过 ``logging.getLogger(__name__)``
获取 logger，由用户在程序启动时调用 ``setup_logging()`` 设置全局格式与级别。
"""
from __future__ import annotations

import logging
import os
import sys

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATEFMT = "%H:%M:%S"


def setup_logging(
    level: str | None = None,
    fmt: str = DEFAULT_FORMAT,
    datefmt: str = DEFAULT_DATEFMT,
    stream=None,
) -> None:
    """配置全局日志

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR），为 None 时读取
            ``CHROME_AGENT_LOG_LEVEL`` 环境变量，默认 INFO
        fmt:    日志格式字符串
        datefmt: 时间格式字符串
        stream: 日志输出流，默认 stderr
    """
    if level is None:
        level = os.environ.get("CHROME_AGENT_LOG_LEVEL", "INFO")
    level_value = getattr(logging, str(level).upper(), logging.INFO)

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    # 清掉重复 handler，避免多次调用累积
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level_value)


def get_logger(name: str) -> logging.Logger:
    """便捷工厂：``logging.getLogger(name)`` 的薄包装"""
    return logging.getLogger(name)


__all__ = ["setup_logging", "get_logger", "DEFAULT_FORMAT", "DEFAULT_DATEFMT"]
