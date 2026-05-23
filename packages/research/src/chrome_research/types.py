"""调研数据结构定义"""
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class SubTask:
    """单个网站调研子任务"""
    id: str
    description: str
    website: str
    url: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2
    fallback_url: str | None = None
    fallback_website: str | None = None


@dataclass
class ResearchPlan:
    """整体调研计划"""
    goal: str
    sub_tasks: list[SubTask] = field(default_factory=list)
    current_step: int = 0
    max_parallel: int = 1  # 浏览器单实例限制，保持顺序执行
    status: TaskStatus = TaskStatus.PENDING
