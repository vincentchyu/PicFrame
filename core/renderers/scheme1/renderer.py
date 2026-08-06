from ...renderer import PresentationRenderer
from ...context import build_context
from ...metadata import fmt_copyright, fmt_gps, photo_year
from .assets import attach_gear_assets, load_gear_assets
from .cards import draw_copyright_overlay, draw_landscape_card, draw_portrait_card, draw_top_gps


class Scheme1Renderer(PresentationRenderer):
    renderer_id = "scheme1"

    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none", exif=None):
        gear_config = presentation.resolve_path(presentation.resources.get("gear_config"))
        gear_asset_dir = presentation.resolve_path(presentation.resources.get("gear_assets"))
        context = build_context(photo_path, source_dir, presentation, layout, compression=compression, exif=exif)
        return attach_gear_assets(context, load_gear_assets(source_dir, config_path=gear_config, asset_dir=gear_asset_dir))


    def render(self, context):
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
