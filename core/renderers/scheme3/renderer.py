from ...context import build_context
from ...renderer import PresentationRenderer
from .gallery import render_scheme3_gallery


class Scheme3Renderer(PresentationRenderer):
    renderer_id = "scheme3"

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
            f"🛰️ 提取遥测参数: {ctx.camera_model or '未知相机'} | {ctx.lens_model or '未知镜头'}",
            camera=ctx.camera_model,
            lens=ctx.lens_model,
            gps=ctx.exif.get("GPSPosition") or ctx.exif.get("GPSLatitude"),
        )
        return ctx

    def render(self, context):
        context.report_step(
            "[Sobel]",
            "⚡ Sobel 边缘梯度特征提取与主色调采样",
            edge_kernel="Sobel 3x3",
            bg_color=context.bg,
        )
        context.report_step(
            "[ASCII]",
            "👾 栅格化 ASCII 结构图元矩阵 (Block: █▓▒░)",
            charset="Block █▓▒░",
            matrix_mode="Adaptive Chroma",
        )
        context.report_step(
            "[Render]",
            f"🎛️ 组装 1:1 极客仪表舱与画廊双联 ({context.layout})",
            layout=context.layout,
        )
        return render_scheme3_gallery(context)
