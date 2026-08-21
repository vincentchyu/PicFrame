from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class EventLevel(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARN = "warn"
    ERROR = "error"


class PipelineStage(StrEnum):
    SCANNING = "扫描照片"
    PRECHECK = "环境与依赖预检"
    EXIF_BATCH = "批量解析EXIF"
    RENDERING = "生成摄影卡片"
    COMPRESSION = "格式转换与压缩"
    CONTACT_SHEET = "生成联系单"
    MANIFEST = "生成任务清单"
    COMPLETE = "任务完成"


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: PipelineStage
    level: EventLevel
    message: str
    step_tag: str = ""
    current_index: int = 0
    total_items: int = 0
    photo_path: Path | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
