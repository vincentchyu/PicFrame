import concurrent.futures
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import IMAGE_EXTENSIONS
from .domain.events import EventLevel, PipelineStage, ProgressEvent
from .domain.task import PlanIssue, TaskSummary
from .metadata import run_exif_batch
from .output import OutputPolicy
from .presentation import normalize_presentation
from .renderer import validate_presentation_requirements
from .rendering import get_renderer, make_card, make_contact_sheet


def list_photos(source_dir):
    return sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def normalize_layout(layout, scheme="scheme1"):
    _, layout = normalize_presentation(scheme, layout)
    return layout


def _write_manifest(path, presentation, renderer, layout, output_policy, source_dir, result_dir, outputs, contact_sheet, summary=None):
    manifest = {
        "scheme": presentation.scheme_id,
        "renderer": presentation.renderer,
        "renderer_id": renderer.renderer_id,
        "config": presentation.config,
        "resources": presentation.resources,
        "dependencies": list(presentation.dependencies),
        "layout": layout,
        "compression": output_policy.compression,
        "format": output_policy.format,
        "source_directory": str(source_dir),
        "output_directory": str(result_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_photos": len(outputs),
        "outputs": [str(path) for path in outputs],
        "contact_sheet": str(contact_sheet) if contact_sheet else None,
    }
    if summary:
        manifest["summary"] = {
            "success": summary.success,
            "failed": summary.failed,
            "elapsed_seconds": summary.elapsed_seconds,
            "warnings_count": len(summary.warnings),
        }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_generation_report(path: Path, summary: TaskSummary, presentation, layout: str, outputs: list[Path]) -> Path:
    lines = [
        f"# 📷 PicFrame 生成结算报告",
        f"",
        f"- **渲染方案**: `{presentation.scheme_id}` ({presentation.name})",
        f"- **应用布局**: `{layout}`",
        f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **总耗时**: {summary.elapsed_seconds:.2f} 秒",
        f"- **成功数量**: {summary.success} / {summary.total}",
        f"- **失败数量**: {summary.failed}",
        f"",
        f"## 🖼️ 产物清单",
        f"",
    ]
    if summary.contact_sheet:
        lines.append(f"- **总览联系单**: `{summary.contact_sheet.name}`")
    lines.append(f"- **卡片列表** ({len(outputs)} 张):")
    for out in outputs:
        lines.append(f"  - `{out.name}`")

    if summary.warnings:
        lines.extend([
            f"",
            f"## ⚠️ 告警与优化建议 ({len(summary.warnings)} 条)",
            f"",
        ])
        for w in summary.warnings:
            target = f"[{w.photo.name}] " if w.photo else ""
            lines.append(f"- **{target}{w.reason}**")
            if w.suggestion:
                lines.append(f"  - *建议*: {w.suggestion}")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def generate_batch(
    source_dir,
    result_dir,
    asset_dir,
    progress_callback=None,
    layout=None,
    scheme="scheme1",
    compression="none",
    legacy=False,
    debug=False,
    photo=None,
    event_callback: Callable[[ProgressEvent], None] | None = None,
):
    start_time = time.time()
    presentation, layout = normalize_presentation(scheme, layout)
    validate_presentation_requirements(presentation)
    renderer = get_renderer(presentation)
    output_policy = OutputPolicy(compression)
    source_dir = Path(source_dir).resolve()
    result_dir = Path(result_dir).resolve()
    asset_dir = Path(asset_dir).resolve()

    # 构造事件派发管道
    def dispatch_event(event: ProgressEvent):
        if event_callback:
            event_callback(event)
        if progress_callback:
            # 兼容老版回调格式 ("action", current, total, photo, result_dir)
            action_map = {
                PipelineStage.SCANNING: "scanning",
                PipelineStage.EXIF_BATCH: "exif_batch",
                PipelineStage.RENDERING: "generated" if event.level == EventLevel.SUCCESS else "processing",
                PipelineStage.CONTACT_SHEET: "contact_sheet",
                PipelineStage.COMPLETE: "done",
            }
            act = action_map.get(event.stage, "processing")
            progress_callback(act, event.current_index, event.total_items, event.photo_path, result_dir)

    if not source_dir.exists():
        raise FileNotFoundError(f"Missing source folder: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a folder: {source_dir}")

    dispatch_event(
        ProgressEvent(
            stage=PipelineStage.SCANNING,
            level=EventLevel.INFO,
            message=f"正在扫描源目录: {source_dir.name}",
        )
    )

    photos = list_photos(source_dir)
    if not photos:
        raise ValueError(f"No photos found in {source_dir}")

    if photo:
        target_name = Path(photo).name.lower()
        photos = [p for p in photos if p.name.lower() == target_name or p.stem.lower() == target_name]
        if not photos:
            raise ValueError(f"Specified photo '{photo}' not found in {source_dir}")

    result_dir.mkdir(parents=True, exist_ok=True)
    total = len(photos)

    # 1. 批量提取 EXIF 阶段
    dispatch_event(
        ProgressEvent(
            stage=PipelineStage.EXIF_BATCH,
            level=EventLevel.INFO,
            message=f"正在批量解析 {total} 张照片 EXIF 元数据...",
            total_items=total,
        )
    )
    exif_map = run_exif_batch(photos)

    outputs = []
    warnings: list[PlanIssue] = []
    is_sequential = (presentation.scheme_id == "scheme4") or debug

    # 内部单图事件桥接器
    def step_reporter(event: ProgressEvent):
        dispatch_event(event)

    dispatch_event(
        ProgressEvent(
            stage=PipelineStage.RENDERING,
            level=EventLevel.INFO,
            message=f"启动卡片渲染管线 (方案: {presentation.scheme_id}, 模式: {'串行' if is_sequential else '多并发'})",
            total_items=total,
        )
    )

    if total > 1 and not is_sequential:
        max_workers = min(8, (os.cpu_count() or 1) + 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(
                    make_card,
                    photo_path=p,
                    result_dir=result_dir,
                    renderer=renderer,
                    presentation=presentation,
                    layout=layout,
                    output_policy=output_policy,
                    asset_dir=asset_dir,
                    exif=exif_map.get(p.resolve()),
                    debug=debug,
                    step_callback=step_reporter,
                ): (idx, p)
                for idx, p in enumerate(photos, start=1)
            }
            indexed_outputs = []
            for future in concurrent.futures.as_completed(future_to_item):
                idx, p = future_to_item[future]
                try:
                    out_path = future.result()
                    indexed_outputs.append((idx, out_path))
                    dispatch_event(
                        ProgressEvent(
                            stage=PipelineStage.RENDERING,
                            level=EventLevel.SUCCESS,
                            message=f"卡片渲染完成: {p.name}",
                            step_tag="[Done]",
                            current_index=len(indexed_outputs),
                            total_items=total,
                            photo_path=p,
                        )
                    )
                except Exception as exc:
                    warnings.append(
                        PlanIssue(
                            photo=p,
                            level="error",
                            reason=f"渲染失败: {exc}",
                            suggestion="请检查图片格式或 EXIF 完整度",
                        )
                    )
                    dispatch_event(
                        ProgressEvent(
                            stage=PipelineStage.RENDERING,
                            level=EventLevel.ERROR,
                            message=f"渲染异常 ({p.name}): {exc}",
                            step_tag="[Error]",
                            current_index=len(indexed_outputs) + 1,
                            total_items=total,
                            photo_path=p,
                        )
                    )
        indexed_outputs.sort(key=lambda item: item[0])
        outputs = [out for _, out in indexed_outputs]
    else:
        # 串行执行
        for idx, p in enumerate(photos, start=1):
            dispatch_event(
                ProgressEvent(
                    stage=PipelineStage.RENDERING,
                    level=EventLevel.INFO,
                    message=f"正在处理 ({idx}/{total}): {p.name}",
                    step_tag="[Start]",
                    current_index=idx,
                    total_items=total,
                    photo_path=p,
                )
            )
            try:
                out_path = make_card(
                    photo_path=p,
                    result_dir=result_dir,
                    renderer=renderer,
                    presentation=presentation,
                    layout=layout,
                    output_policy=output_policy,
                    asset_dir=asset_dir,
                    exif=exif_map.get(p.resolve()),
                    debug=debug,
                    step_callback=step_reporter,
                )
                outputs.append(out_path)
                dispatch_event(
                    ProgressEvent(
                        stage=PipelineStage.RENDERING,
                        level=EventLevel.SUCCESS,
                        message=f"卡片生成成功: {p.name}",
                        step_tag="[Done]",
                        current_index=idx,
                        total_items=total,
                        photo_path=p,
                    )
                )
            except Exception as exc:
                warnings.append(
                    PlanIssue(
                        photo=p,
                        level="error",
                        reason=f"生成失败: {exc}",
                        suggestion="请检查该图片是否损坏",
                    )
                )
                dispatch_event(
                    ProgressEvent(
                        stage=PipelineStage.RENDERING,
                        level=EventLevel.ERROR,
                        message=f"生成异常 ({p.name}): {exc}",
                        step_tag="[Error]",
                        current_index=idx,
                        total_items=total,
                        photo_path=p,
                    )
                )

    # 3. 联系单阶段
    dispatch_event(
        ProgressEvent(
            stage=PipelineStage.CONTACT_SHEET,
            level=EventLevel.INFO,
            message="正在拼装摄影总览联系单 (Contact Sheet)...",
            current_index=total,
            total_items=total,
        )
    )
    contact_sheet = make_contact_sheet(outputs, result_dir, output_policy)

    elapsed = round(time.time() - start_time, 2)
    summary = TaskSummary(
        total=total,
        success=len(outputs),
        failed=total - len(outputs),
        warnings=warnings,
        output_dir=result_dir,
        elapsed_seconds=elapsed,
        contact_sheet=contact_sheet,
    )

    # 4. Manifest 与 Report 结算
    dispatch_event(
        ProgressEvent(
            stage=PipelineStage.MANIFEST,
            level=EventLevel.INFO,
            message="正在落盘任务清单与结算报告...",
            current_index=total,
            total_items=total,
        )
    )
    manifest = _write_manifest(
        result_dir / "manifest.json",
        presentation,
        renderer,
        layout,
        output_policy,
        source_dir,
        result_dir,
        outputs,
        contact_sheet,
        summary=summary,
    )
    report_path = _write_generation_report(
        result_dir / "generation_report.md",
        summary,
        presentation,
        layout,
        outputs,
    )
    summary.manifest_path = manifest
    summary.report_path = report_path

    dispatch_event(
        ProgressEvent(
            stage=PipelineStage.COMPLETE,
            level=EventLevel.SUCCESS,
            message=f"任务完成！成功生成 {len(outputs)} 张卡片，耗时 {elapsed} 秒",
            current_index=total,
            total_items=total,
            photo_path=contact_sheet,
        )
    )

    return {
        "source_dir": source_dir,
        "result_dir": result_dir,
        "scheme": presentation.scheme_id,
        "renderer": presentation.renderer,
        "renderer_id": renderer.renderer_id,
        "layout": layout,
        "compression": output_policy.compression,
        "format": output_policy.format,
        "outputs": outputs,
        "contact_sheet": contact_sheet,
        "manifest": manifest,
        "report": report_path,
        "summary": summary,
    }


def generate_from_source(
    source_dir,
    output_dir=None,
    progress_callback=None,
    layout=None,
    scheme="scheme1",
    compression="none",
    debug=False,
    photo=None,
    event_callback: Callable[[ProgressEvent], None] | None = None,
):
    source_dir = Path(source_dir).resolve()
    presentation, normalized_layout = normalize_presentation(scheme, layout)
    output_root = Path(output_dir).resolve() if output_dir else source_dir / "PicFrame"
    result_dir = output_root / presentation.output_dir / normalized_layout / OutputPolicy(compression).format
    return generate_batch(
        source_dir,
        result_dir,
        source_dir,
        progress_callback=progress_callback,
        layout=normalized_layout,
        scheme=scheme,
        compression=compression,
        debug=debug,
        photo=photo,
        event_callback=event_callback,
    )


def generate(task_dir, progress_callback=None, layout=None, scheme="scheme1", compression="none", debug=False, photo=None, event_callback=None):
    """Legacy src/result compatibility path; it intentionally skips new nesting."""
    task_dir = Path(task_dir).resolve()
    src_dir = task_dir / "src"
    result_dir = task_dir / "result"
    if not src_dir.exists():
        raise SystemExit(f"Missing src folder: {src_dir}")

    try:
        result = generate_batch(
            src_dir,
            result_dir,
            task_dir,
            progress_callback=progress_callback,
            layout=layout,
            scheme=scheme,
            compression=compression,
            legacy=True,
            debug=debug,
            photo=photo,
            event_callback=event_callback,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Generated {len(result['outputs'])} cards in {result['result_dir']}")
    for out in result["outputs"]:
        print(out)
    if result["contact_sheet"]:
        print(result["contact_sheet"])
    return result
