"""
Scheme4 多阶段摄影视觉解构流水线协调器 (Multi-Stage Vision & Abstraction Pipeline)

核心架构 (Four-Stage Progressive Pipeline):
Stage 1: 视觉解构与真实空间地貌/主体锚定 (Spatial & Semantic Deconstruction)
Stage 2: 文学策展与诗性标题 (Curatorial Literature & Title)
Stage 3: 核心主焦点艺术造型理论特征抽象 (Hero Focus Art Theory & Morphological Abstraction)
Stage 4: 定制化极简艺术矢量 SVG / 几何图元合成 (Artistic Synthesis & Primitive Engine)

包含全流程状态日志、SVG 代码提取、Debug 产物有序落盘与自适应降级自愈保障。
"""
import json
import re
import time
from pathlib import Path

from .generators import generate_motif_svg, apply_selective_color_filter, apply_selective_color_pipeline
from .primitive_engine import generate_primitive_svg
from .prompts import (
    STAGE1_SYSTEM_PROMPT,
    STAGE1_USER_PROMPT,
    build_stage1_user_prompt,
    STAGE2_SYSTEM_PROMPT,
    build_stage2_user_prompt,
    STAGE3_FEATURES_SYSTEM_PROMPT,
    build_stage3_features_user_prompt,
    STAGE4_SYSTEM_PROMPT,
    build_stage4_system_prompt,
    build_stage4_user_prompt,
    FAST_UNIFIED_SYSTEM_PROMPT,
    FAST_UNIFIED_USER_PROMPT,
)


def _soften_editorial_rgb(rgb, max_sat=0.45):
    """将色彩压低饱和度至画廊级哑光质感"""
    import colorsys
    r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    s = min(s, max_sat)
    l = max(0.18, min(0.88, l))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return (int(nr * 255), int(ng * 255), int(nb * 255))


