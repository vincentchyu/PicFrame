import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core.batch import generate_from_source
from core.output import OutputPolicy


class OutputPolicyTests(unittest.TestCase):
    def test_none_is_uncompressed_png_and_jpeg_is_compressed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = Image.new("RGB", (8, 8), "white")
            png = root / "a.png"
            jpg = root / "a.jpg"
            OutputPolicy("none").save_card(image, png)
            OutputPolicy("jpeg").save_card(image, jpg)
            with Image.open(png) as rendered_png:
                self.assertEqual(rendered_png.format, "PNG")
            with Image.open(jpg) as rendered_jpg:
                self.assertEqual(rendered_jpg.format, "JPEG")


class BatchOutputTests(unittest.TestCase):
    def test_scheme_layout_format_and_manifest_are_isolated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            photo = source / "photo.jpg"
            photo.write_bytes(b"source")

            def fake_card(photo_path, result_dir, *args, **kwargs):
                output = result_dir / f"{photo_path.stem}_card.jpg"
                output.write_bytes(b"jpeg")
                return output

            contact_sheet = lambda outputs, result_dir, *args, **kwargs: result_dir / "contact-sheet.jpg"
            with patch("core.batch.make_card", side_effect=fake_card), patch(
                "core.batch.make_contact_sheet", side_effect=contact_sheet
            ):
                result = generate_from_source(source, scheme="scheme2", compression="jpeg")

            expected = source / "PicFrame" / "scheme2" / "watermark_right_logo" / "jpeg"
            self.assertEqual(result["result_dir"], expected.resolve())
            self.assertTrue((expected / "photo_card.jpg").exists())
            manifest = json.loads((expected / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["scheme"], "scheme2")
            self.assertEqual(manifest["renderer_id"], "scheme2")
            self.assertEqual(manifest["renderer"], "core.renderers.scheme2:Scheme2Renderer")
            self.assertEqual(manifest["compression"], "jpeg")
            self.assertEqual(manifest["format"], "jpeg")


class CompressionResolutionTests(unittest.TestCase):
    def test_scheme1_and_scheme2_compression_resolution_behavior(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            # 创建一个 3000x2000 的大像素图像
            photo = source / "test_photo.jpg"
            img = Image.new("RGB", (3000, 2000), color="blue")
            img.save(photo)

            # 1. Scheme1 + compression="none" (不压缩：照片像素100%保留，卡片比例放大)
            res_s1_none = generate_from_source(source, scheme="scheme1", compression="none")
            s1_none_card = res_s1_none["result_dir"] / "test_photo_card.png"
            self.assertTrue(s1_none_card.exists())
            with Image.open(s1_none_card) as im:
                # 横图在 landscape 下基准尺寸是 1440x1080 (照片框 816x912)。3000x2000照片的fit_scale是 816/3000 = 0.272，放大 scale 约 3.676
                # 放大后的画布宽应该显著大于 1440
                self.assertGreater(im.width, 3000)
                self.assertGreater(im.height, 2000)

            # 2. Scheme1 + compression="jpeg" (压缩：画布使用 1080 基准尺寸 1080x1440 或 1440x1080)
            res_s1_jpeg = generate_from_source(source, scheme="scheme1", compression="jpeg")
            s1_jpeg_card = res_s1_jpeg["result_dir"] / "test_photo_card.jpg"
            self.assertTrue(s1_jpeg_card.exists())
            with Image.open(s1_jpeg_card) as im:
                self.assertEqual(im.width, 1080)

            # 3. Scheme2 + compression="none" (不压缩：照片保持 3000px 原始宽度，外加 white_margin)
            res_s2_none = generate_from_source(source, scheme="scheme2", compression="none")
            s2_none_card = res_s2_none["result_dir"] / "test_photo_card.png"
            self.assertTrue(s2_none_card.exists())
            with Image.open(s2_none_card) as im:
                self.assertGreaterEqual(im.width, 3000)

            # 4. Scheme2 + compression="jpeg" (压缩：横图高度收敛在 1080 基准范围内)
            res_s2_jpeg = generate_from_source(source, scheme="scheme2", compression="jpeg")
            s2_jpeg_card = res_s2_jpeg["result_dir"] / "test_photo_card.jpg"
            self.assertTrue(s2_jpeg_card.exists())
            with Image.open(s2_jpeg_card) as im:
                self.assertLess(im.height, 1200)


class OptimizationTests(unittest.TestCase):
    def test_exif_cache_hits_memory(self):
        from core.metadata import _EXIF_MEMORY_CACHE, run_exif
        path = Path("tests/test_photo.jpg").resolve()
        _EXIF_MEMORY_CACHE[path] = {"Model": "TestCamera"}
        exif = run_exif(path)
        self.assertEqual(exif.get("Model"), "TestCamera")

    def test_dominant_bg_single_color(self):
        from core.rendering import dominant_bg
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            img = Image.new("RGB", (10, 10), color=(255, 0, 0))
            img.save(f.name)
            bg = dominant_bg(f.name)
            self.assertEqual(len(bg), 3)


if __name__ == "__main__":
    unittest.main()
