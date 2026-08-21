from ...context import build_context
from ...renderer import PresentationRenderer
from .editorial import render_scheme4_editorial


class Scheme4Renderer(PresentationRenderer):
    renderer_id = "scheme4"

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
        ctx.report_step("[EXIF]", f"📷 提取参数与物理事实: {ctx.camera_model or '未知相机'} | {ctx.lens_model or '未知镜头'}")
        return ctx

    def render(self, context):
        return render_scheme4_editorial(context)
