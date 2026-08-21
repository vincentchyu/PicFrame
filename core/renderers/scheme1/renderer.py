from ...renderer import PresentationRenderer
from ...context import build_context
from ...metadata import fmt_copyright, fmt_gps, photo_year
from .assets import attach_gear_assets, load_gear_assets
from .cards import draw_copyright_overlay, draw_landscape_card, draw_portrait_card, draw_top_gps


class Scheme1Renderer(PresentationRenderer):
    renderer_id = "scheme1"

    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none", exif=None, step_callback=None):
        gear_config = presentation.resolve_path(presentation.resources.get("gear_config"))
        gear_asset_dir = presentation.resolve_path(presentation.resources.get("gear_assets"))
        context = build_context(
            photo_path,
            source_dir,
            presentation,
            layout,
            compression=compression,
            exif=exif,
            step_callback=step_callback,
        )
        exp_text = " | ".join(context.line_items) if context.line_items else ""
        context.report_step(
            "[EXIF]",
            f"📷 提取参数: {context.camera_model or '未知相机'} | {context.lens_model or '未知镜头'}",
            camera=context.camera_model,
            lens=context.lens_model,
            exposure=exp_text,
        )
        attached_ctx = attach_gear_assets(context, load_gear_assets(source_dir, config_path=gear_config, asset_dir=gear_asset_dir))
        cam_stat = "官方高清PNG" if attached_ctx.camera_png else "默认图标"
        lens_stat = "官方高清PNG" if attached_ctx.lens_png else "默认图标"
        attached_ctx.report_step(
            "[Asset]",
            f"🔍 匹配图标: 机身[{cam_stat}] 镜头[{lens_stat}]",
            camera_asset=cam_stat,
            lens_asset=lens_stat,
        )
        return attached_ctx

    def render(self, context):
        context.report_step("[Palette]", f"🎨 提取背景柔和色调: {context.bg}", bg_rgb=context.bg)
        context.report_step("[Render]", f"🖼️ 绘制极简信息卡 ({context.effective_layout})", layout=context.effective_layout)
        if context.effective_layout == "landscape":
            return draw_landscape_card(context)
        return draw_portrait_card(context)

    def apply_overlays(self, canvas, context):
        scale = canvas.width / 1080 if context.effective_layout != "landscape" else canvas.height / 1080
        draw_top_gps(canvas, fmt_gps(context.exif), context.bg, scale=scale)
        draw_copyright_overlay(
            canvas,
            fmt_copyright(context.exif),
            context.bg,
            scale=scale,
        )
        return canvas
