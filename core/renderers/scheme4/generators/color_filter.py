"""
Scheme4 矢量级主体聚焦抽色与多阶段画廊美学管道 (Vector Multi-Stage Aesthetic Filter Pipeline)

解耦为 4 个清晰的独立工序（每个工序独立生效并生成专属过程态产物与详尽日志）：
- 工序 4.1 (Step 1): 主体聚焦抽色 (Selective Chromatic Pop) -> 06_01_stage4_selective_pop.svg
- 工序 4.2 (Step 2): 多主体视线引力场 (Visual Tension Bridge) -> 06_02_stage4_tension_bridge.svg
- 工序 4.3 (Step 3): 暗房冷矿青 / 暖砂岩色调微调 (Chromatic Tinting) -> 06_03_stage4_chromatic_tint.svg
- 工序 4.4 (Step 4): 象牙白底板 Alpha 渐隐融化 (Alpha Dissolve into Ivory) -> 06_04_stage4_alpha_dissolve.svg
- 最终汇聚产物 -> 06_stage4_artwork_selective.svg (若开启抽色) 与 05_stage4_artwork.svg
"""
import colorsys
import math
import re


def _parse_rgba_str(val: str) -> tuple[int, int, int, int] | None:
    """解析 rgba(...) 或 rgb(...) 或 #HEX 字符串"""
    if not val:
        return None
    val = val.strip().lower()
    
    # 1. rgba / rgb
    m = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", val)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if m.group(4) is not None:
            a_raw = float(m.group(4))
            alpha = int(a_raw if a_raw > 1.0 else a_raw * 255.0)
        else:
            alpha = 255
        return (r, g, b, max(0, min(255, alpha)))

    # 2. #HEX
    if val.startswith("#"):
        h = val.lstrip("#")
        try:
            if len(h) == 6:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
            elif len(h) == 8:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
        except ValueError:
            return None

    return None


class SaliencySubjectZone:
    """单个主体的紧致几何轮廓判定域"""

    def __init__(self, cx: float, cy: float, rx: float, ry: float, subject_type: str = "general"):
        self.cx = cx
        self.cy = cy
        self.rx = max(0.06, rx)
        self.ry = max(0.08, ry)
        self.subject_type = subject_type.lower()

    def normalized_distance(self, px: float, py: float) -> float:
        """计算归一化点 (px, py) 到主体外轮廓的归一化距离 (<=1.0 表示在主体轮廓内部)"""
        dx = (px - self.cx) / self.rx
        dy = (py - self.cy) / self.ry
        return math.hypot(dx, dy)


def _point_to_segment_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    """计算点 (px, py) 到线段 (x1, y1)-(x2, y2) 的距离以及在线段上的投影比例 t"""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-6:
        return math.hypot(px - x1, py - y1), 0.0
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y), t


