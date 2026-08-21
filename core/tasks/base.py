from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from ..domain.events import PipelineStage, ProgressEvent
from ..domain.task import PlanResult, TaskSummary


class BaseTask(ABC):
    """摄影任务抽象基类，提供通用任务生命周期骨架。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """任务中文显示名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """任务详细描述"""
        pass

    @abstractmethod
    def stages(self) -> list[PipelineStage]:
        """返回该任务专有的流水线阶段列表"""
        pass

    @abstractmethod
    def plan(self) -> PlanResult:
        """执行预检 (Dry-Run)，不产生实际副作用"""
        pass

    @abstractmethod
    def execute(self, event_callback: Callable[[ProgressEvent], None] | None = None) -> TaskSummary:
        """执行真实流水线任务，实时通过 event_callback 派发进度"""
        pass
