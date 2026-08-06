import json
import tempfile
import unittest
from pathlib import Path

from core.presentation import PresentationScheme, load_presentation_schemes, normalize_presentation
from core.renderers.scheme2.watermark import Scheme2Config
from core.renderer import validate_presentation_requirements
from core.rendering import get_renderer


class PresentationConfigTests(unittest.TestCase):
    def test_scheme1_defaults_and_layouts(self):
        scheme, layout = normalize_presentation("scheme1")
        self.assertEqual(scheme.scheme_id, "scheme1")
        self.assertEqual(scheme.layouts, ("portrait", "landscape"))
        self.assertEqual(layout, "portrait")

    def test_rejects_layout_not_supported_by_scheme(self):
        with self.assertRaisesRegex(ValueError, "not supported by scheme1"):
            normalize_presentation("scheme1", "square")

    def test_loads_future_scheme_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "presentation_schemes.json"
            path.write_text(
                json.dumps(
                    {
                        "schemes": {
                            "scheme2": {
                                "name": "方案2",
                                "renderer": "scheme2",
                                "layouts": ["wide"],
                                "default_layout": "wide",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            schemes = load_presentation_schemes(path)
            self.assertEqual(schemes["scheme2"].default_layout, "wide")
            self.assertEqual(schemes["scheme2"].renderer, "scheme2")

    def test_scheme2_migrated_config_and_assets(self):
        scheme, layout = normalize_presentation("scheme2")
        validate_presentation_requirements(scheme)
        config = Scheme2Config.load(scheme.resolve_path(scheme.config))
        self.assertEqual(scheme.renderer, "core.renderers.scheme2:Scheme2Renderer")
        self.assertEqual(scheme.config, "config/schemes/scheme2/config.yaml")
        self.assertIn("PyYAML", scheme.dependencies)
        self.assertEqual(layout, "watermark_right_logo")
        self.assertTrue(config._resolve(config._base()["font"]).exists())
        self.assertTrue(config.logo_for_make("NIKON CORPORATION").exists())

    def test_scheme_owned_config_and_resources_are_declared(self):
        scheme1, _ = normalize_presentation("scheme1")
        scheme2, _ = normalize_presentation("scheme2")
        self.assertEqual(scheme1.config, "config/schemes/scheme1/gear_assets.json")
        self.assertEqual(scheme1.resources["gear_assets"], "assets/scheme1/gear")
        self.assertEqual(scheme2.config, "config/schemes/scheme2/config.yaml")
        self.assertEqual(scheme2.resources["fonts"], "assets/scheme2/fonts")

    def test_registered_renderer_is_resolvable(self):
        for scheme in load_presentation_schemes().values():
            self.assertTrue(scheme.renderer.startswith("core.renderers."))
            self.assertEqual(get_renderer(scheme).renderer_id, scheme.scheme_id)

    def test_unknown_renderer_is_rejected(self):
        scheme, _ = normalize_presentation("scheme1")
        scheme = scheme.__class__(
            scheme.scheme_id,
            scheme.name,
            "missing:Renderer",
            scheme.layouts,
            scheme.default_layout,
            scheme.output_dir,
            scheme.config,
            scheme.resources,
            scheme.dependencies,
        )
        with self.assertRaisesRegex(ValueError, "Invalid presentation renderer"):
            get_renderer(scheme)

    def test_missing_declared_resource_is_rejected_for_selected_scheme(self):
        scheme = PresentationScheme(
            "future",
            "Future",
            "core.renderers.scheme1:Scheme1Renderer",
            ("portrait",),
            "portrait",
            "future",
            None,
            {"missing_asset_root": "assets/not-here"},
            (),
        )
        with self.assertRaisesRegex(FileNotFoundError, "missing_asset_root"):
            validate_presentation_requirements(scheme)

    def test_missing_declared_dependency_is_rejected_for_selected_scheme(self):
        scheme = PresentationScheme(
            "future",
            "Future",
            "core.renderers.scheme1:Scheme1Renderer",
            ("portrait",),
            "portrait",
            "future",
            None,
            {},
            ("definitely_missing_PicFrame_dependency",),
        )
        with self.assertRaisesRegex(RuntimeError, "definitely_missing_PicFrame_dependency"):
            validate_presentation_requirements(scheme)


if __name__ == "__main__":
    unittest.main()
