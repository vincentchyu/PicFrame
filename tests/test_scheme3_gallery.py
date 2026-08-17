import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from core.batch import generate_from_source
from core.presentation import normalize_presentation
from core.renderers.scheme3.gallery import Scheme3Config, render_scheme3_gallery
from core.renderers.scheme3.renderer import Scheme3Renderer
from core.renderer import validate_presentation_requirements
from core.rendering import get_renderer


class Scheme3GalleryTests(unittest.TestCase):
    def test_scheme3_registration_and_validation(self):
        scheme, layout = normalize_presentation("scheme3")
        self.assertEqual(scheme.scheme_id, "scheme3")
        self.assertEqual(scheme.layouts, ("gallery_ascii_terminal", "gallery_ascii_diptych"))
        self.assertEqual(layout, "gallery_ascii_terminal")
        validate_presentation_requirements(scheme)
        renderer = get_renderer(scheme)
        self.assertIsInstance(renderer, Scheme3Renderer)
        self.assertEqual(renderer.renderer_id, "scheme3")

    def test_scheme3_config_loading(self):
        config = Scheme3Config.load()
        self.assertEqual(config.artist(), "Vincent Chyu")
        term_layout = config.layout("gallery_ascii_terminal")
        self.assertEqual(term_layout["background_color"], "auto")
        self.assertTrue(term_layout["shadow"]["enable"])
        diptych_layout = config.layout("gallery_ascii_diptych")
        self.assertEqual(diptych_layout["background_color"], "auto")

    def test_scheme3_batch_generation_terminal_and_diptych(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            photo = source / "test_gallery.jpg"
            img = Image.new("RGB", (1200, 800), color=(100, 150, 200))
            img.save(photo)

            # 1. 默认 gallery_ascii_terminal (输出 1:1 正方形)
            res_term = generate_from_source(source, scheme="scheme3", layout="gallery_ascii_terminal", compression="none")
            term_card = res_term["result_dir"] / "test_gallery_card.png"
            self.assertTrue(term_card.exists())
            with Image.open(term_card) as im:
                self.assertEqual(im.width, im.height)  # 严格 1:1 正方形

            # 2. gallery_ascii_diptych
            res_dip = generate_from_source(source, scheme="scheme3", layout="gallery_ascii_diptych", compression="jpeg")
            dip_card = res_dip["result_dir"] / "test_gallery_card.jpg"
            self.assertTrue(dip_card.exists())

            # 3. 验证 manifest
            manifest = json.loads((res_dip["result_dir"] / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["scheme"], "scheme3")
            self.assertEqual(manifest["layout"], "gallery_ascii_diptych")
            self.assertEqual(manifest["renderer_id"], "scheme3")


if __name__ == "__main__":
    unittest.main()