def _hex_to_rgb(hex_str, default=(100, 100, 100)):
    if not hex_str or not isinstance(hex_str, str):
        return default
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 6:
        try:
            raw = (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
            return _soften_editorial_rgb(raw)
        except ValueError:
            pass
    return default


def _extract_json_from_text(text: str) -> dict | None:
    if not text:
        return None

    # 1. 优先提取 ```json ... ``` 代码块
    json_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if json_block:
        candidate = json_block.group(1).strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 2. 尝试整体解析
    clean = text.strip()
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 3. 寻找最外层的大括号范围（从第一个 { 到最后一个 }）
    start_idx = clean.find("{")
    end_idx = clean.rfind("}")
    if start_idx != -1 and end_idx > start_idx:
        candidate = clean[start_idx : end_idx + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 4. 括号深度扫描所有闭合的 JSON 对象候选
    start = -1
    depth = 0
    in_string = False
    escape = False
    candidates = []

    for i, char in enumerate(text):
        if char == '"' and not escape:
            in_string = not in_string
        elif char == '\\' and in_string:
            escape = not escape
            continue
        elif not in_string:
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    candidates.append(text[start : i + 1])
                    start = -1
        escape = False

    for c in reversed(candidates):
        try:
            data = json.loads(c)
            if isinstance(data, dict) and (
                "title" in data or "svg" in data or "spatial_structure" in data or "scene_type" in data or "saliency_foci" in data or "kandinsky_elemental_grammar" in data or "hero_label" in data
            ):
                return data
        except json.JSONDecodeError:
            continue

    return None


def _extract_svg_code(text: str, data: dict | None = None) -> str | None:
    """从结构化 JSON 或原始文本中提取 <svg>...</svg> 代码块"""
    if data and isinstance(data, dict) and "svg" in data and isinstance(data["svg"], str):
        svg_val = data["svg"].strip()
        if "<svg" in svg_val:
            return svg_val

    if not text:
        return None

    svg_block = re.search(r"```(?:svg|xml)?\s*(<svg[\s\S]*?<\/svg>)\s*```", text, re.IGNORECASE)
    if svg_block:
        return svg_block.group(1).strip()

    direct_match = re.search(r"<svg[\s\S]*?<\/svg>", text, re.IGNORECASE)
    if direct_match:
        return direct_match.group(0).strip()

    return None


def _extract_curatorial_fallback_from_text(s2_raw: str, s2_think: str) -> dict:
    """
    当 Stage 2 JSON 结构解析为空时，从思考链或原始响应中智能兜底提取画廊标题与副标
    """
    combined = f"{s2_raw}\n\n{s2_think}".strip()
    if not combined:
        return {}

    title = ""
    subtitle = ""

    # 1. 尝试匹配 JSON 字段模式 "title": "..."
    t_match = re.search(r'"title"\s*:\s*"([^"]{2,50})"', combined)
    if t_match:
        title = t_match.group(1).strip().upper()
    s_match = re.search(r'"subtitle"\s*:\s*"([^"]{3,80})"', combined)
    if s_match:
        subtitle = s_match.group(1).strip()

    # 2. 尝试从思考链结论中匹配 Title: **...** 或 Title: ...
    if not title:
        m = re.search(r'(?:Title|title|TITLE)\s*:\s*(?:\*\*)?([A-Za-z\s&,–—\'-]{3,40})(?:\*\*)?', combined)
        if m:
            t = m.group(1).strip().strip('"').strip("'")
            if len(t.split()) <= 6:
                title = t.upper()

    if not title:
        m = re.search(r'(?:think|believe|select|choose)\s+[\'"]([A-Za-z\s&,–—\'-]{3,40})[\'"]\s+is\s+the\s+(?:best|strongest|chosen|winning|final)\s+title', combined, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
            if len(t.split()) <= 6:
                title = t.upper()

    if not subtitle:
        m = re.search(r'(?:Subtitle|subtitle|SUBTITLE)\s*:\s*(?:\*|\")?([A-Za-z\s,–—\'-]{4,70})(?:\*|\")?', combined)
        if m:
            s = m.group(1).strip().strip('"').strip("'")
            if len(s.split()) <= 10:
                subtitle = s

    # 3. 尝试匹配 Option A/B/C: [Title] | [Subtitle] 格式
    if not title or not subtitle:
        opt_match = re.search(r'Option\s+[A-C][^:]*:\s*([A-Za-z\s&,–—\'-]{3,40})\s*\|\s*([A-Za-z\s,–—\'-]{4,70})', combined)
        if opt_match:
            if not title:
                title = opt_match.group(1).strip().upper()
            if not subtitle:
                subtitle = opt_match.group(2).strip()

    res = {}
    if title:
        res["title"] = title
    if subtitle:
        res["subtitle"] = subtitle
    return res


def _save_debug_file(debug_dir: Path | str | None, filename: str, content: str | bytes | dict | list):
    """按序号节点安全保存中间流水线调试文件"""
    if not debug_dir:
        return
    try:
        p = Path(debug_dir)
        p.mkdir(parents=True, exist_ok=True)
        target = p / filename
        if isinstance(content, bytes):
            with open(target, "wb") as f:
                f.write(content)
        elif isinstance(content, (dict, list)):
            with open(target, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(str(content))
    except Exception as exc:
        print(f"[Debug Dump] ⚠️ 保存调试文件 {filename} 异常: {exc}")


def _synthesize_focus_features_fallback(s1_data: dict, s2_data: dict = None) -> dict:
    """当 VLM 离线或异常时，基于 Stage 1 空间几何事实自适应推导艺术造型理论特征模型 (Local CV Fallback)"""
    foci = s1_data.get("saliency_foci", [])
    hero = foci[0] if (foci and isinstance(foci, list) and len(foci) > 0 and isinstance(foci[0], dict)) else {}
    label = hero.get("label", "HERO FEATURE")
    st = hero.get("subject_type", "general")
    center = hero.get("center", [0.5, 0.5])
    bbox = hero.get("bbox", [0.2, 0.2, 0.8, 0.8])
    kpts = hero.get("keypoints", [])
    axis = s1_data.get("composition_axis", {})
    slope = float(axis.get("slope_angle_deg", 0.0))
    pal = s1_data.get("palette", {})

    if "tree" in str(st).lower() or "botanical" in str(st).lower():
        point_nature = "pulsing_impulse_pivot"
        line_trajectory = "ascending_vertical_with_diagonal_shear"
        genesis_action = "branching_out_into_void"
        geo_archetype = "cylindrical_trunk_to_fractal_spires"
        strata = "striated_bark_fibers"
        metaphor_title = "FRACTAL RESILIENCE AGAINST THE VOID"
    elif "human" in str(st).lower() or "figure" in str(st).lower() or "gesture" in str(st).lower():
        point_nature = "kinetic_pivot"
        line_trajectory = "curvilinear_undulation"
        genesis_action = "reaching_across_space"
        geo_archetype = "planar_polyhedron"
        strata = "organic_flesh_contour"
        metaphor_title = "KINETIC TENSION IN DIALOGUE"
    elif "mountain" in str(st).lower() or "alpine" in str(st).lower() or "ridge" in str(st).lower():
        point_nature = "static_grounded_pivot"
        line_trajectory = "ascending_vertical_with_diagonal_shear"
        genesis_action = "static_crystallization"
        geo_archetype = "conical_spire"
        strata = "crystalline_rock_facets"
        metaphor_title = "MONOLITHIC STILLNESS ON THE RIDGE"
    else:
        point_nature = "static_grounded_pivot"
        line_trajectory = "curvilinear_undulation"
        genesis_action = "walking_line_journey"
        geo_archetype = "hyperbolic_sheet"
        strata = "flowing_fluid_currents"
        metaphor_title = "SPATIAL AXIS OF MEMORY"

    return {
        "hero_label": label,
        "subject_type": st,
        "kandinsky_elemental_grammar": {
            "primary_point_nature": point_nature,
            "primary_line_trajectory": line_trajectory,
            "tension_level": 0.75,
            "force_vectors": [
                {"name": "primary_thrust", "start": [center[0], bbox[3] if len(bbox) >= 4 else 0.8], "end": center, "angle_deg": 90.0 - slope}
            ],
            "basic_plane_gravity": "terrestrial_anchored"
        },
        "klee_genesis_and_growth": {
            "genesis_action": genesis_action,
            "dendritic_morphology": {
                "branching_order": 2 if len(kpts) > 2 else 1,
                "divergence_angle_deg": 45.0,
                "taper_factor": 0.40
            },
            "gravitational_equilibrium": "anti_gravity_thrust" if center[1] < 0.5 else "tensegrity_balance"
        },
        "cezanne_volumetric_faceting": {
            "geometric_archetype": geo_archetype,
            "facet_planes": [
                {"name": "primary_light_facet", "orientation": "left", "tone_level": "highlight"},
                {"name": "shadow_recession", "orientation": "right", "tone_level": "deep_shadow"}
            ],
            "terminator_line_style": "hard_organic_ridge"
        },
        "gestalt_field_dynamics": {
            "figure_ground_relation": "high_relief_silhouette",
            "closure_tendency": "open_dispersive",
            "perceptual_weight_offset": [0.0, -0.05]
        },
        "micro_hatching_and_strata": {
            "hatching_logic": "parallel_shadow_stream",
            "hatching_density": "sparse_breathing_5lines",
            "hatching_angle_deg": slope - 40.0 if abs(slope) > 1 else -35.0,
            "surface_strata": strata
        },
        "chromatic_soul": {
            "chromatic_temperature": "cool_mineral_slate" if "blue" in str(pal).lower() else "warm_earth_ochre",
            "hero_dominant_color": pal.get("dominant", "#5A6E82") if isinstance(pal, dict) else "#5A6E82",
            "focal_accent_pop": pal.get("accent", "#B45A3C") if isinstance(pal, dict) else "#B45A3C",
            "tint_alpha": 0.85
        },
        "curatorial_abstract_metaphor": {
            "formal_concept_title": metaphor_title,
            "curatorial_reduction_rule": "Preserve primary skeletal thrust, 2 secondary branch tethers, anchor with soft mineral tint crosshair"
        }
    }


from ...domain.events import EventLevel, PipelineStage, ProgressEvent


class MultiStageVisionPipeline:
    """四阶段视觉解构、艺术造型特征抽象与专属 SVG 合成流水线协调器"""

    def __init__(self, provider, vlm_cfg: dict):
        self.provider = provider
        self.vlm_cfg = vlm_cfg or {}
        self.provider_name = self.vlm_cfg.get("provider", "mlx")

    def _get_stage_options(self, stage_name: str) -> dict:
        """从配置中提取指定阶段的思考级别与推理参数配置 (Stage-specific Reasoning Options)"""
        thinking_cfg = self.vlm_cfg.get("thinking", {})
        is_enabled = thinking_cfg.get("enable", True)
        is_default = bool(thinking_cfg.get("isDefault", thinking_cfg.get("is_default", False)))

        if is_default:
            # 极简模式：完全使用服务端默认 AI 调参（仅传递 Prompt、图片并开启自动思考）
            return {
                "level": "default",
                "max_thinking_tokens": None,
                "temperature": None,
                "reasoning_effort": None,
                "thinking_enabled": is_enabled,
                "is_default": True,
            }

        stages = thinking_cfg.get("stages", {})
        st_cfg = stages.get(stage_name, {})

        # 默认基准策略映射
        defaults = {
            "stage1_spatial": {"level": "medium", "max_thinking_tokens": 1536, "temperature": 0.2, "reasoning_effort": "medium"},
            "stage2_curatorial": {"level": "low", "max_thinking_tokens": 768, "temperature": 0.2, "reasoning_effort": "low"},
            "stage3_art_theory": {"level": "expert", "max_thinking_tokens": 4096, "temperature": 0.4, "reasoning_effort": "high"},
            "stage4_svg_synthesis": {"level": "medium", "max_thinking_tokens": 2048, "temperature": 0.2, "reasoning_effort": "medium"},
            "fast_unified": {"level": "medium", "max_thinking_tokens": 2048, "temperature": 0.3, "reasoning_effort": "medium"},
        }
        fallback = defaults.get(stage_name, {"level": "medium", "max_thinking_tokens": 2048, "temperature": 0.2, "reasoning_effort": "medium"})

        level = st_cfg.get("level", fallback["level"])
        max_thinking = st_cfg.get("max_thinking_tokens", fallback["max_thinking_tokens"]) if is_enabled else 0
        temp = float(st_cfg.get("temperature", fallback["temperature"]))
        effort = st_cfg.get("reasoning_effort", fallback["reasoning_effort"]) if is_enabled else None

        return {
            "level": level,
            "max_thinking_tokens": max_thinking,
            "temperature": temp,
            "reasoning_effort": effort,
            "thinking_enabled": is_enabled,
            "is_default": False,
        }

    def run(self, img_bytes: bytes, filename: str, debug_dir=None, geo_context=None, step_callback=None) -> dict | None:
        mode = self.vlm_cfg.get("pipeline_mode", "progressive")
        if mode == "fast":
            return self.run_fast(img_bytes, filename, debug_dir=debug_dir, geo_context=geo_context, step_callback=step_callback)
        return self.run_progressive(img_bytes, filename, debug_dir=debug_dir, geo_context=geo_context, step_callback=step_callback)

    def run_progressive(self, img_bytes: bytes, filename: str, debug_dir=None, geo_context=None, step_callback=None) -> dict | None:
        """
        运行四阶段渐进式流水线：
        1. 视觉解构与空间锚定 (Stage 1)
        2. 文学策展与诗性标题 (Stage 2)
        3. 核心主焦点艺术造型理论特征抽象 (Stage 3 - NEW)
        4. 定制化极简艺术矢量 SVG / 几何图元合成 (Stage 4)
        """
        def _report(step_tag, msg, level=EventLevel.INFO, **details):
            if step_callback:
                step_callback(
                    ProgressEvent(
                        stage=PipelineStage.RENDERING,
                        level=level,
                        message=msg,
                        step_tag=step_tag,
                        details=details,
                    )
                )

        _report("[VLM]", f"🚀 启动四阶段视觉解构与造型理论抽象流水线: {filename}", engine=self.provider_name)
        print(f"\n[VLM Pipeline] 🚀 启动四阶段视觉解构、造型理论抽象与定制 SVG 矢量流水线: {filename}")
        if geo_context and (geo_context.get("gps") or geo_context.get("altitude")):
            gps_info = geo_context.get("gps", "")
            alt_info = geo_context.get("altitude", "")
            print(f"[VLM Context] 📍 注入真实地理物理事实: GPS={gps_info} | 海拔={alt_info}")
        t_total_start = time.time()

        # 解析输入图片的物理尺寸与真实画幅比例
        orig_w, orig_h, native_aspect = 1000, 1000, 1.0
        orientation = "landscape"
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(img_bytes)) as _test_im:
                orig_w, orig_h = _test_im.size
                native_aspect = round(orig_w / float(orig_h), 3) if orig_h > 0 else 1.0
                orientation = "square" if orig_w == orig_h else ("portrait" if orig_w < orig_h else "landscape")
        except Exception:
            pass

        # -------------------------------------------------------------------
        # Stage 1: 视觉解构与空间锚定 (带图调用) [20%]
        # -------------------------------------------------------------------
        s1_opts = self._get_stage_options("stage1_spatial")
        if s1_opts.get("is_default"):
            print(f"[VLM Stage 1/5] [20%] 🔍 正在解构空间地貌、构件与核心主体 (Thinking: DEFAULT | Mode: Raw AI Defaults)...")
        else:
            print(f"[VLM Stage 1/5] [20%] 🔍 正在解构空间地貌、构件与核心主体 (Thinking: {s1_opts['level'].upper()} | Budget: {s1_opts['max_thinking_tokens']} tok | Temp: {s1_opts['temperature']})...")
        t0 = time.time()
        s1_base_prompt = build_stage1_user_prompt(orig_w, orig_h, native_aspect)
        s1_user_prompt = (
            f"{s1_base_prompt}\n\nGeographical & Altitude Reality Context:\n{json.dumps(geo_context, ensure_ascii=False)}"
            if geo_context else s1_base_prompt
        )
        s1_raw, s1_think = self.provider.generate(
            img_bytes,
            STAGE1_SYSTEM_PROMPT,
            s1_user_prompt,
            self.vlm_cfg,
            stage_options=s1_opts,
        )
        s1_data = _extract_json_from_text(s1_raw) or _extract_json_from_text(s1_think)
        s1_cost = time.time() - t0

        if s1_data and isinstance(s1_data, dict):
            # 保证 canvas 顶级对象物理自包含与严密自愈
            if "canvas" not in s1_data or not isinstance(s1_data["canvas"], dict):
                s1_data["canvas"] = {}
            c_obj = s1_data["canvas"]
            try:
                parsed_asp = float(c_obj.get("aspect_ratio", 0))
                c_obj["aspect_ratio"] = parsed_asp if 0.1 <= parsed_asp <= 10.0 else native_aspect
            except (ValueError, TypeError):
                c_obj["aspect_ratio"] = native_aspect
            c_obj["orientation"] = str(c_obj.get("orientation") or orientation)
            c_obj["width"] = int(c_obj.get("width") or orig_w)
            c_obj["height"] = int(c_obj.get("height") or orig_h)
            c_obj["coordinate_space"] = "normalized_uv_top_left"

        # Debug 记录 Stage 1 (01_stage1_...)
        _save_debug_file(debug_dir, "01_stage1_prompt_system.txt", STAGE1_SYSTEM_PROMPT)
        _save_debug_file(debug_dir, "01_stage1_prompt_user.txt", s1_user_prompt)
        _save_debug_file(debug_dir, "01_stage1_raw_response.txt", f"=== THINKING ({len(s1_think)} chars) ===\n{s1_think}\n\n=== RESPONSE ===\n{s1_raw}")
        _save_debug_file(debug_dir, "01_stage1_parsed.json", s1_data or {"error": "failed to parse"})

        if not s1_data:
            print(f"[VLM Stage 1/5] ⚠️ 阶段 1 解析失败 ({s1_cost:.2f}s)，尝试平滑降级至极速模式")
            return self.run_fast(img_bytes, filename, debug_dir=debug_dir, geo_context=geo_context)

        scene_type = str(s1_data.get("scene_type") or "landscape").strip()
        season_light = str(s1_data.get("season_and_light") or "").strip()
        mood = str(s1_data.get("emotional_mood") or "").strip()
        subjects = s1_data.get("subjects") or []
        spatial = s1_data.get("spatial_structure") or {}
        phys = s1_data.get("physical_reality") or {}
        foci = s1_data.get("saliency_foci") or []
        hero_focus = foci[0] if (foci and isinstance(foci, list) and len(foci) > 0 and isinstance(foci[0], dict)) else (s1_data.get("protagonist") or (subjects[0] if subjects else {}))

        print(f"[VLM Stage 1/5] ✅ 场景: {scene_type} | 氛围: {season_light or mood} | 耗时: {s1_cost:.2f}s")
        hero_desc = None
        if hero_focus and isinstance(hero_focus, dict) and hero_focus.get("label"):
            c = hero_focus.get("center") or [0.5, 0.5]
            lbl = hero_focus.get("label")
            hero_desc = f"{lbl} @ ({c[0]:.2f}, {c[1]:.2f})"
            print(f"[VLM Stage 1/5] 🌟 核心主角: {hero_desc}")

        raw_pal = s1_data.get("palette", {})
        palette = {
            "dominant": _hex_to_rgb(raw_pal.get("dominant"), (90, 120, 70)),
            "dark":     _hex_to_rgb(raw_pal.get("dark"),     (40, 55, 35)),
            "neutral":  _hex_to_rgb(raw_pal.get("neutral"),  (160, 175, 190)),
            "accent":   _hex_to_rgb(raw_pal.get("accent"),   (160, 90, 50)),
        }
        _report(
            "[VLM 1/5]",
            f"🔍 场景: {scene_type} | 主角: {hero_desc or '自然地貌'}",
            scene_type=scene_type,
            mood=season_light or mood,
            hero_focus=hero_desc,
            palette_hex=raw_pal,
        )

        # -------------------------------------------------------------------
        # Stage 2: 文学策展与诗性标题 [40%]
        # -------------------------------------------------------------------
        s2_opts = self._get_stage_options("stage2_curatorial")
        if s2_opts.get("is_default"):
            print(f"[VLM Stage 2/5] [40%] ✍️ 正在提炼画廊级英文标题与诗性副标 (Thinking: DEFAULT | Mode: Raw AI Defaults)...")
        else:
            print(f"[VLM Stage 2/5] [40%] ✍️ 正在提炼画廊级英文标题与诗性副标 (Thinking: {s2_opts['level'].upper()} | Budget: {s2_opts['max_thinking_tokens']} tok | Temp: {s2_opts['temperature']})...")
        t0 = time.time()
        s2_user_prompt = build_stage2_user_prompt(s1_data, geo_context=geo_context)
        s2_raw, s2_think = self.provider.generate(
            img_bytes,
            STAGE2_SYSTEM_PROMPT,
            s2_user_prompt,
            self.vlm_cfg,
            stage_options=s2_opts,
        )
        s2_data = _extract_json_from_text(s2_raw) or _extract_json_from_text(s2_think) or {}
        if not s2_data or not s2_data.get("title"):
            fallback_s2 = _extract_curatorial_fallback_from_text(s2_raw, s2_think)
            if fallback_s2:
                s2_data = {**s2_data, **fallback_s2}
        s2_cost = time.time() - t0

        # Debug 记录 Stage 2 (02_stage2_...)
        _save_debug_file(debug_dir, "02_stage2_prompt_system.txt", STAGE2_SYSTEM_PROMPT)
        _save_debug_file(debug_dir, "02_stage2_prompt_user.txt", s2_user_prompt)
        _save_debug_file(debug_dir, "02_stage2_raw_response.txt", f"=== THINKING ({len(s2_think)} chars) ===\n{s2_think}\n\n=== RESPONSE ===\n{s2_raw}")
        _save_debug_file(debug_dir, "02_stage2_parsed.json", s2_data)

        title = str(s2_data.get("title") or "").strip()
        subtitle = str(s2_data.get("subtitle") or "").strip()
        title_layout = str(s2_data.get("title_layout") or "center").strip()
        if title_layout not in ("center", "left"):
            title_layout = "center"

        if not title:
            if hero_focus and isinstance(hero_focus, dict) and hero_focus.get("label"):
                title = f"{scene_type.upper()} & {hero_focus.get('label', '').split()[-1].upper()}"
            else:
                title = f"SILENT {scene_type.upper()}"
        if not subtitle and season_light:
            subtitle = season_light

        print(f"[VLM Stage 2/5] ✅ 标题: \"{title}\" | 副标: \"{subtitle}\" | 耗时: {s2_cost:.2f}s")
        _report(
            "[VLM 2/5]",
            f"✍️ 策展标题: \"{title}\" | 副标: \"{subtitle}\"",
            title=title,
            subtitle=subtitle,
        )

        # -------------------------------------------------------------------
        # Stage 3: 核心主焦点艺术造型理论特征抽象 [60%]
        # -------------------------------------------------------------------
        s3_opts = self._get_stage_options("stage3_art_theory")
        if s3_opts.get("is_default"):
            print(f"[VLM Stage 3/5] [60%] 🎨 正在深度解构核心主焦点艺术造型理论特征 (Thinking: DEFAULT | Mode: Raw AI Defaults)...")
        else:
            print(f"[VLM Stage 3/5] [60%] 🎨 正在深度解构核心主焦点艺术造型理论特征 (Thinking: {s3_opts['level'].upper()} | Budget: {s3_opts['max_thinking_tokens']} tok | Temp: {s3_opts['temperature']})...")
        t0 = time.time()
        s3_features_user_prompt = build_stage3_features_user_prompt(s1_data, s2_data, geo_context=geo_context)
        s3_f_raw, s3_f_think = self.provider.generate(
            img_bytes,
            STAGE3_FEATURES_SYSTEM_PROMPT,
            s3_features_user_prompt,
            self.vlm_cfg,
            stage_options=s3_opts,
        )
        s3_features_data = _extract_json_from_text(s3_f_raw) or _extract_json_from_text(s3_f_think)
        s3_f_cost = time.time() - t0

        if not s3_features_data or not isinstance(s3_features_data, dict) or "kandinsky_elemental_grammar" not in s3_features_data:
            print(f"[VLM Stage 3/5] ⚠️ 阶段 3 未返回完整造型理论 JSON ({s3_f_cost:.2f}s)，自动触发 Local CV 造型规则推导")
            s3_features_data = _synthesize_focus_features_fallback(s1_data, s2_data)

        # Debug 记录 Stage 3 特征 (03_stage3_...)
        _save_debug_file(debug_dir, "03_stage3_prompt_system.txt", STAGE3_FEATURES_SYSTEM_PROMPT)
        _save_debug_file(debug_dir, "03_stage3_prompt_user.txt", s3_features_user_prompt)
        _save_debug_file(debug_dir, "03_stage3_raw_response.txt", f"=== THINKING ({len(s3_f_think)} chars) ===\n{s3_f_think}\n\n=== RESPONSE ===\n{s3_f_raw}")
        _save_debug_file(debug_dir, "03_stage3_focus_features.json", s3_features_data)

        concept_title = s3_features_data.get("curatorial_abstract_metaphor", {}).get("formal_concept_title", "FORMAL ABSTRACTION")
        print(f"[VLM Stage 3/5] ✅ 抽象概念: \"{concept_title}\" | 耗时: {s3_f_cost:.2f}s (已保留 03_stage3_focus_features.json)")
        _report(
            "[VLM 3/5]",
            f"🎨 艺术理论: \"{concept_title}\" (康定斯基/克利)",
            concept_title=concept_title,
            art_theory="Kandinsky & Klee Abstraction",
        )

        # -------------------------------------------------------------------
        # Stage 4: 几何图元与抽色美学工序 [80%]
        # -------------------------------------------------------------------
        print(f"[Stage 4/5] [80%] 🧩 启动 CPU 高精几何剖分与抽色美学工序...")
        layout_style = str(self.vlm_cfg.get("layout_style", "")).strip().lower()
        motif_engine = str(self.vlm_cfg.get("motif_engine", "hybrid")).strip().lower()
        primitive_cfg = self.vlm_cfg.get("primitive", {})

        if layout_style in ("architectural_line", "minimal_line"):
            print(f"│ 🏛️ 选用细线草图风格 ({layout_style})，直接复用空间焦点与造型事实，跳过冗余晶格拟合")
            svg_code = None
            s4_data = {"engine": "spatial_line_art", "directives": s1_data, "focus_features": s3_features_data}
            s4_cost = 0.0
        elif motif_engine in ("hybrid", "primitive"):
            gen_type = str(self.vlm_cfg.get("generator_type", "triangle")).strip().lower()
            if gen_type in ("triangle", "delaunay"):
                gen_cfg = self.vlm_cfg.get("triangle", {})
                pts = gen_cfg.get("points") or gen_cfg.get("pts", 2500)
                print(f"│ ▲ Triangle Delaunay 高精三角面片剖分 (采样点: {pts} 个, 并发: {gen_cfg.get('concurrency', 10)})...")
            else:
                gen_cfg = self.vlm_cfg.get("primitive", {})
                num_s = gen_cfg.get("num_shapes", 220)
                s_type = gen_cfg.get("shape_type", "triangle")
                print(f"│ 🧩 Primitive 爬山图元拟合 (模式: {s_type}, 图元: {num_s} 个)...")

            t0 = time.time()
            raw_svg_code = generate_motif_svg(
                image_input=img_bytes,
                generator_type=gen_type,
                generator_config=gen_cfg,
                palette=palette,
                directives=s1_data,
            )
            s4_cost = time.time() - t0
            s4_data = {"engine": f"motif_{gen_type}", "config": gen_cfg, "directives": s1_data}

            # 1. 记录未经抽色的原生全彩 SVG 过程文件 (阶段 4-0)
            _save_debug_file(debug_dir, "04_00_stage4_artwork_raw.svg", raw_svg_code)

            # 2. 检查是否开启主体聚焦抽色 (Selective Chromatic Pop)
            sel_cfg = gen_cfg.get("selective_color") or self.vlm_cfg.get("selective_color", {})
            if raw_svg_code and sel_cfg.get("enable", True):
                def _dbg_saver(fname, content):
                    _save_debug_file(debug_dir, fname, content)

                selective_svg_code, sel_stats = apply_selective_color_pipeline(
                    raw_svg_code,
                    directives=s1_data,
                    config=sel_cfg,
                    save_debug_fn=_dbg_saver if debug_dir else None,
                )
                svg_code = selective_svg_code
            else:
                print(f"│ 🎨 [抽色美学工序] 抽色总开关处于关闭状态 (enable: false)，使用原生全彩几何矢量代码")
                svg_code = raw_svg_code
                _save_debug_file(debug_dir, "04_stage4_artwork_final.svg", raw_svg_code)
        else:
            domain_key = s1_data.get("morphology_domain")
            if not domain_key:
                s1_str = str(s1_data).lower()
                if "city" in scene_type or "urban" in scene_type or "skyscraper" in s1_str:
                    domain_key = "urban_architecture"
                elif "temple" in s1_str or "pagoda" in s1_str or "statue" in s1_str or "roof" in s1_str:
                    domain_key = "classical_heritage"
                elif "tree" in s1_str or "forest" in s1_str or "branch" in s1_str:
                    domain_key = "botanical_trees"
                elif "sea" in scene_type or "water" in scene_type or "lake" in s1_str:
                    domain_key = "water_seascape"
                elif "street" in scene_type or "people" in s1_str or "person" in s1_str:
                    domain_key = "human_street_life"
                elif "horse" in s1_str or "sheep" in s1_str or "cow" in s1_str or "cattle" in s1_str:
                    domain_key = "animal_wildlife"
                else:
                    domain_key = "alpine_landscape"

            s4_opts = self._get_stage_options("stage4_svg_synthesis")
            s4_system_prompt = build_stage4_system_prompt(domain_key)
            if s4_opts.get("is_default"):
                print(f"│ 📐 匹配 [{domain_key}] 专属几何语法库，正在生成定制矢量 SVG (Thinking: DEFAULT | Mode: Raw AI Defaults)...")
            else:
                print(f"│ 📐 匹配 [{domain_key}] 专属几何语法库，正在生成定制矢量 SVG (Thinking: {s4_opts['level'].upper()} | Budget: {s4_opts['max_thinking_tokens']} tok)...")
            t0 = time.time()
            s4_user_prompt = build_stage4_user_prompt(s1_data, s2_data)
            s4_raw, s4_think = self.provider.generate(
                img_bytes,
                s4_system_prompt,
                s4_user_prompt,
                self.vlm_cfg,
                stage_options=s4_opts,
            )
            s4_data = _extract_json_from_text(s4_raw) or _extract_json_from_text(s4_think) or {}
            s4_cost = time.time() - t0

            svg_code = _extract_svg_code(s4_raw, s4_data) or _extract_svg_code(s4_think)
            if not svg_code:
                print(f"│ ⚠️ 未直接提取到有效 SVG，基于空间坐标自适应合成专属 SVG")
                svg_code = self._synthesize_svg_from_spatial(scene_type, spatial, subjects, palette)

            # Debug 记录 Stage 4 Prompt
            _save_debug_file(debug_dir, "04_stage4_prompt_system.txt", s4_system_prompt)
            _save_debug_file(debug_dir, "04_stage4_prompt_user.txt", s4_user_prompt)
            _save_debug_file(debug_dir, "04_stage4_raw_response.txt", f"=== THINKING ({len(s4_think)} chars) ===\n{s4_think}\n\n=== RESPONSE ===\n{s4_raw}")
            _save_debug_file(debug_dir, "04_stage4_artwork_final.svg", svg_code)

        _save_debug_file(debug_dir, "04_stage4_parsed.json", s4_data)

        if svg_code:
            print(f"[Stage 4/5] ✅ 成功生成定制 SVG 矢量代码 ({len(svg_code)} 字符) | 耗时: {s4_cost:.2f}s")
        else:
            print(f"[Stage 4/5] ✅ 细线草图模式：已完成空间地貌与核心主体焦点解构 | 耗时: {s4_cost:.2f}s")

        _report(
            "[VLM 4/5]",
            f"🧩 几何工序: 定制 SVG ({len(svg_code) if svg_code else 0} 字符)",
            geometry_mode=f"Delaunay/SVG ({layout_style or 'hybrid'})",
            svg_len=len(svg_code) if svg_code else 0,
        )

        return {
            "title": title,
            "subtitle": subtitle,
            "palette": palette,
            "svg": svg_code,
            "scene_type": scene_type,
            "title_layout": title_layout,
            "source": f"{self.provider_name}_progressive",
            "spatial_facts": s1_data,
            "focus_features": s3_features_data,
            "timings": {
                "stage1_s1": s1_cost,
                "stage2_s2": s2_cost,
                "stage3_s3": s3_f_cost,
                "stage4_s4": s4_cost,
                "vlm_total": time.time() - t_total_start,
            }
        }

    def run_fast(self, img_bytes: bytes, filename: str, debug_dir=None, geo_context=None, step_callback=None) -> dict | None:
        """单阶段极速优化模式 (直接输出 SVG)"""
        def _report(step_tag, msg, level=EventLevel.INFO, **details):
            if step_callback:
                step_callback(
                    ProgressEvent(
                        stage=PipelineStage.RENDERING,
                        level=level,
                        message=msg,
                        step_tag=step_tag,
                        details=details,
                    )
                )

        fast_opts = self._get_stage_options("fast_unified")
        _report("[VLM Fast]", f"⚡ 启动极速模式分析 (SVG 生成): {filename}", engine=self.provider_name)
        if fast_opts.get("is_default"):
            print(f"\n[VLM Fast] ⚡ 启动极速模式分析 (SVG 生成, Thinking: DEFAULT | Mode: Raw AI Defaults): {filename}")
        else:
            print(f"\n[VLM Fast] ⚡ 启动极速模式分析 (SVG 生成, Thinking: {fast_opts['level'].upper()} | Budget: {fast_opts['max_thinking_tokens']} tok): {filename}")
        t0 = time.time()
        fast_user_prompt = (
            f"{FAST_UNIFIED_USER_PROMPT}\n\nGeographical & Altitude Reality Context:\n{json.dumps(geo_context, ensure_ascii=False)}"
            if geo_context else FAST_UNIFIED_USER_PROMPT
        )
        content, thinking = self.provider.generate(
            img_bytes,
            FAST_UNIFIED_SYSTEM_PROMPT,
            fast_user_prompt,
            self.vlm_cfg,
            stage_options=fast_opts,
        )
        cost = time.time() - t0

        data = _extract_json_from_text(content) or _extract_json_from_text(thinking)

        # 解析真实图片画幅尺寸
        orig_w, orig_h, native_aspect = 1000, 1000, 1.0
        orientation = "landscape"
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(img_bytes)) as _test_im:
                orig_w, orig_h = _test_im.size
                native_aspect = round(orig_w / float(orig_h), 3) if orig_h > 0 else 1.0
                orientation = "square" if orig_w == orig_h else ("portrait" if orig_w < orig_h else "landscape")
        except Exception:
            pass

        if data and isinstance(data, dict):
            if "canvas" not in data or not isinstance(data["canvas"], dict):
                data["canvas"] = {}
            c_obj = data["canvas"]
            try:
                parsed_asp = float(c_obj.get("aspect_ratio", 0))
                c_obj["aspect_ratio"] = parsed_asp if 0.1 <= parsed_asp <= 10.0 else native_aspect
            except (ValueError, TypeError):
                c_obj["aspect_ratio"] = native_aspect
            c_obj["orientation"] = str(c_obj.get("orientation") or orientation)
            c_obj["width"] = int(c_obj.get("width") or orig_w)
            c_obj["height"] = int(c_obj.get("height") or orig_h)
            c_obj["coordinate_space"] = "normalized_uv_top_left"

        # Debug 记录 Fast 模式
        _save_debug_file(debug_dir, "02_fast_prompt_system.txt", FAST_UNIFIED_SYSTEM_PROMPT)
        _save_debug_file(debug_dir, "02_fast_prompt_user.txt", fast_user_prompt)
        _save_debug_file(debug_dir, "02_fast_raw_response.txt", f"=== THINKING ({len(thinking)} chars) ===\n{thinking}\n\n=== RESPONSE ===\n{content}")
        _save_debug_file(debug_dir, "02_fast_parsed.json", data or {"error": "failed to parse"})

        if not data:
            print(f"[VLM Fast] ⚠️ 极速模式未返回有效 JSON (耗时: {cost:.2f}s)")
            return None

        scene_type = str(data.get("scene_type") or "landscape").strip()
        title = str(data.get("title") or "SILENT DIALOGUE").strip()
        subtitle = str(data.get("subtitle") or "").strip()
        title_layout = str(data.get("title_layout") or "center").strip()
        if title_layout not in ("center", "left"):
            title_layout = "center"

        raw_pal = data.get("palette", {})
        palette = {
            "dominant": _hex_to_rgb(raw_pal.get("dominant"), (90, 120, 70)),
            "dark":     _hex_to_rgb(raw_pal.get("dark"),     (40, 55, 35)),
            "neutral":  _hex_to_rgb(raw_pal.get("neutral"),  (160, 175, 190)),
            "accent":   _hex_to_rgb(raw_pal.get("accent"),   (160, 90, 50)),
        }

        motif_engine = str(self.vlm_cfg.get("motif_engine", "hybrid")).strip().lower()
        primitive_cfg = self.vlm_cfg.get("primitive", {})
        if motif_engine in ("hybrid", "primitive"):
            svg_code = generate_primitive_svg(img_bytes, primitive_cfg, palette=palette, directives=data)
        else:
            svg_code = _extract_svg_code(content, data) or _extract_svg_code(thinking)
            if not svg_code:
                svg_code = self._synthesize_svg_from_spatial(scene_type, {}, [], palette)

        _save_debug_file(debug_dir, "02_fast_artwork.svg", svg_code)

        print(f"[VLM Fast] 👁️  场景: {scene_type} | 耗时: {cost:.2f}s")
        print(f"[VLM Fast] ✅ 标题: \"{title}\" | 副标: \"{subtitle}\"")
        print(f"[VLM Fast] 📐 生成定制 SVG ({len(svg_code)} 字符)\n")

        _report(
            "[VLM Fast]",
            f"✅ 场景: {scene_type} | 标题: \"{title}\"",
            scene_type=scene_type,
            title=title,
            subtitle=subtitle,
            palette_hex=raw_pal,
            svg_len=len(svg_code) if svg_code else 0,
        )

        return {
            "title": title,
            "subtitle": subtitle,
            "palette": palette,
            "svg": svg_code,
            "scene_type": scene_type,
            "title_layout": title_layout,
            "source": f"{self.provider_name}_fast",
        }

    def _synthesize_svg_from_spatial(self, scene_type: str, spatial: dict, subjects: list, palette: dict) -> str:
        """基于真实地貌与主体事实自适应生成专属定制 SVG (极高保真兜底)"""
        elements = []
        elements.append('<path d="M 8 20 Q 50 10 92 20 L 92 82 L 8 82 Z" fill="neutral" fill-opacity="0.5"/>')

        if scene_type in ("cityscape", "architecture"):
            elements.append('<rect x="32" y="38" width="12" height="44" fill="dark" opacity="0.9"/>')
            elements.append('<rect x="48" y="30" width="16" height="52" fill="dominant" opacity="0.95"/>')
            elements.append('<rect x="68" y="44" width="10" height="38" fill="dark" opacity="0.85"/>')
            elements.append('<line x1="8" y1="82" x2="92" y2="82" stroke="dark" stroke-width="1.5"/>')
        elif "street" in scene_type or "play" in str(spatial).lower() or any("mound" in str(s).lower() or "child" in str(s).lower() for s in subjects):
            elements.append('<path d="M 12 82 Q 50 35 88 82 Z" fill="dominant" fill-opacity="0.9"/>')
            elements.append('<circle cx="50" cy="62" r="9" fill="dark"/>')
            elements.append('<rect x="68" y="24" width="8" height="58" rx="2" fill="dark" opacity="0.8"/>')
            elements.append('<circle cx="68" cy="20" r="5" fill="accent"/>')
        else:
            axis_str = str(spatial.get("structural_axis") or "").lower()
            if "ridge" in axis_str or "snow" in str(spatial).lower() or any("climber" in str(s).lower() for s in subjects):
                elements.append('<path d="M 8 82 L 88 42 L 88 82 Z" fill="dominant" fill-opacity="0.9"/>')
                elements.append('<line x1="8" y1="82" x2="88" y2="42" stroke="dark" stroke-width="1.5"/>')
                elements.append('<line x1="45" y1="62" x2="45" y2="82" stroke="dark" stroke-width="1" opacity="0.6"/>')
                elements.append('<line x1="65" y1="52" x2="65" y2="82" stroke="dark" stroke-width="1" opacity="0.6"/>')
            else:
                elements.append('<path d="M 8 82 Q 35 48 65 60 T 92 50 L 92 82 Z" fill="neutral" fill-opacity="0.7"/>')
                elements.append('<path d="M 8 82 Q 30 65 60 52 T 92 68 L 92 82 Z" fill="dominant" fill-opacity="0.95"/>')

        for subj in subjects:
            if not isinstance(subj, dict):
                continue
            x = float(subj.get("x", 0.5)) * 100.0
            y = float(subj.get("y", 0.5)) * 100.0
            count = int(subj.get("count", 1))
            if count > 1:
                for i in range(min(count, 4)):
                    px = x + (i - (count-1)/2) * 6.0
                    elements.append(f'<circle cx="{px:.1f}" cy="{y:.1f}" r="2" fill="dark"/>')
                    elements.append(f'<circle cx="{px+1.5:.1f}" cy="{y-1.5:.1f}" r="1" fill="accent"/>')
            else:
                elements.append(f'<rect x="{x-1.5:.1f}" y="{y-6:.1f}" width="3" height="6" rx="0.5" fill="dark"/>')
                elements.append(f'<circle cx="{x:.1f}" cy="{y-7.5:.1f}" r="1.5" fill="accent"/>')

        body = "\n  ".join(elements)
        return f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">\n  {body}\n</svg>'
