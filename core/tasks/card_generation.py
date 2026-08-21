from pathlib import Path
from typing import Callable

from ..batch import generate_from_source
from ..domain.events import PipelineStage, ProgressEvent
from ..domain.task import PlanResult, TaskSummary
from ..plan import plan_batch
from ..presentation import get_presentation_scheme, normalize_presentation
from .base import BaseTask


class CardGenerationTask(BaseTask):
    """摄影信息卡与艺术画册生成任务 (CardGenerationTask)。"""

    def __init__(
        self,
        source_dir: str | Path,
        output_dir: str | Path | None = None,
        scheme: str = "scheme1",
        layout: str | None = None,
        compression: str = "none",
        debug: bool = False,
        photo: str | None = None,
    ):
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve() if output_dir else None
        self.scheme_id = scheme
        self.presentation, self.layout = normalize_presentation(scheme, layout)
        self.compression = compression
        self.debug = debug
        self.photo = photo

    @property
    def name(self) -> str:
        return f"摄影卡片生成 ({self.presentation.name})"

    @property
    def description(self) -> str:
        return f"将 {self.source_dir.name} 目录照片渲染为 {self.presentation.scheme_id} 方案 ({self.layout}) 卡片与联系单"

    def stages(self) -> list[PipelineStage]:
        return [
            PipelineStage.SCANNING,
            PipelineStage.EXIF_BATCH,
            PipelineStage.RENDERING,
            PipelineStage.CONTACT_SHEET,
            PipelineStage.MANIFEST,
            PipelineStage.COMPLETE,
        ]

    def plan(self) -> PlanResult:
        """执行环境依赖、EXIF 资产与耗时预检 (Dry-Run)。"""
        return plan_batch(
            source_dir=self.source_dir,
            scheme=self.scheme_id,
            layout=self.layout,
            photo=self.photo,
        )

    def execute(self, event_callback: Callable[[ProgressEvent], None] | None = None) -> TaskSummary:
        """执行完整生成流水线，流式派发进度事件。"""
        result = generate_from_source(
            source_dir=self.source_dir,
            output_dir=self.output_dir,
            scheme=self.scheme_id,
            layout=self.layout,
            compression=self.compression,
            debug=self.debug,
            photo=self.photo,
            event_callback=event_callback,
        )
        return result["summary"]
