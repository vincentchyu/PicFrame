import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from core.batch import generate_from_source
from core.presentation import normalize_presentation
from core.renderers.scheme4.editorial import Scheme4Config, _extract_editorial_palette, render_scheme4_editorial
from core.renderers.scheme4.renderer import Scheme4Renderer
from core.renderer import validate_presentation_requirements
from core.rendering import get_renderer


class Scheme4EditorialTests(unittest.TestCase):
    def test_scheme4_registration_and_validation(self):
        scheme, layout = normalize_presentation("scheme4")
        self.assertEqual(scheme.scheme_id, "scheme4")
        self.assertEqual(scheme.layouts, ("editorial_diptych", "editorial_guidance", "editorial_asymmetric", "editorial_minimal"))
        self.assertEqual(layout, "editorial_diptych")
        validate_presentation_requirements(scheme)
        renderer = get_renderer(scheme)
        self.assertIsInstance(renderer, Scheme4Renderer)
        self.assertEqual(renderer.renderer_id, "scheme4")

    def test_scheme4_config_loading(self):
        config = Scheme4Config.load()
        diptych_layout = config.layout("editorial_diptych")
        self.assertEqual(diptych_layout["panel_color"], "#F3F0E8")
        self.assertEqual(diptych_layout["title_layout"], "center")
        guidance_layout = config.layout("editorial_guidance")
        self.assertEqual(guidance_layout["style"], "architectural_line")
        asymmetric_layout = config.layout("editorial_asymmetric")
        self.assertEqual(asymmetric_layout["title_layout"], "left")

    def test_palette_extraction(self):
        img = Image.new("RGB", (100, 100), color=(50, 100, 180))
        palette = _extract_editorial_palette(img)
        self.assertIn("dominant", palette)
        self.assertIn("dark", palette)
        self.assertIn("neutral", palette)
        self.assertIn("accent", palette)
        self.assertEqual(len(palette["dominant"]), 3)

    def test_scheme4_batch_generation_diptych_and_asymmetric(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            photo = source / "test_editorial.jpg"
            img = Image.new("RGB", (1200, 800), color=(70, 120, 190))
            img.save(photo)

            # 1. 默认 editorial_diptych
            res_diptych = generate_from_source(source, scheme="scheme4", layout="editorial_diptych", compression="none")
            diptych_card = res_diptych["result_dir"] / "test_editorial_card.png"
            self.assertTrue(diptych_card.exists())
            with Image.open(diptych_card) as im:
                self.assertEqual(im.width, 1200)
                self.assertGreater(im.height, 800)

            # 2. editorial_asymmetric
            res_asym = generate_from_source(source, scheme="scheme4", layout="editorial_asymmetric", compression="jpeg")
            asym_card = res_asym["result_dir"] / "test_editorial_card.jpg"
            self.assertTrue(asym_card.exists())

            # 3. 验证 manifest
            manifest = json.loads((res_asym["result_dir"] / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["scheme"], "scheme4")
            self.assertEqual(manifest["layout"], "editorial_asymmetric")
            self.assertEqual(manifest["renderer_id"], "scheme4")

    def test_universal_motifs_gallery_rendering(self):
        """验证所有通用抽象矢量图元类型均可稳定无异常渲染"""
        from core.renderers.scheme4.editorial import _draw_editorial_motif_gallery
        canvas = Image.new("RGBA", (1080, 1440), (243, 240, 232, 255))
        palette = {
            "dominant": (90, 120, 70),
            "dark": (35, 45, 35),
            "neutral": (180, 190, 200),
            "accent": (200, 90, 50),
        }
        all_motifs = [
            {"type": "atmospheric_band", "y": 0.22, "height": 0.38, "fill": "neutral"},
            {"type": "slope_plane", "start_y": 0.78, "end_y": 0.44, "fill": "dominant", "stroke": "dark"},
            {"type": "contour_surface", "curve_points": [0.4, 0.45, 0.38, 0.46, 0.41, 0.43], "fill": "dominant", "stroke": "dark"},
            {"type": "structural_columns", "pillars": [{"x": 0.4, "y": 0.5, "w": 0.1, "h": 0.4, "fill": "dark"}]},
            {"type": "arch_volume", "cx": 0.5, "cy": 0.6, "radius_w": 0.4, "radius_h": 0.3, "fill": "dominant"},
            {"type": "axis_line", "x0": 0.1, "y0": 0.7, "x1": 0.9, "y1": 0.7, "stroke": "dark"},
            {"type": "focal_marker", "x": 0.68, "y": 0.42, "shape": "vertical_notch", "fill": "accent"},
            {"type": "rhythm_marks", "points": [{"x": 0.4, "y": 0.6}, {"x": 0.6, "y": 0.62}], "fill": "accent"},
            {"type": "circle", "x": 0.75, "y": 0.3, "radius": 0.06, "fill": "accent"},
        ]
        # 执行绘制
        _draw_editorial_motif_gallery(canvas, 540, 1050, 400, 320, palette, all_motifs, "landscape")
        self.assertEqual(canvas.size, (1080, 1440))

    def test_svg_rasterizer_rendering(self):
        """验证纯 Python SVGRasterizer 支持 rect, circle, line, polygon, path(贝塞尔曲线)"""
        from core.renderers.scheme4.svg_rasterizer import SVGRasterizer
        palette = {
            "dominant": (90, 120, 70),
            "dark": (35, 45, 35),
            "neutral": (180, 190, 200),
            "accent": (200, 90, 50),
        }
        svg_code = """
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <rect x="10" y="20" width="80" height="60" rx="6" fill="neutral" fill-opacity="0.5"/>
          <path d="M 10 75 Q 50 45 90 70 L 90 85 L 10 85 Z" fill="dominant"/>
          <circle cx="50" cy="62" r="8" fill="dark"/>
          <line x1="10" y1="85" x2="90" y2="85" stroke="dark" stroke-width="1.5"/>
          <polygon points="65,35 75,35 70,25" fill="accent"/>
        </svg>
        """
        rasterizer = SVGRasterizer(400, 300, palette, super_sample=2)
        img = rasterizer.rasterize(svg_code)
        self.assertEqual(img.size, (400, 300))
        self.assertEqual(img.mode, "RGBA")

    def test_progressive_pipeline_flow(self):
        """验证四阶段流水线协调逻辑（Stage 1 空间焦点 -> Stage 2 标题 -> Stage 3 艺术造型特征 -> Stage 4 定制 SVG）"""
        from unittest.mock import MagicMock
        from core.renderers.scheme4.pipeline import MultiStageVisionPipeline

        stage1_resp = json.dumps({
            "scene_type": "landscape",
            "season_and_light": "winter morning snow",
            "emotional_mood": "solitary calm",
            "spatial_structure": {"horizon_y": 0.6, "structural_axis": "ridge ascending"},
            "subjects": [{"label": "lone climber", "x": 0.68, "y": 0.42, "count": 1, "role": "focal_anchor"}],
            "saliency_foci": [{"label": "LONE CLIMBER", "subject_type": "human", "center": [0.68, 0.42], "bbox": [0.64, 0.38, 0.72, 0.46]}],
            "palette": {"dominant": "#5A7A9A", "dark": "#1E2A38", "neutral": "#D0DCE8", "accent": "#C44E32"}
        })
        stage2_resp = json.dumps({
            "title": "SOLITUDE ON THE RIDGE",
            "subtitle": "a lone presence against eternal blue",
            "title_layout": "center"
        })
        stage3_resp = json.dumps({
            "hero_label": "LONE CLIMBER",
            "subject_type": "human",
            "kandinsky_elemental_grammar": {
                "primary_point_nature": "kinetic_pivot",
                "primary_line_trajectory": "ascending_vertical_with_diagonal_shear",
                "tension_level": 0.82,
                "force_vectors": [{"name": "climbing_thrust", "start": [0.68, 0.46], "end": [0.68, 0.38], "angle_deg": 85.0}],
                "basic_plane_gravity": "terrestrial_anchored"
            },
            "klee_genesis_and_growth": {
                "genesis_action": "reaching_across_space",
                "dendritic_morphology": {"branching_order": 1, "divergence_angle_deg": 40.0, "taper_factor": 0.5},
                "gravitational_equilibrium": "anti_gravity_thrust"
            },
            "cezanne_volumetric_faceting": {
                "geometric_archetype": "planar_polyhedron",
                "facet_planes": [{"name": "sunlit_profile", "orientation": "left", "tone_level": "highlight"}],
                "terminator_line_style": "hard_organic_ridge"
            },
            "gestalt_field_dynamics": {
                "figure_ground_relation": "high_relief_silhouette",
                "closure_tendency": "enclosed_monolithic",
                "perceptual_weight_offset": [0.0, -0.05]
            },
            "micro_hatching_and_strata": {
                "hatching_logic": "parallel_shadow_stream",
                "hatching_density": "sparse_breathing_5lines",
                "hatching_angle_deg": -40.0,
                "surface_strata": "organic_flesh_contour"
            },
            "chromatic_soul": {
                "chromatic_temperature": "cool_mineral_slate",
                "hero_dominant_color": "#5A7A9A",
                "focal_accent_pop": "#C44E32",
                "tint_alpha": 0.85
            },
            "curatorial_abstract_metaphor": {
                "formal_concept_title": "TENSION OF REACHING IN SILENCE",
                "curatorial_reduction_rule": "Preserve vertical thrust anchor with red accent"
            }
        })
        stage4_resp = json.dumps({
            "svg": "<svg viewBox=\"0 0 100 100\"><path d=\"M 10 80 L 90 40 L 90 85 L 10 85 Z\" fill=\"dominant\"/><circle cx=\"68\" cy=\"42\" r=\"2\" fill=\"accent\"/></svg>"
        })

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (stage1_resp, ""),
            (stage2_resp, ""),
            (stage3_resp, ""),
            (stage4_resp, ""),
        ]

        pipeline = MultiStageVisionPipeline(mock_provider, {"provider": "mlx", "pipeline_mode": "progressive", "motif_engine": "vlm"})
        res = pipeline.run(b"fake_bytes", "test.jpg")

        self.assertIsNotNone(res)
        self.assertEqual(res["title"], "SOLITUDE ON THE RIDGE")
        self.assertEqual(res["subtitle"], "a lone presence against eternal blue")
        self.assertIn("svg", res)
        self.assertIn("<svg", res["svg"])
        self.assertIn("focus_features", res)
        self.assertEqual(res["focus_features"]["kandinsky_elemental_grammar"]["primary_point_nature"], "kinetic_pivot")
        self.assertEqual(mock_provider.generate.call_count, 4)

    def test_vlm_analysis_mock_and_fallback(self):
        from unittest.mock import MagicMock, patch
        from core.renderers.scheme4.vlm import analyze_photo_with_ollama

        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
            img = Image.new("RGB", (100, 100), color=(100, 150, 200))
            img.save(tmp.name)

            # 1. 模拟 Fast 模式单次调用成功
            fake_content = json.dumps({
                "scene_type": "landscape",
                "title": "GRAZING HORIZONS",
                "subtitle": "whispering breeze on endless green",
                "palette": {
                    "dominant": "#5A7A42",
                    "dark": "#283820",
                    "neutral": "#8EA6C0",
                    "accent": "#9E5A32"
                },
                "svg": "<svg viewBox=\"0 0 100 100\"><path d=\"M 10 80 Q 50 60 90 75 L 90 85 L 10 85 Z\" fill=\"dominant\"/></svg>"
            })
            fake_response = MagicMock()
            fake_response.message.content = fake_content

            with patch("ollama.chat", return_value=fake_response):
                res = analyze_photo_with_ollama(tmp.name, {"enable": True, "provider": "ollama", "pipeline_mode": "fast", "motif_engine": "vlm", "model": "qwen3-vl:latest"})
                self.assertIsNotNone(res)
                self.assertEqual(res["title"], "GRAZING HORIZONS")
                self.assertIn("svg", res)
                self.assertEqual(len(res["palette"]["dominant"]), 3)

            # 2. 模拟服务异常平滑回退（返回 None）
            with patch("ollama.chat", side_effect=Exception("Connection refused")):
                res_err = analyze_photo_with_ollama(tmp.name, {"enable": True, "provider": "ollama", "pipeline_mode": "fast", "motif_engine": "vlm", "model": "qwen3-vl:latest"})
                self.assertIsNone(res_err)

    def test_debug_dump_intermediate_artifacts(self):
        """验证开启 debug 模式时，四阶段所有中间产物（含 Stage 3 艺术造型特征 json）均有序落盘"""
        from unittest.mock import MagicMock
        from core.renderers.scheme4.pipeline import MultiStageVisionPipeline

        stage1_resp = json.dumps({
            "scene_type": "landscape",
            "season_and_light": "winter morning",
            "emotional_mood": "solitary",
            "spatial_structure": {"horizon_y": 0.6},
            "subjects": [{"label": "lone figure", "x": 0.5, "y": 0.5}],
            "saliency_foci": [{"label": "FIGURE", "subject_type": "human", "center": [0.5, 0.5], "bbox": [0.4, 0.4, 0.6, 0.6]}],
            "palette": {"dominant": "#5A7A9A", "dark": "#1E2A38", "neutral": "#D0DCE8", "accent": "#C44E32"}
        })
        stage2_resp = json.dumps({
            "title": "SOLITUDE",
            "subtitle": "a quiet moment",
            "title_layout": "center"
        })
        stage3_resp = json.dumps({
            "hero_label": "FIGURE",
            "subject_type": "human",
            "kandinsky_elemental_grammar": {"primary_point_nature": "kinetic_pivot", "tension_level": 0.7},
            "curatorial_abstract_metaphor": {"formal_concept_title": "SILENT EMBODIMENT"}
        })
        stage4_resp = json.dumps({
            "svg": "<svg viewBox=\"0 0 100 100\"><polygon points=\"0,100 100,70 100,100\" fill=\"dominant\"/><path d=\"M 10 90 Q 60 20 95 65\" stroke=\"dark\"/></svg>"
        })

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (stage1_resp, "stage 1 thinking"),
            (stage2_resp, "stage 2 thinking"),
            (stage3_resp, "stage 3 thinking"),
            (stage4_resp, "stage 4 thinking"),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            debug_dir = Path(tmp_dir) / "photo_debug"
            pipeline = MultiStageVisionPipeline(mock_provider, {"provider": "mlx", "pipeline_mode": "progressive", "motif_engine": "vlm"})
            res = pipeline.run(b"fake_image_bytes", "photo.jpg", debug_dir=debug_dir)

            self.assertIsNotNone(res)
            # 验证四阶段序号命名的调试文件均存在且内容非空
            expected_files = [
                "01_stage1_prompt_system.txt",
                "01_stage1_prompt_user.txt",
                "01_stage1_raw_response.txt",
                "01_stage1_parsed.json",
                "02_stage2_prompt_system.txt",
                "02_stage2_prompt_user.txt",
                "02_stage2_raw_response.txt",
                "02_stage2_parsed.json",
                "03_stage3_prompt_system.txt",
                "03_stage3_prompt_user.txt",
                "03_stage3_raw_response.txt",
                "03_stage3_focus_features.json",
                "04_stage4_artwork_final.svg",
            ]
            for ef in expected_files:
                f_path = debug_dir / ef
                self.assertTrue(f_path.exists(), f"Missing debug file: {ef}")
                self.assertGreater(f_path.stat().st_size, 0, f"Empty debug file: {ef}")

    def test_fmt_editorial_meta_line(self):
        """验证画廊级元数据行对仗格式化"""
        from core.metadata import fmt_editorial_meta_line

        # 1. 完整 EXIF (包含经纬度、海拔与作者)
        exif_full = {
            "GPSLatitude": 38.2045,
            "GPSLatitudeRef": "N",
            "GPSLongitude": 100.7512,
            "GPSLongitudeRef": "E",
            "GPSAltitude": 3280,
            "Artist": "Vincent Chyu",
        }
        res_full = fmt_editorial_meta_line(exif_full)
        self.assertIn("38°12'N 100°45'E", res_full)
        self.assertIn("3280M", res_full)
        self.assertIn("BY VINCENT CHYU", res_full)
        self.assertEqual(res_full.count(" · "), 2)

        # 2. 缺失 GPS 时优雅回退
        exif_no_gps = {
            "Artist": "Vincent Chyu",
        }
        res_no_gps = fmt_editorial_meta_line(exif_no_gps)
        self.assertEqual(res_no_gps, "BY VINCENT CHYU")

    def test_morphology_domain_routing(self):
        """验证 8 大摄影视觉形态学领域专属语法库与动态 Prompt 组装"""
        from core.renderers.scheme4.prompts.morphology_domains import DOMAIN_GRAMMARS, get_domain_grammar
        from core.renderers.scheme4.prompts.stage3_synthesis import build_stage3_system_prompt, build_stage3_user_prompt

        # 1. 验证 8 大领域全量覆盖
        expected_domains = [
            "urban_architecture",
            "classical_heritage",
            "botanical_trees",
            "alpine_landscape",
            "water_seascape",
            "human_street_life",
            "animal_wildlife",
            "minimalist_fine_art",
        ]
        for dom in expected_domains:
            self.assertIn(dom, DOMAIN_GRAMMARS)
            g = get_domain_grammar(dom)
            self.assertIn("title", g)
            self.assertIn("geometric_rules", g)
            self.assertIn("few_shot", g)
            self.assertIn("<svg", g["few_shot"]["svg"])

        # 2. 验证现代都市领域动态注入了摩天楼网格规则且严禁山峰
        urban_prompt = build_stage3_system_prompt("urban_architecture")
        self.assertIn("Modern Urban", urban_prompt)
        self.assertIn("PARALLEL LIGHT HATCHING", urban_prompt)
        self.assertIn("triangular mountain peaks", urban_prompt)

        # 3. 验证东方古建领域动态注入了起翘飞檐与多层宝塔规则
        heritage_prompt = build_stage3_system_prompt("classical_heritage")
        self.assertIn("Classical Heritage", heritage_prompt)
        self.assertIn("SWEEPING UPWARD EAVE ARCS", heritage_prompt)
        self.assertIn("TIERED PAGODA SILHOUETTE", heritage_prompt)

        # 4. 验证植物老树领域动态注入了分叉枝桠矢量规则
        botanical_prompt = build_stage3_system_prompt("botanical_trees")
        self.assertIn("SKELETAL RADIAL BRANCHING", botanical_prompt)
        self.assertIn("CONIFER / SPRUCE SPIRES", botanical_prompt)

        # 5. 验证未知领域优雅回退
        fallback_prompt = build_stage3_system_prompt("unknown_random_domain")
        self.assertIn("Alpine Mountains", fallback_prompt)

    def test_generate_single_photo_filter(self):
        """验证 --photo 参数能准确过滤并只生成指定单张照片"""
        from core.batch import generate_from_source

        with tempfile.TemporaryDirectory() as tmp_src:
            src_dir = Path(tmp_src)
            img1 = Image.new("RGB", (600, 400), (200, 100, 100))
            img2 = Image.new("RGB", (600, 400), (100, 200, 100))
            img1.save(src_dir / "DSC_0001.jpg")
            img2.save(src_dir / "DSC_0002.jpg")

            # 1. 正常过滤 DSC_0002.jpg
            res = generate_from_source(src_dir, scheme="scheme4", layout="editorial_diptych", compression="jpeg", photo="DSC_0002.jpg")
            self.assertEqual(len(res["outputs"]), 1)
            self.assertTrue(res["outputs"][0].name.startswith("DSC_0002"))

            # 2. 传入不存在的文件名抛出合理异常
            with self.assertRaises(ValueError):
                generate_from_source(src_dir, scheme="scheme4", layout="editorial_diptych", photo="non_existent.jpg")

    def test_editorial_guidance_rendering(self):
        """验证精工细线草图风 (editorial_guidance) 在横图与竖图下的完整渲染流程"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src_dir = Path(tmp_dir) / "source"
            src_dir.mkdir()

            # 1. 横图测试 (无压缩原尺寸)
            photo_land = src_dir / "test_landscape.jpg"
            Image.new("RGB", (1200, 800), (60, 100, 150)).save(photo_land)

            res_land = generate_from_source(src_dir, scheme="scheme4", layout="editorial_guidance", compression="none", photo="test_landscape.jpg")
            card_land = res_land["result_dir"] / "test_landscape_card.png"
            self.assertTrue(card_land.exists())
            with Image.open(card_land) as im:
                self.assertEqual(im.width, 1200)
                self.assertGreater(im.height, 800)

            # 2. 竖图测试 (验证 4:3 左右横版双联，JPEG 1080 移动端压缩)
            photo_port = src_dir / "test_portrait.jpg"
            Image.new("RGB", (800, 1200), (150, 100, 60)).save(photo_port)

            res_port = generate_from_source(src_dir, scheme="scheme4", layout="editorial_guidance", compression="jpeg", photo="test_portrait.jpg")
            card_port = res_port["result_dir"] / "test_portrait_card.jpg"
            self.assertTrue(card_port.exists())
            with Image.open(card_port) as im:
                # 4:3 横版左右双联，总宽 = 1200 * 4 / 3 = 1600 -> JPEG 压缩至 1440x1080
                self.assertEqual(im.height, 1080)
                self.assertEqual(im.width, 1440)

    def test_subject_skeletal_curves_and_multi_foci(self):
        """验证不同主体类型 (tree, human/gesture, mountain, architecture) 的真实骨架与双焦点解构生成"""
        from core.renderers.scheme4.editorial import _generate_subject_skeletal_curves, _draw_architectural_line_art

        # 1. 树木结构测试
        tree_focus = {
            "label": "gnarled larch tree",
            "subject_type": "tree",
            "geometry_style": "fractal_spires",
            "center": [0.41, 0.52],
            "bbox": [0.1, 0.1, 0.7, 0.9],
            "keypoints": [[0.53, 0.93], [0.53, 0.50], [0.35, 0.45], [0.68, 0.42]],
        }
        tree_prim, tree_sec = _generate_subject_skeletal_curves(tree_focus, 0, 0, 500, 400)
        self.assertGreater(len(tree_prim), 0)
        self.assertGreater(len(tree_sec), 0)

        # 2. 人物与伸手手势测试
        figure_focus = {
            "label": "person reaching",
            "subject_type": "human",
            "geometry_style": "monolithic_block",
            "center": [0.51, 0.58],
            "bbox": [0.45, 0.28, 0.57, 0.89],
            "keypoints": [[0.50, 0.28], [0.50, 0.40], [0.50, 0.88]],
        }
        fig_prim, fig_sec = _generate_subject_skeletal_curves(figure_focus, 0, 0, 500, 400)
        self.assertGreater(len(fig_prim), 0)

        # 3. 双主体与焦点准星绘制测试
        canvas = Image.new("RGBA", (1080, 1440), (243, 240, 232, 255))
        palette = {
            "dominant": (90, 120, 70),
            "dark": (35, 45, 35),
            "neutral": (180, 190, 200),
            "accent": (200, 90, 50),
        }
        vlm_mock = {
            "scene_type": "seascape",
            "spatial_facts": {
                "composition_axis": {"horizon_y": 0.45, "slope_angle_deg": -5.0},
                "saliency_foci": [
                    tree_focus,
                    {
                        "label": "distant ridge",
                        "subject_type": "mountain",
                        "geometry_style": "sharp_planes",
                        "center": [0.75, 0.42],
                        "bbox": [0.0, 0.40, 1.0, 0.46],
                        "keypoints": [[0.0, 0.44], [0.5, 0.40], [1.0, 0.45]],
                    }
                ]
            }
        }
        _draw_architectural_line_art(canvas, 540, 1050, 500, 400, palette, "seascape", vlm_result=vlm_mock)
        self.assertEqual(canvas.size, (1080, 1440))

    def test_parse_content_and_thinking(self):
        from core.renderers.scheme4.vlm import _parse_content_and_thinking
        c, t = _parse_content_and_thinking("{\"title\": \"ALPINE\"}", "This is a thinking process.")
        self.assertEqual(c, "{\"title\": \"ALPINE\"}")
        self.assertEqual(t, "This is a thinking process.")

        raw_with_think = "<think>\nLet's analyze the alpine landscape...\n</think>\n{\"title\": \"ALPINE ECHO\"}"
        c2, t2 = _parse_content_and_thinking(raw_with_think, "")
        self.assertEqual(c2, "{\"title\": \"ALPINE ECHO\"}")
        self.assertIn("Let's analyze the alpine landscape...", t2)

    def test_pipeline_get_stage_options(self):
        from core.renderers.scheme4.vlm import MLXProvider
        from core.renderers.scheme4.pipeline import MultiStageVisionPipeline
        vlm_cfg = {
            "provider": "mlx",
            "thinking": {
                "enable": True,
                "stages": {
                    "stage1_spatial": {"level": "medium", "max_thinking_tokens": 1536, "temperature": 0.2, "reasoning_effort": "medium"},
                    "stage2_curatorial": {"level": "high", "max_thinking_tokens": 3072, "temperature": 0.6, "reasoning_effort": "high"},
                    "stage3_art_theory": {"level": "expert", "max_thinking_tokens": 4096, "temperature": 0.4, "reasoning_effort": "high"},
                }
            }
        }
        pipeline = MultiStageVisionPipeline(MLXProvider(), vlm_cfg)
        s1 = pipeline._get_stage_options("stage1_spatial")
        self.assertEqual(s1["level"], "medium")
        self.assertEqual(s1["max_thinking_tokens"], 1536)
        self.assertEqual(s1["temperature"], 0.2)
        self.assertEqual(s1["reasoning_effort"], "medium")

        s2 = pipeline._get_stage_options("stage2_curatorial")
        self.assertEqual(s2["level"], "high")
        self.assertEqual(s2["max_thinking_tokens"], 3072)
        self.assertEqual(s2["temperature"], 0.6)

        s3 = pipeline._get_stage_options("stage3_art_theory")
        self.assertEqual(s3["level"], "expert")
        self.assertEqual(s3["max_thinking_tokens"], 4096)
        self.assertEqual(s3["temperature"], 0.4)

        # 测试 isDefault: True 模式
        vlm_cfg_default = {
            "provider": "mlx",
            "thinking": {
                "enable": True,
                "isDefault": True,
            }
        }
        pipeline_default = MultiStageVisionPipeline(MLXProvider(), vlm_cfg_default)
        s_def = pipeline_default._get_stage_options("stage1_spatial")
        self.assertEqual(s_def["level"], "default")
        self.assertEqual(s_def["is_default"], True)
        self.assertIsNone(s_def["temperature"])
        self.assertIsNone(s_def["max_thinking_tokens"])

    def test_extract_curatorial_fallback_from_text(self):
        from core.renderers.scheme4.pipeline import _extract_curatorial_fallback_from_text

        # 模拟 9318 思考链末尾文本
        think_text_9318 = 'I think "WOOD, WOOL, AND MIST" is the best title.\nSubtitle: "a quiet flock beneath the pines"'
        res = _extract_curatorial_fallback_from_text("", think_text_9318)
        self.assertEqual(res.get("title"), "WOOD, WOOL, AND MIST")
        self.assertEqual(res.get("subtitle"), "a quiet flock beneath the pines")

        # 模拟 Option 格式
        think_text_opt = "Option A (Tactile & Material): SCULPTED SNOW | a solitary figure on frozen curves"
        res2 = _extract_curatorial_fallback_from_text("", think_text_opt)
        self.assertEqual(res2.get("title"), "SCULPTED SNOW")
        self.assertEqual(res2.get("subtitle"), "a solitary figure on frozen curves")


if __name__ == "__main__":
    unittest.main()







