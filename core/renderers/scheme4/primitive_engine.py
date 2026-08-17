"""
Scheme4 通用参数化事实几何图元引擎 (Universal Saliency Primitive Engine)

核心目标：
- 零场景硬编码：基于大模型实时解构的《动态几何指引协议》（含主体 BBox、显著性权重、构图主轴与锐度张力），纯参数化通用求解。
- 动态显著性加权矩阵：将 15~25 倍优化权重聚焦在主体区域，彻底解决“主体被忽略、细节缺失”的问题。
- 多尺度金字塔图元拟合：
  * Pass 1: 宏观地貌切面 (3~6 个图元)，基于真实地貌倾角与地平线拟合宏观大地骨架；
  * Pass 2: 显著性微观精修 (25~45 个图元)，密集生成硬边多边形、定向细骨架或散点几何，极致刻画主体轮廓。
- 彻底去除封闭小方框底色：图元悬浮于象牙白底板 (#F3F0E8)，实现 70% 画廊级纯净留白呼吸感。
"""

import io
import math
import os
import random
import shutil
import subprocess
import tempfile
import numpy as np
from PIL import Image, ImageDraw


def _clamp(val, min_val, max_val):
    return max(min_val, min(max_val, val))


def _norm_coord(v) -> float:
    """自适应将 [0.0, 1.0]、千分制 [0, 1000] 或其他坐标无损归一化到 [0.0, 1.0]"""
    try:
        val = float(v)
    except (ValueError, TypeError):
        return 0.5
    if val < 0.0:
        return 0.0
    if val <= 1.0:
        return val
    if val <= 1000.0:
        return val / 1000.0
    # 若大于 1000 则限制为 1.0
    return min(1.0, val / 1000.0)


