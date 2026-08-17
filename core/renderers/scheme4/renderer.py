from ...context import build_context
from ...renderer import PresentationRenderer
from .editorial import render_scheme4_editorial


class Scheme4Renderer(PresentationRenderer):
    renderer_id = "scheme4"

    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none", exif=None):
        return build_context(photo_path, source_dir, presentation, layout, compression=compression, exif=exif)

    def render(self, context):
        return render_scheme4_editorial(context)