def _build_subject_zones(directives: dict | None) -> list[SaliencySubjectZone]:
    """从大模型 directives 中提取真实紧致主体轮廓域，解决 BBox 虚大过宽问题"""
    zones = []
    if not directives or not isinstance(directives, dict):
        return [SaliencySubjectZone(0.50, 0.50, 0.20, 0.28, "general")]

    foci = directives.get("saliency_foci") or []
    if not isinstance(foci, list) or len(foci) == 0:
        prot = directives.get("protagonist") or {}
        if isinstance(prot, dict) and "x" in prot and "y" in prot:
            px = float(prot["x"]) / (1000.0 if float(prot["x"]) > 1.0 else 1.0)
            py = float(prot["y"]) / (1000.0 if float(prot["y"]) > 1.0 else 1.0)
            return [SaliencySubjectZone(px, py, 0.18, 0.26, "general")]
        return [SaliencySubjectZone(0.50, 0.50, 0.20, 0.28, "general")]

    for f in foci:
        if not isinstance(f, dict):
            continue

        stype = str(f.get("subject_type") or f.get("label") or "general").lower()
        kpts = f.get("keypoints") or []
        raw_center = f.get("center")
        raw_bbox = f.get("bbox")

        # 1. 优先根据骨架关键点 (keypoints) 提取真实轮廓跨度
        if isinstance(kpts, list) and len(kpts) >= 2:
            kx = [float(p[0]) / (1000.0 if float(p[0]) > 1.0 else 1.0) for p in kpts if isinstance(p, (list, tuple)) and len(p) >= 2]
            ky = [float(p[1]) / (1000.0 if float(p[1]) > 1.0 else 1.0) for p in kpts if isinstance(p, (list, tuple)) and len(p) >= 2]
            if kx and ky:
                span_x = max(kx) - min(kx)
                span_y = max(ky) - min(ky)
                cx = sum(kx) / len(kx)
                cy = sum(ky) / len(ky)
                
                if any(k in stype for k in ("human", "person", "portrait", "figure")):
                    rx = max(0.12, span_x * 0.60 + 0.08)
                    ry = max(0.18, span_y * 0.60 + 0.10)
                elif any(k in stype for k in ("tree", "botanical", "branch")):
                    rx = max(0.14, span_x * 0.65 + 0.09)
                    ry = max(0.18, span_y * 0.65 + 0.10)
                else:
                    rx = max(0.12, span_x * 0.60 + 0.08)
                    ry = max(0.14, span_y * 0.60 + 0.08)

                zones.append(SaliencySubjectZone(cx, cy, rx, ry, stype))
                continue

        # 2. 其次结合 center 与 bbox
        if raw_center and len(raw_center) == 2:
            cx = float(raw_center[0]) / (1000.0 if float(raw_center[0]) > 1.0 else 1.0)
            cy = float(raw_center[1]) / (1000.0 if float(raw_center[1]) > 1.0 else 1.0)
        else:
            cx, cy = 0.50, 0.50

        if raw_bbox and len(raw_bbox) == 4:
            b = [float(v) / (1000.0 if float(v) > 1.0 else 1.0) for v in raw_bbox]
            bx0, by0 = min(b[0], b[2]), min(b[1], b[3])
            bx1, by1 = max(b[0], b[2]), max(b[1], b[3])
            bw = bx1 - bx0
            bh = by1 - by0
            
            if any(k in stype for k in ("human", "person", "portrait")):
                rx = min(0.24, max(0.12, bw * 0.40))
                ry = min(0.38, max(0.18, bh * 0.45))
            else:
                rx = min(0.30, max(0.12, bw * 0.45))
                ry = min(0.35, max(0.14, bh * 0.45))
        else:
            rx, ry = 0.18, 0.26

        zones.append(SaliencySubjectZone(cx, cy, rx, ry, stype))

    return zones if zones else [SaliencySubjectZone(0.50, 0.50, 0.20, 0.28, "general")]


def _extract_tint_hue(directives: dict | None, default_hue: float = 0.58) -> float:
    """从调色板提取主导氛围色相 (默认 Slate 0.58 冷青灰)"""
    if not directives or not isinstance(directives, dict):
        return default_hue
    pal = directives.get("palette") or {}
    if isinstance(pal, dict):
        dom_hex = pal.get("dominant") or pal.get("neutral") or pal.get("dark")
        if dom_hex and isinstance(dom_hex, str) and dom_hex.startswith("#"):
            try:
                h_str = dom_hex.lstrip("#")
                r, g, b = int(h_str[0:2], 16), int(h_str[2:4], 16), int(h_str[4:6], 16)
                h, _, _ = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
                return h
            except Exception:
                pass
    return default_hue