class PythonPrimitiveOptimizer:
    """
    通用参数化显著性爬山几何图元拟合器 (General Saliency-Guided Primitive Optimizer)
    """

    def __init__(
        self,
        target_img: Image.Image,
        num_shapes: int = 36,
        shape_type: str = "combo",
        alpha: int = 200,
        sample_size: int = 256,
        candidate_count: int = 60,
        mutate_steps: int = 16,
        directives: dict | None = None,
    ):
        self.num_shapes = max(6, min(500, num_shapes))
        self.shape_type = shape_type.lower().strip()
        self.alpha = max(30, min(255, alpha))
        self.sample_size = max(64, min(512, sample_size))
        self.candidate_count = max(20, candidate_count)
        self.mutate_steps = max(0, mutate_steps)
        self.directives = directives or {}

        # 1. 准备目标图像并保持宽高比降采样
        orig_w, orig_h = target_img.size
        scale = self.sample_size / max(orig_w, orig_h)
        self.w = max(16, int(orig_w * scale))
        self.h = max(16, int(orig_h * scale))

        resample_filter = getattr(Image.Resampling, "LANCZOS", Image.BILINEAR)
        resized = target_img.convert("RGB").resize((self.w, self.h), resample_filter)
        self.target_np = np.asarray(resized, dtype=np.float32)

        # 2. 从指令中读取几何微调参数
        geo_tuning = self.directives.get("geometry_tuning", {})
        self.angularity = float(geo_tuning.get("angularity", 0.85))
        self.transparent = geo_tuning.get("background_treatment", "transparent") == "transparent"

        # 3. 计算 Sobel 边缘梯度图 (Edge Gradient Energy Map)
        lum = 0.299 * self.target_np[:, :, 0] + 0.587 * self.target_np[:, :, 1] + 0.114 * self.target_np[:, :, 2]
        gy, gx = np.gradient(lum)
        grad_mag = np.sqrt(gx**2 + gy**2)
        max_grad = np.max(grad_mag) if np.max(grad_mag) > 0 else 1.0
        self.edge_grad_map = grad_mag / max_grad

        # 4. 构建动态显著性热力图权重矩阵 (结合 Sobel 边缘能量 2.5x 赋权)
        self.weight_map, self.saliency_boxes = self._build_saliency_weight_map()

        # 5. 初始化画布状态
        avg_r = np.mean(self.target_np[:, :, 0])
        avg_g = np.mean(self.target_np[:, :, 1])
        avg_b = np.mean(self.target_np[:, :, 2])
        self.bg_color = (int(avg_r), int(avg_g), int(avg_b))

        self.current_img = Image.new("RGBA", (self.w, self.h), (*self.bg_color, 255))
        self.current_np = np.asarray(self.current_img.convert("RGB"), dtype=np.float32)

        # 加权当前得分
        diff = self.current_np - self.target_np
        self.current_score = np.sum((diff ** 2) * self.weight_map[:, :, np.newaxis]) / (self.w * self.h * 3)

        self.recorded_shapes = []

    def _build_saliency_weight_map(self) -> tuple[np.ndarray, list[dict]]:
        """根据大模型实时解析的 saliency_foci 与 protagonist 构建像素级加权热力图"""
        weight_map = np.ones((self.h, self.w), dtype=np.float32)
        boxes = []

        # 1. 优先读取 saliency_foci 列表
        foci = self.directives.get("saliency_foci") or []
        if not isinstance(foci, list) or len(foci) == 0:
            # 兼容旧版 protagonist 格式
            prot = self.directives.get("protagonist") or {}
            if isinstance(prot, dict) and "x" in prot and "y" in prot:
                px = float(prot.get("x", 0.5))
                py = float(prot.get("y", 0.5))
                foci = [{
                    "label": prot.get("label", "focal_subject"),
                    "bbox": [max(0.0, px - 0.15), max(0.0, py - 0.15), min(1.0, px + 0.15), min(1.0, py + 0.15)],
                    "center": [px, py],
                    "weight": 18.0,
                    "geometry_style": "scattered_facets",
                }]

        for f in foci:
            if not isinstance(f, dict):
                continue
            bbox = f.get("bbox")
            weight = float(f.get("weight", 16.0))
            style = str(f.get("geometry_style", "scattered_facets")).strip()
            subject_type = str(f.get("subject_type", "")).strip().lower()
            posture = str(f.get("posture_or_gesture", "")).strip()
            raw_kpts = f.get("keypoints", [])
            label = str(f.get("label", "")).strip()

            # 智能推断 subject_type (如果大模型未提供明确类型)
            if not subject_type:
                lbl_lower = (label + " " + style).lower()
                if any(w in lbl_lower for w in ("person", "human", "climber", "figure", "traveler", "child", "man", "woman")):
                    subject_type = "human"
                elif any(w in lbl_lower for w in ("bird", "eagle", "seagull", "avian", "fly")):
                    subject_type = "bird"
                elif any(w in lbl_lower for w in ("horse", "cow", "cattle", "sheep", "animal", "deer", "wildlife", "dog")):
                    subject_type = "animal"
                elif any(w in lbl_lower for w in ("tree", "branch", "wood", "spire", "forest", "flora", "plant")):
                    subject_type = "tree"
                elif any(w in lbl_lower for w in ("peak", "mountain", "snow", "ridge", "cliff", "rock")):
                    subject_type = "mountain"
                elif any(w in lbl_lower for w in ("eave", "roof", "building", "temple", "pagoda", "architecture", "house", "tower")):
                    subject_type = "architecture"
                elif any(w in lbl_lower for w in ("boat", "canoe", "vessel", "ship", "sail", "car")):
                    subject_type = "vessel"
                else:
                    subject_type = "other"

            if isinstance(bbox, list) and len(bbox) == 4:
                bx0 = _norm_coord(bbox[0]) * self.w
                by0 = _norm_coord(bbox[1]) * self.h
                bx1 = _norm_coord(bbox[2]) * self.w
                by1 = _norm_coord(bbox[3]) * self.h
                x0 = int(min(bx0, bx1))
                y0 = int(min(by0, by1))
                x1 = int(max(bx0, bx1))
                y1 = int(max(by0, by1))
            else:
                raw_c = f.get("center", [0.5, 0.5])
                cx = _norm_coord(raw_c[0] if isinstance(raw_c, (list, tuple)) and len(raw_c) > 0 else 0.5) * self.w
                cy = _norm_coord(raw_c[1] if isinstance(raw_c, (list, tuple)) and len(raw_c) > 1 else 0.5) * self.h
                x0 = int(cx - 0.15 * self.w)
                y0 = int(cy - 0.15 * self.h)
                x1 = int(cx + 0.15 * self.w)
                y1 = int(cy + 0.15 * self.h)

            x0 = _clamp(x0, 0, self.w)
            y0 = _clamp(y0, 0, self.h)
            x1 = _clamp(max(x0 + 4, x1), 0, self.w)
            y1 = _clamp(max(y0 + 4, y1), 0, self.h)

            # 转换 keypoints 为物理画布像素坐标
            kpts = []
            if isinstance(raw_kpts, list):
                for pt in raw_kpts:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        kx = _norm_coord(pt[0]) * self.w
                        ky = _norm_coord(pt[1]) * self.h
                        kpts.append((kx, ky))

            # 在主体矩形范围内叠加显著性加权倍率 (结合 Sobel 边缘梯度强化 2.5x)
            local_grad = self.edge_grad_map[y0:y1, x0:x1] if hasattr(self, "edge_grad_map") else 0.0
            enhanced_weight = weight * (1.0 + 2.5 * local_grad)
            weight_map[y0:y1, x0:x1] = np.maximum(weight_map[y0:y1, x0:x1], enhanced_weight)
            boxes.append({
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "style": style,
                "subject_type": subject_type,
                "posture": posture,
                "keypoints": kpts,
                "label": label,
            })

        return weight_map, boxes

    def _random_shape(self, progress: float = 0.0, is_macro: bool = False) -> dict:
        """三阶段多尺度自适应退火图元生成：宏观大地切面 (0-20%) -> 中等结构 (20-55%) -> 超微晶格微雕 (55-100%)"""
        w, h = self.w, self.h

        # Stage 1: 宏观地貌与天空大体块 (0-20%)
        if is_macro or progress < 0.20:
            axis = self.directives.get("composition_axis", {})
            horizon_y = _norm_coord(axis.get("horizon_y", 0.5)) * h
            slope_deg = float(axis.get("slope_angle_deg", 0.0))

            if self.shape_type in ("triangle", "triangles"):
                y_mid = _clamp(horizon_y, 0, h)
                p1 = (0.0, _clamp(y_mid + random.uniform(-h * 0.15, h * 0.15), 0, h))
                p2 = (w, _clamp(y_mid + random.uniform(-h * 0.15, h * 0.15), 0, h))
                p3 = (_clamp(random.uniform(0, w), 0, w), h if random.random() < 0.5 else 0.0)
                return {"kind": "polygon", "points": [p1, p2, p3]}
            elif self.shape_type in ("polygon", "polygons"):
                rad = math.radians(slope_deg)
                dy = math.tan(rad) * (w / 2.0)
                y_left = _clamp(horizon_y - dy, 0, h)
                y_right = _clamp(horizon_y + dy, 0, h)
                pts = [(0.0, y_left), (w, y_right), (w, h), (0.0, h)]
                return {"kind": "polygon", "points": pts}
            else:
                return {
                    "kind": "polygon",
                    "points": [
                        (random.uniform(0, w), random.uniform(0, h)),
                        (random.uniform(0, w), random.uniform(0, h)),
                        (random.uniform(0, w), random.uniform(0, h)),
                    ]
                }

        # Stage 2 & 3: 显著性主体退火精雕 (Annealed Micro-Facet Carving)
        is_micro = progress >= 0.55  # 后 45% 进度全面进入超微晶格雕刻
        focus_prob = 0.92 if is_micro else 0.75

        if self.saliency_boxes and random.random() < focus_prob:
            box = random.choice(self.saliency_boxes)
            bx0, by0, bx1, by1 = box["x0"], box["y0"], box["x1"], box["y1"]
            bw = max(4, bx1 - bx0)
            bh = max(4, by1 - by0)

            # 残差与边缘双重引导定位 (Residual & Gradient Snapping)
            if is_micro and hasattr(self, "current_np") and random.random() < 0.70:
                crop_diff = np.sum((self.current_np[by0:by1, bx0:bx1] - self.target_np[by0:by1, bx0:bx1])**2, axis=-1)
                crop_diff *= (1.0 + 2.0 * self.edge_grad_map[by0:by1, bx0:bx1])
                if crop_diff.size > 0:
                    flat_idx = np.argmax(crop_diff)
                    ry, rx = np.unravel_index(flat_idx, crop_diff.shape)
                    cx = _clamp(bx0 + rx + random.uniform(-bw * 0.08, bw * 0.08), bx0, bx1)
                    cy = _clamp(by0 + ry + random.uniform(-bh * 0.08, bh * 0.08), by0, by1)
                else:
                    cx = random.uniform(bx0, bx1)
                    cy = random.uniform(by0, by1)
            else:
                cx = random.uniform(bx0, bx1)
                cy = random.uniform(by0, by1)

            # 尺度退火：微观晶格尺度缩小至 BBox 的 4% ~ 14%
            if is_micro:
                scale_w = max(2.0, bw * random.uniform(0.04, 0.14))
                scale_h = max(2.0, bh * random.uniform(0.04, 0.14))
            else:
                scale_w = max(4.0, bw * random.uniform(0.15, 0.35))
                scale_h = max(4.0, bh * random.uniform(0.15, 0.35))

            p1 = (_clamp(cx + random.uniform(-scale_w, scale_w), 0, w), _clamp(cy + random.uniform(-scale_h, scale_h), 0, h))
            p2 = (_clamp(cx + random.uniform(-scale_w, scale_w), 0, w), _clamp(cy + random.uniform(-scale_h, scale_h), 0, h))
            p3 = (_clamp(cx + random.uniform(-scale_w, scale_w), 0, w), _clamp(cy + random.uniform(-scale_h, scale_h), 0, h))
            return {"kind": "polygon", "points": [p1, p2, p3]}
        else:
            # 全局次要区域图元 (带有天空纯净度保护)
            axis = self.directives.get("composition_axis", {})
            horizon_y = _norm_coord(axis.get("horizon_y", 0.5)) * h
            cx = random.uniform(0, w)
            cy = random.uniform(0, h)
            if cy < horizon_y and random.random() < 0.80:
                cy = random.uniform(horizon_y, h)
            scale_w = w * random.uniform(0.10, 0.25)
            scale_h = h * random.uniform(0.10, 0.25)
            p1 = (_clamp(cx + random.uniform(-scale_w, scale_w), 0, w), _clamp(cy + random.uniform(-scale_h, scale_h), 0, h))
            p2 = (_clamp(cx + random.uniform(-scale_w, scale_w), 0, w), _clamp(cy + random.uniform(-scale_h, scale_h), 0, h))
            p3 = (_clamp(cx + random.uniform(-scale_w, scale_w), 0, w), _clamp(cy + random.uniform(-scale_h, scale_h), 0, h))
            return {"kind": "polygon", "points": [p1, p2, p3]}

        # 显著性主体微观图元 (Pass 2)
        # 75% 概率将图元中心落在显著性焦点 BBox 区域内
        if self.saliency_boxes and random.random() < 0.75:
            box = random.choice(self.saliency_boxes)
            bx0, by0, bx1, by1 = box["x0"], box["y0"], box["x1"], box["y1"]
            style = box["style"]
            cx = random.uniform(bx0, bx1)
            cy = random.uniform(by0, by1)
            bw = max(4, bx1 - bx0)
            bh = max(4, by1 - by0)

            # 根据总图元数量自适应缩小微观图元尺寸，雕刻细节
            size_decay = max(0.2, 1.0 - (len(self.recorded_shapes) / float(self.num_shapes)) * 0.7)

            if self.shape_type in ("triangle", "triangles") or style == "sharp_planes":
                # 纯锐角三角形切面 (Triangle Mesh)
                span_w = max(2, bw * 0.4 * size_decay)
                span_h = max(2, bh * 0.4 * size_decay)
                p1 = (_clamp(cx + random.uniform(-span_w, span_w), 0, w), _clamp(cy + random.uniform(-span_h, span_h), 0, h))
                p2 = (_clamp(cx + random.uniform(-span_w, span_w), 0, w), _clamp(cy + random.uniform(-span_h, span_h), 0, h))
                p3 = (_clamp(cx + random.uniform(-span_w, span_w), 0, w), _clamp(cy + random.uniform(-span_h, span_h), 0, h))
                return {"kind": "polygon", "points": [p1, p2, p3]}
            elif style == "fractal_spires":
                rw = max(1, random.uniform(bw * 0.05, bw * 0.3) * size_decay)
                rh = max(2, random.uniform(bh * 0.15, bh * 0.8) * size_decay)
                ang = random.uniform(-45, 45)
                return {"kind": "rotated_rect", "cx": cx, "cy": cy, "width": rw, "height": rh, "angle": ang}
            elif style == "scattered_facets":
                r_scale = max(2, random.uniform(min(bw, bh) * 0.05, min(bw, bh) * 0.25) * size_decay)
                pt_count = 3 if self.shape_type == "triangle" else random.choice([3, 4])
                pts = []
                for _ in range(pt_count):
                    ang = random.uniform(0, 2 * math.pi)
                    r = random.uniform(r_scale * 0.3, r_scale)
                    pts.append((_clamp(cx + r * math.cos(ang), 0, w), _clamp(cy + r * math.sin(ang), 0, h)))
                return {"kind": "polygon", "points": pts}
            else:
                if self.shape_type == "ellipse":
                    rx = max(2, random.uniform(bw * 0.05, bw * 0.3) * size_decay)
                    ry = max(2, random.uniform(bh * 0.05, bh * 0.3) * size_decay)
                    return {"kind": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry}
                else:
                    span_w = max(2, bw * 0.35 * size_decay)
                    span_h = max(2, bh * 0.35 * size_decay)
                    p1 = (_clamp(cx + random.uniform(-span_w, span_w), 0, w), _clamp(cy + random.uniform(-span_h, span_h), 0, h))
                    p2 = (_clamp(cx + random.uniform(-span_w, span_w), 0, w), _clamp(cy + random.uniform(-span_h, span_h), 0, h))
                    p3 = (_clamp(cx + random.uniform(-span_w, span_w), 0, w), _clamp(cy + random.uniform(-span_h, span_h), 0, h))
                    return {"kind": "polygon", "points": [p1, p2, p3]}

        # 全局普通图元
        size_decay = max(0.2, 1.0 - (len(self.recorded_shapes) / float(self.num_shapes)) * 0.6)
        if self.shape_type in ("triangle", "triangles"):
            kind = "polygon"
            pt_count = 3
        elif self.shape_type in ("polygon", "polygons"):
            kind = "polygon"
            pt_count = random.choice([3, 3, 4])
        elif self.shape_type in ("ellipse", "circles"):
            kind = "ellipse"
        else:
            kind = random.choice(["polygon", "polygon", "rotated_rect", "ellipse"]) if self.angularity > 0.6 else random.choice(["ellipse", "polygon"])
            pt_count = random.choice([3, 3, 4])

        if kind == "polygon":
            cx, cy = random.uniform(0, w), random.uniform(0, h)
            rad_max = max(2, random.uniform(min(w, h) * 0.04, min(w, h) * 0.25) * size_decay)
            pts = []
            for _ in range(pt_count):
                ang = random.uniform(0, 2 * math.pi)
                r = random.uniform(rad_max * 0.25, rad_max)
                pts.append((_clamp(cx + r * math.cos(ang), 0, w), _clamp(cy + r * math.sin(ang), 0, h)))
            return {"kind": "polygon", "points": pts}
        elif kind == "rotated_rect":
            cx, cy = random.uniform(0, w), random.uniform(0, h)
            rw = max(2, random.uniform(w * 0.04, w * 0.25) * size_decay)
            rh = max(2, random.uniform(h * 0.03, h * 0.18) * size_decay)
            ang = random.uniform(-55, 55)
            return {"kind": "rotated_rect", "cx": cx, "cy": cy, "width": rw, "height": rh, "angle": ang}
        else:
            cx, cy = random.uniform(0, w), random.uniform(0, h)
            rx = max(2, random.uniform(w * 0.03, w * 0.18) * size_decay)
            ry = max(2, random.uniform(h * 0.03, h * 0.18) * size_decay)
            return {"kind": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry}

    def _rasterize_shape_mask(self, shape: dict) -> np.ndarray:
        """将几何图元光栅化为单通道二值 Mask 掩膜"""
        mask_img = Image.new("L", (self.w, self.h), 0)
        draw = ImageDraw.Draw(mask_img)

        kind = shape["kind"]
        if kind == "polygon":
            draw.polygon(shape["points"], fill=255)
        elif kind == "ellipse":
            cx, cy, rx, ry = shape["cx"], shape["cy"], shape["rx"], shape["ry"]
            draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
        elif kind == "rotated_rect":
            cx, cy, rw, rh, ang = shape["cx"], shape["cy"], shape["width"], shape["height"], shape["angle"]
            rad = math.radians(ang)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            dx1, dy1 = cos_a * (rw / 2), sin_a * (rw / 2)
            dx2, dy2 = -sin_a * (rh / 2), cos_a * (rh / 2)
            p1 = (cx - dx1 - dx2, cy - dy1 - dy2)
            p2 = (cx + dx1 - dx2, cy + dy1 - dy2)
            p3 = (cx + dx1 + dx2, cy + dy1 + dy2)
            p4 = (cx - dx1 + dx2, cy - dy1 + dy2)
            draw.polygon([p1, p2, p3, p4], fill=255)

        return np.asarray(mask_img, dtype=bool)

    def _evaluate_shape(self, shape: dict) -> tuple[float, tuple[int, int, int], np.ndarray]:
        """结合显著性热力图计算加权 MSE 收益"""
        mask = self._rasterize_shape_mask(shape)
        count = np.count_nonzero(mask)
        if count < 3:
            return float("inf"), (0, 0, 0), mask

        target_pixels = self.target_np[mask]
        mean_color = np.mean(target_pixels, axis=0)
        color = (int(mean_color[0]), int(mean_color[1]), int(mean_color[2]))

        a = self.alpha / 255.0
        current_pixels = self.current_np[mask]
        new_pixels = current_pixels * (1.0 - a) + mean_color * a

        # 乘以显著性权重矩阵
        weights = self.weight_map[mask, np.newaxis]
        old_diff = current_pixels - target_pixels
        new_diff = new_pixels - target_pixels

        old_weighted_mse = np.sum((old_diff ** 2) * weights)
        new_weighted_mse = np.sum((new_diff ** 2) * weights)

        total_weight_sum = np.sum(self.weight_map) * 3
        delta_score = (new_weighted_mse - old_weighted_mse) / total_weight_sum
        new_total_score = self.current_score + delta_score

        return new_total_score, color, mask

    def _mutate_shape(self, shape: dict, jitter: float = 0.05) -> dict:
        """局部爬山变异微调"""
        mutated = {"kind": shape["kind"]}
        w, h = self.w, self.h
        scale_jitter = jitter

        if shape["kind"] == "polygon":
            new_pts = []
            for px, py in shape["points"]:
                nx = _clamp(px + random.uniform(-w * scale_jitter, w * scale_jitter), 0, w)
                ny = _clamp(py + random.uniform(-h * scale_jitter, h * scale_jitter), 0, h)
                new_pts.append((nx, ny))
            mutated["points"] = new_pts
        elif shape["kind"] == "ellipse":
            mutated["cx"] = _clamp(shape["cx"] + random.uniform(-w * scale_jitter, w * scale_jitter), 0, w)
            mutated["cy"] = _clamp(shape["cy"] + random.uniform(-h * scale_jitter, h * scale_jitter), 0, h)
            mutated["rx"] = max(3, shape["rx"] * random.uniform(1.0 - scale_jitter * 1.5, 1.0 + scale_jitter * 1.5))
            mutated["ry"] = max(3, shape["ry"] * random.uniform(1.0 - scale_jitter * 1.5, 1.0 + scale_jitter * 1.5))
        elif shape["kind"] == "rotated_rect":
            mutated["cx"] = _clamp(shape["cx"] + random.uniform(-w * scale_jitter, w * scale_jitter), 0, w)
            mutated["cy"] = _clamp(shape["cy"] + random.uniform(-h * scale_jitter, h * scale_jitter), 0, h)
            mutated["width"] = max(3, shape["width"] * random.uniform(1.0 - scale_jitter * 1.5, 1.0 + scale_jitter * 1.5))
            mutated["height"] = max(3, shape["height"] * random.uniform(1.0 - scale_jitter * 1.5, 1.0 + scale_jitter * 1.5))
            mutated["angle"] = shape["angle"] + random.uniform(-jitter * 100, jitter * 100)

        return mutated

    def fit(self) -> list[dict]:
        """执行三阶段多尺度自适应退火图元拟合循环"""
        total_steps = self.num_shapes

        for step in range(total_steps):
            progress = step / float(max(1, total_steps))
            best_shape = None
            best_score = self.current_score
            best_color = (128, 128, 128)
            best_mask = None

            # 随着进度退火，微调变异步长
            jitter = 0.08 if progress < 0.25 else (0.04 if progress < 0.55 else 0.015)

            for _ in range(self.candidate_count):
                candidate = self._random_shape(progress=progress, is_macro=(progress < 0.20))
                score, color, mask = self._evaluate_shape(candidate)
                if score < best_score:
                    best_score = score
                    best_shape = candidate
                    best_color = color
                    best_mask = mask

            if best_shape:
                for _ in range(self.mutate_steps):
                    mutated = self._mutate_shape(best_shape, jitter)
                    score, color, mask = self._evaluate_shape(mutated)
                    if score < best_score:
                        best_score = score
                        best_shape = mutated
                        best_color = color
                        best_mask = mask

                a = self.alpha / 255.0
                color_arr = np.array(best_color, dtype=np.float32)
                self.current_np[best_mask] = self.current_np[best_mask] * (1.0 - a) + color_arr * a
                self.current_score = best_score
                best_shape["color"] = best_color
                best_shape["alpha"] = self.alpha
                self.recorded_shapes.append(best_shape)

        return self.recorded_shapes

    def to_svg(self) -> str:
        """导出标准极简 SVG，严格锁定原照片真实长宽比并强制 clipPath 裁切边界"""
        w, h = float(self.w), float(self.h)

        svg_lines = [
            f'<svg viewBox="0 0 {w:.2f} {h:.2f}" xmlns="http://www.w3.org/2000/svg">',
            f'  <defs>',
            f'    <clipPath id="canvas_clip">',
            f'      <rect x="0" y="0" width="{w:.2f}" height="{h:.2f}"/>',
            f'    </clipPath>',
            f'  </defs>',
            f'  <!-- Saliency Guided Primitive Abstract: {len(self.recorded_shapes)} shapes -->',
            f'  <rect x="0" y="0" width="{w:.2f}" height="{h:.2f}" fill="#{self.bg_color[0]:02x}{self.bg_color[1]:02x}{self.bg_color[2]:02x}"/>',
            f'  <g clip-path="url(#canvas_clip)">',
        ]

        for s in self.recorded_shapes:
            r, g, b = s["color"]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            opacity = round(s["alpha"] / 255.0, 3)

            kind = s["kind"]
            if kind == "polygon":
                pts_str = " ".join([f"{_clamp(px, 0, w):.2f},{_clamp(py, 0, h):.2f}" for px, py in s["points"]])
                svg_lines.append(f'    <polygon points="{pts_str}" fill="{hex_color}" fill-opacity="{opacity}"/>')
            elif kind == "ellipse":
                cx = _clamp(s["cx"], 0, w)
                cy = _clamp(s["cy"], 0, h)
                rx = s["rx"]
                ry = s["ry"]
                svg_lines.append(f'    <ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="{hex_color}" fill-opacity="{opacity}"/>')
            elif kind == "rotated_rect":
                cx = _clamp(s["cx"], 0, w)
                cy = _clamp(s["cy"], 0, h)
                rw = s["width"]
                rh = s["height"]
                ang = s["angle"]
                svg_lines.append(
                    f'    <rect x="{-rw/2:.2f}" y="{-rh/2:.2f}" width="{rw:.2f}" height="{rh:.2f}" '
                    f'transform="translate({cx:.2f},{cy:.2f}) rotate({ang:.1f})" '
                    f'fill="{hex_color}" fill-opacity="{opacity}"/>'
                )

        # ── 顶层核心主体灵魂特征线条叠加 (Hero Subject Gestural Strokes) ───────
        # 严格遵守：线条只作用于 1~2 个关键主体，背景彻底留白涂抹，杜绝背景杂线
        dark_hex = f"#{int(self.bg_color[0]*0.35):02x}{int(self.bg_color[1]*0.35):02x}{int(self.bg_color[2]*0.35):02x}"
        light_accent_hex = "#E8EEF5"

        for box in self.saliency_boxes[:2]:
            bx0, by0, bx1, by1 = box["x0"], box["y0"], box["x1"], box["y1"]
            stype = box.get("subject_type", "other")
            kpts = box.get("keypoints", [])
            cx = (bx0 + bx1) / 2.0
            cy = (by0 + by1) / 2.0
            bw = max(2.0, bx1 - bx0)
            bh = max(2.0, by1 - by0)

            # 1. 局部感知亮度自适应对比度 (Luminance-Adaptive Stroke Color)
            box_crop = self.target_np[by0:by1, bx0:bx1]
            if box_crop.size > 0:
                lum = float(np.mean(0.299 * box_crop[:, :, 0] + 0.587 * box_crop[:, :, 1] + 0.114 * box_crop[:, :, 2]))
            else:
                lum = 128.0
            # 若主体处于暗调区（夜景、暗林、深色剪影），自适应采用亮金/高光色；若在亮区采用深墨色
            stroke_hex = light_accent_hex if lum < 115.0 else dark_hex
            stroke_op = 0.88 if lum < 115.0 else 0.80

            if stype == "human":
                # 独行者/人物：头部点睛小圆点 + 贾科梅蒂式极简中轴/姿势流线
                head_x = kpts[0][0] if len(kpts) > 0 else cx
                head_y = kpts[0][1] if len(kpts) > 0 else (by0 + bh * 0.15)
                feet_x = kpts[-1][0] if len(kpts) > 1 else cx
                feet_y = kpts[-1][1] if len(kpts) > 1 else by1
                head_r = max(1.2, min(bw * 0.12, bh * 0.08))

                # 头部小圆点
                svg_lines.append(f'    <circle cx="{head_x:.2f}" cy="{head_y:.2f}" r="{head_r:.2f}" fill="{stroke_hex}" fill-opacity="{stroke_op}"/>')
                # 身体姿势线 (一笔修长躯干流线)
                svg_lines.append(
                    f'    <path d="M {head_x:.2f},{head_y + head_r:.2f} '
                    f'Q {cx + (head_x - cx)*0.5:.2f},{(head_y + feet_y)*0.5:.2f} {feet_x:.2f},{feet_y:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="1.2" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                )

            elif stype == "bird":
                # 鸟/飞禽：轻盈极简展翼双弧
                if len(kpts) >= 3:
                    lx, ly = kpts[0]
                    body_x, body_y = kpts[1]
                    rx, ry = kpts[2]
                else:
                    lx, ly = bx0, cy + bh * 0.1
                    body_x, body_y = cx, cy
                    rx, ry = bx1, cy + bh * 0.1

                svg_lines.append(
                    f'    <path d="M {lx:.2f},{ly:.2f} Q {(lx+body_x)/2:.2f},{body_y - bh*0.25:.2f} {body_x:.2f},{body_y:.2f} '
                    f'Q {(body_x+rx)/2:.2f},{body_y - bh*0.25:.2f} {rx:.2f},{ry:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="1.1" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                )

            elif stype == "animal":
                # 动物/牛马：背脊流畅骨架线与站立支撑
                if len(kpts) >= 3:
                    p1, p2, p3 = kpts[0], kpts[1], kpts[2]
                    svg_lines.append(
                        f'    <path d="M {p1[0]:.2f},{p1[1]:.2f} Q {p2[0]:.2f},{p2[1]:.2f} {p3[0]:.2f},{p3[1]:.2f}" '
                        f'stroke="{stroke_hex}" stroke-width="1.2" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                    )
                else:
                    svg_lines.append(
                        f'    <path d="M {bx0 + bw*0.15:.2f},{by0 + bh*0.4:.2f} Q {cx:.2f},{by0 + bh*0.15:.2f} {bx1 - bw*0.1:.2f},{by0 + bh*0.35:.2f} '
                        f'L {bx1 - bw*0.15:.2f},{by1:.2f}" '
                        f'stroke="{stroke_hex}" stroke-width="1.2" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                    )

            elif stype == "tree":
                # 树木/枯枝：自然蜿蜒向上生长的主干分叉
                svg_lines.append(
                    f'    <path d="M {cx:.2f},{by1:.2f} Q {cx - bw*0.15:.2f},{(by0+by1)/2:.2f} {cx + bw*0.1:.2f},{by0 + bh*0.25:.2f} L {cx + bw*0.25:.2f},{by0:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="1.3" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                )
                svg_lines.append(
                    f'    <path d="M {cx - bw*0.05:.2f},{(by0+by1)*0.55:.2f} Q {cx - bw*0.35:.2f},{by0 + bh*0.4:.2f} {cx - bw*0.25:.2f},{by0 + bh*0.15:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="0.9" stroke-opacity="{stroke_op*0.9:.2f}" fill="none" stroke-linecap="round"/>'
                )

            elif stype == "mountain":
                # 雪山/山峰：刚劲山脊主折线
                peak_x = kpts[1][0] if len(kpts) >= 3 else cx
                peak_y = kpts[1][1] if len(kpts) >= 3 else by0
                left_x = kpts[0][0] if len(kpts) >= 3 else bx0
                left_y = kpts[0][1] if len(kpts) >= 3 else by1
                right_x = kpts[2][0] if len(kpts) >= 3 else bx1
                right_y = kpts[2][1] if len(kpts) >= 3 else by1

                svg_lines.append(
                    f'    <polyline points="{left_x:.2f},{left_y:.2f} {peak_x:.2f},{peak_y:.2f} {right_x:.2f},{right_y:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="1.1" stroke-opacity="{stroke_op}" fill="none" stroke-linejoin="round"/>'
                )

            elif stype == "architecture":
                # 建筑/古建飞檐：挑檐向上优美翘起弧线 + 垂直立面线条
                if len(kpts) >= 2:
                    p_start, p_tip = kpts[0], kpts[1]
                    svg_lines.append(
                        f'    <path d="M {p_start[0]:.2f},{p_start[1]:.2f} Q {(p_start[0]+p_tip[0])/2:.2f},{p_start[1]+bh*0.1:.2f} {p_tip[0]:.2f},{p_tip[1]:.2f}" '
                        f'stroke="{stroke_hex}" stroke-width="1.3" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                    )
                else:
                    # 飞檐上翘弧线
                    svg_lines.append(
                        f'    <path d="M {bx0:.2f},{by0 + bh*0.45:.2f} Q {bx0 + bw*0.5:.2f},{by0 + bh*0.55:.2f} {bx1:.2f},{by0 + bh*0.1:.2f}" '
                        f'stroke="{stroke_hex}" stroke-width="1.3" stroke-opacity="{stroke_op}" fill="none" stroke-linecap="round"/>'
                    )
                # 建筑立面垂线
                svg_lines.append(
                    f'    <line x1="{cx:.2f}" y1="{by0 + bh*0.4:.2f}" x2="{cx:.2f}" y2="{by1:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="0.9" stroke-opacity="{stroke_op*0.8:.2f}"/>'
                )

            elif stype == "vessel":
                # 孤舟/船：微弧船底与挺立桅杆
                svg_lines.append(
                    f'    <path d="M {bx0:.2f},{cy:.2f} Q {cx:.2f},{by1:.2f} {bx1:.2f},{cy:.2f} Z" '
                    f'stroke="{stroke_hex}" stroke-width="1.1" stroke-opacity="{stroke_op}" fill="none" stroke-linejoin="round"/>'
                )
                svg_lines.append(
                    f'    <line x1="{cx:.2f}" y1="{by0:.2f}" x2="{cx:.2f}" y2="{cy + bh*0.2:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="0.9" stroke-opacity="{stroke_op*0.9:.2f}"/>'
                )

            else:
                # 通用聚焦律动短弧
                svg_lines.append(
                    f'    <path d="M {bx0:.2f},{cy:.2f} Q {cx:.2f},{cy - bh*0.2:.2f} {bx1:.2f},{cy:.2f}" '
                    f'stroke="{stroke_hex}" stroke-width="1.0" stroke-opacity="{stroke_op*0.85:.2f}" fill="none" stroke-linecap="round"/>'
                )

        svg_lines.append("  </g>")
        svg_lines.append("</svg>")
        return "\n".join(svg_lines)


def generate_primitive_svg(
    image_input: Image.Image | bytes,
    config: dict | None = None,
    palette: dict | None = None,
    directives: dict | None = None,
) -> str:
    """
    Scheme4 事实几何图元生成统一入口（接入大模型实时几何指令）
    """
    cfg = config or {}
    num_shapes = int(cfg.get("num_shapes", 200))
    shape_type = str(cfg.get("shape_type", "triangle")).strip().lower()
    alpha = int(cfg.get("alpha", 200))
    sample_size = int(cfg.get("sample_size", 256))
    candidate_count = int(cfg.get("candidate_count", 60))
    mutate_steps = int(cfg.get("mutate_steps", 16))

    try:
        if isinstance(image_input, bytes):
            img_bytes = image_input
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        else:
            pil_img = image_input.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=90)
            img_bytes = buf.getvalue()
    except Exception:
        # 非法图片安全兜底
        dom_c = (palette or {}).get("dominant", (90, 110, 80))
        dark_c = (palette or {}).get("dark", (40, 45, 40))
        return (
            f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">\n'
            f'  <polygon points="10,80 90,40 90,85 10,85" fill="#{dom_c[0]:02x}{dom_c[1]:02x}{dom_c[2]:02x}"/>\n'
            f'  <circle cx="50" cy="45" r="8" fill="#{dark_c[0]:02x}{dark_c[1]:02x}{dark_c[2]:02x}"/>\n'
            f'</svg>'
        )

    optimizer = PythonPrimitiveOptimizer(
        target_img=pil_img,
        num_shapes=num_shapes,
        shape_type=shape_type,
        alpha=alpha,
        sample_size=sample_size,
        candidate_count=candidate_count,
        mutate_steps=mutate_steps,
        directives=directives,
    )
    optimizer.fit()
    return optimizer.to_svg()


def run_cli_primitive(
    image_bytes: bytes,
    bin_path: str = "primitive",
    num_shapes: int = 36,
    shape_mode: int = 0,
    alpha: int = 200,
    sample_size: int = 256,
) -> str | None:
    """尝试调用本地编译的原生 Go primitive 二进制命令行工具"""
    resolved_bin = shutil.which(bin_path) or (bin_path if os.path.isfile(bin_path) and os.access(bin_path, os.X_OK) else None)
    if not resolved_bin:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        in_path = os.path.join(tmp_dir, "input.jpg")
        out_path = os.path.join(tmp_dir, "output.svg")

        with open(in_path, "wb") as f:
            f.write(image_bytes)

        cmd = [
            resolved_bin,
            "-i", in_path,
            "-o", out_path,
            "-n", str(num_shapes),
            "-m", str(shape_mode),
            "-a", str(alpha),
            "-s", str(sample_size),
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, timeout=15, check=True)
            if os.path.exists(out_path):
                with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
                    svg_content = f.read()
                if "<svg" in svg_content:
                    return svg_content
        except Exception:
            return None

    return None
