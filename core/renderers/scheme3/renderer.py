from ...context import build_context
from ...renderer import PresentationRenderer
from .gallery import render_scheme3_gallery


class Scheme3Renderer(PresentationRenderer):
    renderer_id = "scheme3"

    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none", exif=None):
        return build_context(photo_path, source_dir, presentation, layout, compression=compression, exif=exif)

    def render(self, context):
        return render_scheme3_gallery(context)