def _get_svg_viewbox(svg_code: str) -> tuple[float, float, float, float]:
    """提取 SVG viewBox 或尺寸"""
    vb_match = re.search(r'viewBox=["\']([-+]?\d*\.?\d+(?:\s+[-+]?\d*\.?\d+){3})["\']', svg_code, re.IGNORECASE)
    if vb_match:
        vb_parts = [float(p) for p in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", vb_match.group(1))]
        vx0, vy0, vw, vh = vb_parts if len(vb_parts) == 4 else (0.0, 0.0, 100.0, 100.0)
    else:
        w_m = re.search(r'width=["\']?(\d+)', svg_code)
        h_m = re.search(r'height=["\']?(\d+)', svg_code)
        vw = float(w_m.group(1)) if w_m else 100.0
        vh = float(h_m.group(1)) if h_m else 100.0
        vx0, vy0 = 0.0, 0.0
    return vx0, vy0, max(1.0, vw), max(1.0, vh)


def apply_step1_selective_pop(
    svg_code: str,
    zones: list[SaliencySubjectZone],
    bg_sat: float = 0.08,
    feather: float = 0.15,
    bg_bright_factor: float = 1.02,
    hero_contrast_boost: float = 1.05,
) -> tuple[str, dict]:
    """工序 4.1: 基础主体留色与背景去饱和"""
    vx0, vy0, vw, vh = _get_svg_viewbox(svg_code)
    total_paths, hero_paths, bg_paths = 0, 0, 0

    def _transform(match):
        nonlocal total_paths, hero_paths, bg_paths
        total_paths += 1
        full_tag, fill_val, d_val = match.group(0), match.group(1), match.group(2)
        rgba = _parse_rgba_str(fill_val)
        if not rgba: return full_tag
        r, g, b, a = rgba

        coords = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", d_val)]
        poly_cx = sum(coords[0::2]) / (len(coords)//2) if len(coords)>=4 else vw*0.5
        poly_cy = sum(coords[1::2]) / (len(coords)//2) if len(coords)>=4 else vh*0.5
        norm_x, norm_y = (poly_cx - vx0) / vw, (poly_cy - vy0) / vh

        min_d = min(z.normalized_distance(norm_x, norm_y) for z in zones)
        if min_d <= 1.0:
            sat_factor = 1.0
            hero_paths += 1
        elif min_d >= 1.0 + feather:
            sat_factor = bg_sat
            bg_paths += 1
        else:
            t = (min_d - 1.0) / feather
            sat_factor = bg_sat + (1.0 - bg_sat) * (0.5 * (1.0 + math.cos(math.pi * t)))
            hero_paths += 1

        h_norm, l_norm, s_norm = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        new_s = s_norm * sat_factor
        new_l = min(0.96, l_norm * bg_bright_factor) if sat_factor < 0.5 else max(0.05, min(0.95, l_norm * hero_contrast_boost))
        nr, ng, nb = colorsys.hls_to_rgb(h_norm, new_l, new_s)
        new_rgba = f"rgba({int(nr*255)},{int(ng*255)},{int(nb*255)},{a})"
        
        tag = re.sub(r'fill=["\'][^"\']+["\']', f'fill="{new_rgba}"', full_tag, count=1)
        if 'stroke=' in tag: tag = re.sub(r'stroke=["\'][^"\']+["\']', f'stroke="{new_rgba}"', tag, count=1)
        return tag

    res_svg = re.compile(r'<path\b[^>]*fill=["\']([^"\']+)["\'][^>]*d=["\']([^"\']+)["\'][^>]*>', re.I).sub(_transform, svg_code)
    return res_svg, {"hero_polygons": hero_paths, "bg_polygons": bg_paths, "total": total_paths}


def apply_step2_tension_bridge(
    svg_code: str,
    zones: list[SaliencySubjectZone],
    raw_svg_code: str | None = None,
    bridge_width: float = 0.16,
    bridge_sat: float = 0.30,
) -> tuple[str, dict]:
    """工序 5.2: 多主体视线引力场张力注入"""
    if len(zones) < 2:
        return svg_code, {"status": "skipped", "reason": "less_than_2_zones", "bridge_polygons": 0}

    vx0, vy0, vw, vh = _get_svg_viewbox(svg_code)
    bridge_count = 0

    # 若提供了 raw_svg_code，预先建立 path d -> 原生 RGB 映射
    raw_color_map = {}
    if raw_svg_code:
        for m in re.finditer(r'<path\b[^>]*fill=["\']([^"\']+)["\'][^>]*d=["\']([^"\']+)["\'][^>]*>', raw_svg_code, re.I):
            f_val, d_val = m.group(1), m.group(2)
            rgba_parsed = _parse_rgba_str(f_val)
            if rgba_parsed:
                raw_color_map[d_val.strip()] = rgba_parsed

    def _transform(match):
        nonlocal bridge_count
        full_tag, fill_val, d_val = match.group(0), match.group(1), match.group(2)
        d_key = d_val.strip()

        rgba = raw_color_map.get(d_key) or _parse_rgba_str(fill_val)
        if not rgba: return full_tag
        r, g, b, a = rgba

        coords = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", d_val)]
        poly_cx = sum(coords[0::2]) / (len(coords)//2) if len(coords)>=4 else vw*0.5
        poly_cy = sum(coords[1::2]) / (len(coords)//2) if len(coords)>=4 else vh*0.5
        norm_x, norm_y = (poly_cx - vx0) / vw, (poly_cy - vy0) / vh

        min_d = min(z.normalized_distance(norm_x, norm_y) for z in zones)
        if min_d <= 1.0:
            return full_tag  # 主体内部不受引力桥影响

        bridge_boost = 0.0
        for i in range(len(zones)):
            for j in range(i + 1, len(zones)):
                z1, z2 = zones[i], zones[j]
                dist_to_seg, t_proj = _point_to_segment_dist(norm_x, norm_y, z1.cx, z1.cy, z2.cx, z2.cy)
                if dist_to_seg <= bridge_width and 0.05 <= t_proj <= 0.95:
                    w = 0.5 * (1.0 + math.cos(math.pi * (dist_to_seg / bridge_width)))
                    bridge_boost = max(bridge_boost, w)

        if bridge_boost <= 0.0:
            return full_tag

        bridge_count += 1
        h_norm, l_norm, s_norm = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        new_s = s_norm * bridge_sat * bridge_boost
        nr, ng, nb = colorsys.hls_to_rgb(h_norm, l_norm, new_s)
        new_rgba = f"rgba({int(nr*255)},{int(ng*255)},{int(nb*255)},{a})"

        tag = re.sub(r'fill=["\'][^"\']+["\']', f'fill="{new_rgba}"', full_tag, count=1)
        if 'stroke=' in tag: tag = re.sub(r'stroke=["\'][^"\']+["\']', f'stroke="{new_rgba}"', tag, count=1)
        return tag

    res_svg = re.compile(r'<path\b[^>]*fill=["\']([^"\']+)["\'][^>]*d=["\']([^"\']+)["\'][^>]*>', re.I).sub(_transform, svg_code)
    return res_svg, {"status": "applied", "bridge_polygons": bridge_count}


def apply_step3_chromatic_tint(
    svg_code: str,
    zones: list[SaliencySubjectZone],
    ambient_hue: float,
    tint_strength: float = 0.18,
) -> tuple[str, dict]:
    """工序 4.3: 暗房冷矿青 / 暖砂岩色调微调"""
    vx0, vy0, vw, vh = _get_svg_viewbox(svg_code)
    tinted_count = 0

    def _transform(match):
        nonlocal tinted_count
        full_tag, fill_val, d_val = match.group(0), match.group(1), match.group(2)
        rgba = _parse_rgba_str(fill_val)
        if not rgba: return full_tag
        r, g, b, a = rgba

        coords = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", d_val)]
        poly_cx = sum(coords[0::2]) / (len(coords)//2) if len(coords)>=4 else vw*0.5
        poly_cy = sum(coords[1::2]) / (len(coords)//2) if len(coords)>=4 else vh*0.5
        norm_x, norm_y = (poly_cx - vx0) / vw, (poly_cy - vy0) / vh

        min_d = min(z.normalized_distance(norm_x, norm_y) for z in zones)
        if min_d <= 1.0:
            return full_tag  # 主体内部保留纯正原色

        h_norm, l_norm, s_norm = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        new_h = h_norm * (1.0 - tint_strength) + ambient_hue * tint_strength
        tinted_count += 1

        nr, ng, nb = colorsys.hls_to_rgb(new_h, l_norm, s_norm)
        new_rgba = f"rgba({int(nr*255)},{int(ng*255)},{int(nb*255)},{a})"

        tag = re.sub(r'fill=["\'][^"\']+["\']', f'fill="{new_rgba}"', full_tag, count=1)
        if 'stroke=' in tag: tag = re.sub(r'stroke=["\'][^"\']+["\']', f'stroke="{new_rgba}"', tag, count=1)
        return tag

    res_svg = re.compile(r'<path\b[^>]*fill=["\']([^"\']+)["\'][^>]*d=["\']([^"\']+)["\'][^>]*>', re.I).sub(_transform, svg_code)
    return res_svg, {"status": "applied", "tinted_polygons": tinted_count, "ambient_hue": ambient_hue}


def apply_step4_alpha_dissolve(
    svg_code: str,
    zones: list[SaliencySubjectZone],
    feather: float = 0.15,
    bg_min_alpha: float = 0.35,
    fade_feather: float = 0.40,
) -> tuple[str, dict]:
    """工序 4.4: 象牙白底板 Alpha 渐隐融化"""
    vx0, vy0, vw, vh = _get_svg_viewbox(svg_code)
    dissolved_count = 0

    def _transform(match):
        nonlocal dissolved_count
        full_tag, fill_val, d_val = match.group(0), match.group(1), match.group(2)
        rgba = _parse_rgba_str(fill_val)
        if not rgba: return full_tag
        r, g, b, a_orig = rgba

        coords = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", d_val)]
        poly_cx = sum(coords[0::2]) / (len(coords)//2) if len(coords)>=4 else vw*0.5
        poly_cy = sum(coords[1::2]) / (len(coords)//2) if len(coords)>=4 else vh*0.5
        norm_x, norm_y = (poly_cx - vx0) / vw, (poly_cy - vy0) / vh

        min_d = min(z.normalized_distance(norm_x, norm_y) for z in zones)
        if min_d <= 1.0 + feather:
            alpha_factor = 1.0
        else:
            fade_t = min(1.0, (min_d - (1.0 + feather)) / fade_feather)
            alpha_factor = 1.0 - (1.0 - bg_min_alpha) * (0.5 * (1.0 - math.cos(math.pi * fade_t)))
            dissolved_count += 1

        out_a = max(0, min(255, int(a_orig * alpha_factor)))
        new_rgba = f"rgba({r},{g},{b},{out_a})"

        tag = re.sub(r'fill=["\'][^"\']+["\']', f'fill="{new_rgba}"', full_tag, count=1)
        if 'stroke=' in tag: tag = re.sub(r'stroke=["\'][^"\']+["\']', f'stroke="{new_rgba}"', tag, count=1)
        return tag

    res_svg = re.compile(r'<path\b[^>]*fill=["\']([^"\']+)["\'][^>]*d=["\']([^"\']+)["\'][^>]*>', re.I).sub(_transform, svg_code)
    return res_svg, {"status": "applied", "dissolved_polygons": dissolved_count, "bg_min_alpha": bg_min_alpha}


def apply_selective_color_pipeline(
    raw_svg_code: str,
    directives: dict | None = None,
    config: dict | None = None,
    save_debug_fn = None,
) -> tuple[str, dict]:
    """
    执行画廊级多工序抽色美学管道，并在开启对应子项时，独立生成并落盘专属过程文件
    
    :param raw_svg_code: 原始全彩 SVG 源码
    :param directives: AI 结构化空间事实
    :param config: selective_color 配置节
    :param save_debug_fn: debug 存储回调函数 `save_debug_fn(filename, content)`
    :return: (final_selective_svg, summary_stats)
    """
    if not raw_svg_code or "<svg" not in raw_svg_code:
        return raw_svg_code, {"status": "skipped", "reason": "invalid_svg"}

    cfg = config or {}
    enable = bool(cfg.get("enable", True))
    if not enable:
        return raw_svg_code, {"status": "skipped", "reason": "disabled_by_config"}

    # 1. 基础配置
    bg_sat = max(0.0, min(1.0, float(cfg.get("bg_saturation", 0.08))))
    feather = max(0.02, min(0.60, float(cfg.get("feather", 0.18))))
    bg_bright = float(cfg.get("bg_brightness_factor", 1.02))
    hero_boost = float(cfg.get("hero_contrast_boost", 1.05))

    # 子工序配置
    alpha_cfg = cfg.get("alpha_fade", {})
    alpha_enable = bool(alpha_cfg.get("enable", True))

    tint_cfg = cfg.get("chromatic_tint", {})
    tint_enable = bool(tint_cfg.get("enable", True))

    bridge_cfg = cfg.get("tension_bridge", {})
    bridge_enable = bool(bridge_cfg.get("enable", True))

    # 2. 构建紧致主体轮廓域
    zones = _build_subject_zones(directives)
    current_svg = raw_svg_code
    pipeline_stats = {"status": "applied", "steps_executed": []}

    print(f"│ 🎨 [抽色美学工序] 启动解耦式画廊矢量渲染管道 (共检测到 {len(zones)} 处主体判定域)")

    # ── 工序 4.1: 主体留色与背景去饱和 (Step 1) ──
    # 如果开启引力桥，在判定背景时将引力桥区域保护并保留 bridge_sat 饱和度
    current_svg, s1_stat = apply_step1_selective_pop(
        current_svg, zones, bg_sat=bg_sat, feather=feather, bg_bright_factor=bg_bright, hero_contrast_boost=hero_boost
    )
    pipeline_stats["step1_selective_pop"] = s1_stat
    pipeline_stats["steps_executed"].append("step1_selective_pop")
    print(f"│   ├─ [工序 4.1: 主体聚焦留色] 保留主体 {s1_stat['hero_polygons']:,} 面片 | 背景去饱和 {s1_stat['bg_polygons']:,} 面片 (饱和度: {bg_sat:.2f})")
    if save_debug_fn:
        save_debug_fn("04_01_stage4_selective_pop.svg", current_svg)

    # ── 工序 4.2: 多主体视线引力桥 (Step 2) ──
    if bridge_enable and len(zones) >= 2:
        b_width = max(0.05, min(0.35, float(bridge_cfg.get("bridge_width", 0.16))))
        b_sat = max(bg_sat, min(0.80, float(bridge_cfg.get("bridge_saturation", 0.30))))
        # 从 raw_svg_code 中读取原始多边形色彩并在当前画布上对引力桥区域进行张力色彩还原
        current_svg, s2_stat = apply_step2_tension_bridge(
            current_svg, zones, raw_svg_code=raw_svg_code, bridge_width=b_width, bridge_sat=b_sat
        )
        pipeline_stats["step2_tension_bridge"] = s2_stat
        if s2_stat.get("status") == "applied":
            pipeline_stats["steps_executed"].append("step2_tension_bridge")
            print(f"│   ├─ [工序 4.2: 视线引力通道] 在主体连线上注入 {s2_stat['bridge_polygons']:,} 处张力面片 (保留 {b_sat*100:.0f}% 饱和度)")
            if save_debug_fn:
                save_debug_fn("04_02_stage4_tension_bridge.svg", current_svg)
    else:
        pipeline_stats["step2_tension_bridge"] = {"status": "disabled"}

    # ── 工序 4.3: 胶片暗房冷暖色相微调 (Step 3) ──
    if tint_enable:
        t_strength = max(0.0, min(0.6, float(tint_cfg.get("tint_strength", 0.18))))
        amb_hue = _extract_tint_hue(directives)
        current_svg, s3_stat = apply_step3_chromatic_tint(current_svg, zones, ambient_hue=amb_hue, tint_strength=t_strength)
        pipeline_stats["step3_chromatic_tint"] = s3_stat
        pipeline_stats["steps_executed"].append("step3_chromatic_tint")
        print(f"│   ├─ [工序 4.3: 暗房色相微调] 为背景 {s3_stat['tinted_polygons']:,} 面片注入 {t_strength*100:.0f}% 胶片矿物底色 (Hue: {amb_hue:.2f})")
        if save_debug_fn:
            save_debug_fn("04_03_stage4_chromatic_tint.svg", current_svg)
    else:
        pipeline_stats["step3_chromatic_tint"] = {"status": "disabled"}

    # ── 工序 4.4: 象牙白底板 Alpha 渐隐融化 (Step 4) ──
    if alpha_enable:
        bg_min_a = max(0.0, min(1.0, float(alpha_cfg.get("bg_min_alpha", 0.35))))
        fade_f = max(0.1, min(1.0, float(alpha_cfg.get("fade_feather", 0.40))))
        current_svg, s4_stat = apply_step4_alpha_dissolve(
            current_svg, zones, feather=feather, bg_min_alpha=bg_min_a, fade_feather=fade_f
        )
        pipeline_stats["step4_alpha_dissolve"] = s4_stat
        pipeline_stats["steps_executed"].append("step4_alpha_dissolve")
        print(f"│   ├─ [工序 4.4: 象牙底板渐隐] 边缘 {s4_stat['dissolved_polygons']:,} 面片透明度向外衰减至 {bg_min_a*100:.0f}% (融化象牙白底板)")
        if save_debug_fn:
            save_debug_fn("04_04_stage4_alpha_dissolve.svg", current_svg)
    else:
        pipeline_stats["step4_alpha_dissolve"] = {"status": "disabled"}

    # 汇总产物 (04_stage4_artwork_final.svg 与 04_stage4_pipeline_stats.json)
    if save_debug_fn:
        save_debug_fn("04_stage4_artwork_final.svg", current_svg)
        save_debug_fn("04_stage4_pipeline_stats.json", pipeline_stats)

    print(f"│   └─ [工序完成] 最终艺术矢量汇聚完成 (共执行 {len(pipeline_stats['steps_executed'])} 项独立美学工序)")
    return current_svg, pipeline_stats


# 兼容接口
def apply_selective_color_filter(
    svg_code: str,
    directives: dict | None = None,
    config: dict | None = None,
) -> tuple[str, dict]:
    return apply_selective_color_pipeline(svg_code, directives=directives, config=config, save_debug_fn=None)
