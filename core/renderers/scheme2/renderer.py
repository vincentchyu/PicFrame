from ...context import build_context
from ...renderer import PresentationRenderer
from .watermark import render_scheme2


class Scheme2Renderer(PresentationRenderer):
    renderer_id = "scheme2"

    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none", exif=None):
        return build_context(photo_path, source_dir, presentation, layout, compression=compression, exif=exif)


    def render(self, context):
        return render_scheme2(context)
