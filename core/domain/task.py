from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from .events import PipelineStage, ProgressEvent


@dataclass
class PlanIssue:
    photo: Path | None
    level: str  # "info" | "warning" | "error"
    reason: str
    suggestion: str = ""


@dataclass
class PlanResult:
    total_photos: int
    ready_count: int
    estimated_duration_sec: float
    warnings: list[PlanIssue] = field(default_factory=list)
    missing_assets: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSummary:
    total: int
    success: int
    failed: int
    warnings: list[PlanIssue] = field(default_factory=list)
    output_dir: Path | None = None
    elapsed_seconds: float = 0.0
    contact_sheet: Path | None = None
    manifest_path: Path | None = None
    report_path: Path | None = None


@runtime_checkable
class Task(Protocol):
    """摄影处理任务统一通用接口 (遵循 Clean Architecture & PhotoTools Task 设计)"""

    @property
    def name(self) -> str:
        """任务中文名称"""
        ...

    @property
    def description(self) -> str:
        """任务详细描述"""
        ...

    def stages(self) -> list[PipelineStage]:
        """返回该任务专有的流水线阶段列表"""
        ...

    def plan(self) -> PlanResult:
        """执行预检（Dry-Run），评估依赖、耗时与潜在告警，不产生实际写入"""
        ...

    def execute(self, event_callback: Callable[[ProgressEvent], None] | None = None) -> TaskSummary:
        """执行真实流水线，实时通过 event_callback 发送结构化进度事件并返回最终结算指标"""
        ...

