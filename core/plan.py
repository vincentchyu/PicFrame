import os
from pathlib import Path
from typing import Any

from .batch import list_photos
from .domain.events import EventLevel, PipelineStage, ProgressEvent
from .domain.task import PlanIssue, PlanResult
from .metadata import fmt_model, run_exif_batch
from .presentation import normalize_presentation
from .renderer import validate_presentation_requirements


def plan_batch(
    source_dir: str | Path,
    scheme: str = "scheme1",
    layout: str | None = None,
    photo: str | None = None,
) -> PlanResult:
    """对批处理任务进行快速预检 (Dry-Run / Plan)，不执行实际图片生成。"""
    presentation, layout = normalize_presentation(scheme, layout)
    source_path = Path(source_dir).resolve()

    if not source_path.exists() or not source_path.is_dir():
        return PlanResult(
            total_photos=0,
            ready_count=0,
            estimated_duration_sec=0.0,
            warnings=[
                PlanIssue(
                    photo=None,
                    level="error",
                    reason=f"源文件夹不存在或不是目录: {source_path}",
                    suggestion="请确认输入路径有效",
                )
            ],
        )

    photos = list_photos(source_path)
    if photo:
        target_name = Path(photo).name.lower()
        photos = [p for p in photos if p.name.lower() == target_name or p.stem.lower() == target_name]

    total = len(photos)
    if total == 0:
        return PlanResult(
            total_photos=0,
            ready_count=0,
            estimated_duration_sec=0.0,
            warnings=[
                PlanIssue(
                    photo=None,
                    level="warning",
                    reason=f"目录中未找到支持的图像文件: {source_path}",
                    suggestion="支持的格式包括: .jpg, .jpeg, .png, .tif, .tiff",
                )
            ],
        )

    warnings: list[PlanIssue] = []
    missing_assets: list[str] = []

    # 1. 验证方案基础依赖要求
    try:
        validate_presentation_requirements(presentation)
    except Exception as exc:
        warnings.append(
            PlanIssue(
                photo=None,
                level="error",
                reason=f"方案依赖检查未通过: {exc}",
                suggestion="请检查相关环境依赖",
            )
        )

    # 2. 采样/批量读取 EXIF 并进行机身/镜头/GPS 分析
    exif_map = run_exif_batch(photos)
    gps_count = 0
    camera_models = set()
    lens_models = set()

    for p in photos:
        exif = exif_map.get(p.resolve(), {})
        cam = fmt_model(exif)
        lens = (exif.get("LensModel") or exif.get("LensID") or exif.get("Lens") or "").strip()
        if cam:
            camera_models.add(cam)
        if lens:
            lens_models.add(lens)
        if exif.get("GPSLatitude") or exif.get("GPSPosition"):
            gps_count += 1

    # 3. 针对不同方案预估耗时与资产检查
    # Scheme 1/2: ~0.15s/张; Scheme 3: ~0.35s/张; Scheme 4: ~5.0s/张
    scheme_speeds = {
        "scheme1": 0.15,
        "scheme2": 0.12,
        "scheme3": 0.35,
        "scheme4": 6.5,
    }
    unit_time = scheme_speeds.get(presentation.scheme_id, 0.2)
    # 若多线程并发（非 scheme4），耗时按 CPU 核心并发折算
    if presentation.scheme_id != "scheme4" and total > 1:
        workers = min(8, (os.cpu_count() or 1) + 4)
        estimated_duration = (total * unit_time) / (workers * 0.75) + 0.3
    else:
        estimated_duration = total * unit_time

    details: dict[str, Any] = {
        "scheme": presentation.scheme_id,
        "layout": layout,
        "gps_coverage": f"{gps_count}/{total}",
        "detected_cameras": list(camera_models),
        "detected_lenses": list(lens_models),
    }

    return PlanResult(
        total_photos=total,
        ready_count=total,
        estimated_duration_sec=round(estimated_duration, 2),
        warnings=warnings,
        missing_assets=missing_assets,
        details=details,
    )
