from ...context import build_context
from ...renderer import PresentationRenderer
from .watermark import render_scheme2


class Scheme2Renderer(PresentationRenderer):
    renderer_id = "scheme2"

    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none", exif=None, step_callback=None):
        ctx = build_context(
            photo_path,
            source_dir,
            presentation,
            layout,
            compression=compression,
            exif=exif,
            step_callback=step_callback,
        )
        ctx.report_step(
            "[EXIF]",
            f"📷 提取参数: {ctx.camera_model or '未知相机'} | {ctx.lens_model or '未知镜头'}",
            camera=ctx.camera_model,
            lens=ctx.lens_model,
        )
        return ctx

    def render(self, context):
        context.report_step(
            "[Watermark]",
            "🏷️ 匹配品牌 Logo 与计算水印带参数",
            brand_logo="已自动匹配",
            watermark_layout="watermark_right_logo",
        )
        context.report_step("[Render]", "🖼️ 拼接高精无损底部水印带", mode="lossless_bottom_band")
        return render_scheme2(context)
