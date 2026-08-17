"""
Scheme4 Triangle Delaunay 三角剖分母题生成器 (TriangleCLIGenerator)
基于开源高性能 Go 工具 esimov/triangle (https://github.com/esimov/triangle)
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
from PIL import Image

from .base import BaseMotifGenerator

# 默认场景自适应采样点数档位
DEFAULT_SCENE_POINT_TIERS = {
    "portrait": 22000,       # 人像/面部特写: 超高精五官与眼神光还原
    "human": 20000,          # 人物主体/人像生活
    "architecture": 16000,   # 古建/街景/都市: 丰富几何结构与硬边线条
    "wildlife": 14000,       # 生物/飞禽走兽: 灵动羽翼与肌肉体态
    "animal": 14000,         # 动物主体
    "street": 12000,         # 人文街头/生活纪实: 丰富构件与故事细节
    "botanical": 8000,       # 树木/花草: 枝桠纹理与自然生长感
    "tree": 8000,            # 树木主体
    "mountain": 6000,        # 雪山高峰: 刚劲山脊与岩石断层
    "landscape": 5000,       # 自然风光/大地地貌: 适度晶格与地貌起伏
    "nature": 5000,          # 自然风光
    "seascape": 3000,        # 辽阔海景/水面倒影: 大色块波光留白
    "water": 3000,           # 水景/湖泊
    "minimalist": 1500,      # 极简留白/禅意大漠: 极简宏观立体派构成
    "minimal": 1500,         # 极简
}


class TriangleCLIGenerator(BaseMotifGenerator):
    """
    基于 esimov/triangle 命令行工具的 Delaunay 三角剖分生成器
    
    特点：
    - Go 多核并发高速计算 (Delaunay Triangulation)
    - 针对照片明暗边缘与复杂微观细节具有极高的还原度与晶格美感
    - 原生直接输出矢量 SVG
    - 支持结合 AI/CV 场景与主体语义动态自适应点数预算分配 (Auto Points Budget)
    """

    def __init__(self, bin_path: str = "triangle"):
        self.bin_path = bin_path

    def is_available(self) -> bool:
        """检查系统中是否存在可执行的 triangle 命令"""
        resolved = shutil.which(self.bin_path) or (
            self.bin_path if os.path.isfile(self.bin_path) and os.access(self.bin_path, os.X_OK) else None
        )
        return resolved is not None

    def _resolve_binary(self, custom_bin: str | None = None) -> str | None:
        bin_name = custom_bin or self.bin_path
        return shutil.which(bin_name) or (
            bin_name if os.path.isfile(bin_name) and os.access(bin_name, os.X_OK) else None
        )

    def resolve_adaptive_points(self, cfg: dict, directives: dict | None = None) -> tuple[int, str]:
        """
        根据 AI/CV 提取的场景语义与显著性主体事实，自适应计算最佳采样点数预算
        
        :return: (final_points, decision_reason)
        """
        auto_points = bool(cfg.get("auto_points", True))
        max_points = int(cfg.get("max_points") or 35000)
        min_points = int(cfg.get("min_points") or 1200)
        default_points = int(cfg.get("default_points") or cfg.get("points") or cfg.get("pts") or 5000)

        # 若未开启自动决策或未提供指令，使用静态配置并按上限约束
        if not auto_points or not directives:
            explicit_pts = int(cfg.get("points") or cfg.get("pts") or default_points)
            clamped_pts = max(min_points, min(max_points, explicit_pts))
            return clamped_pts, f"静态配置设定 (限制在 [{min_points}, {max_points}])"

        scene_tiers = {**DEFAULT_SCENE_POINT_TIERS, **(cfg.get("scene_point_tiers") or {})}

        # 1. 提取场景类型与核心主体
        scene_type = str(directives.get("scene_type") or "").strip().lower()
        foci = directives.get("saliency_foci") or []
        hero_subject = ""
        if isinstance(foci, list) and len(foci) > 0 and isinstance(foci[0], dict):
            hero_subject = str(foci[0].get("subject_type") or foci[0].get("label") or "").strip().lower()

        # 2. 匹配最佳点数档位
        matched_key = None
        base_budget = None

        # 优先匹配主体类型 (如 human, architecture, wildlife)
        for k, v in scene_tiers.items():
            if k in hero_subject:
                matched_key = f"主体:{k}"
                base_budget = v
                break

        # 其次匹配场景类型 (如 portrait, street, landscape, seascape)
        if base_budget is None:
            for k, v in scene_tiers.items():
                if k in scene_type:
                    matched_key = f"场景:{k}"
                    base_budget = v
                    break

        if base_budget is None:
            matched_key = "默认基准"
            base_budget = default_points

        # 3. 多主体微调：若包含多个显著性焦点，按比例适当追加 15%~30% 的预算池
        foci_count = len(foci) if isinstance(foci, list) else 1
        if foci_count > 1:
            multiplier = min(1.35, 1.0 + (foci_count - 1) * 0.15)
            base_budget = int(base_budget * multiplier)
            decision_info = f"AI 语义匹配 [{matched_key}] ({foci_count} 处焦点加权) → {base_budget:,} 点"
        else:
            decision_info = f"AI 语义匹配 [{matched_key}] → {base_budget:,} 点"

        # 4. 安全钳位在 [min_points, max_points] 区间
        final_points = max(min_points, min(max_points, base_budget))
        if final_points != base_budget:
            decision_info += f" (经阈值 [{min_points:,}, {max_points:,}] 钳位)"

        return final_points, decision_info

    def generate_svg(
        self,
        image_input: Image.Image | bytes,
        config: dict | None = None,
        palette: dict | None = None,
        directives: dict | None = None,
    ) -> str:
        cfg = config or {}
        bin_name = cfg.get("bin_path") or self.bin_path
        resolved_bin = self._resolve_binary(bin_name)
        if not resolved_bin:
            raise FileNotFoundError(
                f"未在系统 PATH 中找到可执行的 '{bin_name}' 命令，请先通过 'brew install triangle' 安装或检查配置。"
            )

        # 1. 动态自适应计算点数预算
        points, decision_reason = self.resolve_adaptive_points(cfg, directives=directives)
        print(f"[Triangle Budget] 🎯 {decision_reason} (最终采样点: {points:,})")

        # 2. 提取其他配置参数
        sample_size = cfg.get("sample_size", 768)  # 适度缩放平衡微观细节与极速并发
        point_rate = float(cfg.get("point_rate") or cfg.get("pr") or 0.075)
        stroke_width = float(cfg.get("stroke_width") or cfg.get("st") or 0.0)
        wireframe_mode = int(cfg.get("wireframe_mode") if "wireframe_mode" in cfg else cfg.get("wf", 0))
        blur_factor = int(cfg.get("blur_factor") or cfg.get("bf") or 1)
        blur_radius = int(cfg.get("blur_radius") or cfg.get("bl") or 2)
        edge_factor = int(cfg.get("edge_factor") or cfg.get("ef") or 6)
        sobel_threshold = int(cfg.get("sobel_threshold") or cfg.get("so") or 10)
        concurrency = int(cfg.get("concurrency") or cfg.get("cw") or 10)
        noise_factor = cfg.get("noise_factor") or cfg.get("nf")
        grayscale = bool(cfg.get("grayscale") or cfg.get("gr", False))
        solid_stroke = bool(cfg.get("solid_stroke") or cfg.get("sl", False))

        # 3. 图像预处理与暂存
        img_bytes, pil_img = self.prepare_image_bytes(image_input, max_size=sample_size)
        orig_w, orig_h = pil_img.size

        with tempfile.TemporaryDirectory(prefix="picframe_triangle_") as tmp_dir:
            in_path = os.path.join(tmp_dir, "input.jpg")
            out_path = os.path.join(tmp_dir, "output.svg")

            with open(in_path, "wb") as f:
                f.write(img_bytes)

            cmd = [
                resolved_bin,
                "-in", in_path,
                "-out", out_path,
                "-pts", str(points),
                "-pr", str(point_rate),
                "-wf", str(wireframe_mode),
                "-bf", str(blur_factor),
                "-bl", str(blur_radius),
                "-ef", str(edge_factor),
                "-so", str(sobel_threshold),
                "-cw", str(concurrency),
            ]

            if stroke_width > 0:
                cmd.extend(["-st", str(stroke_width)])
            if noise_factor is not None:
                cmd.extend(["-nf", str(int(noise_factor))])
            if grayscale:
                cmd.append("-gr")
            if solid_stroke:
                cmd.append("-sl")

            t0 = time.time()
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr or e.stdout or str(e)
                raise RuntimeError(f"Triangle CLI 执行失败 (exit {e.returncode}): {err_msg}")
            except subprocess.TimeoutExpired:
                raise TimeoutError(f"Triangle CLI 执行超时 (60s)")

            cost = time.time() - t0

            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                raise RuntimeError(f"Triangle CLI 未生成有效 SVG 输出文件")

            with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
                svg_content = f.read()

        # 4. 规范化 SVG 头部及 viewBox
        svg_content = self._normalize_svg(svg_content, orig_w, orig_h)
        return svg_content

    def _normalize_svg(self, svg_text: str, default_w: int, default_h: int) -> str:
        """确保 SVG 内容包含正确的 viewBox 属性以便 SVGRasterizer 无缝缩放"""
        if "<svg" not in svg_text:
            raise ValueError("Triangle 生成的内容不是合法的 SVG 代码")

        # 检查是否包含 viewBox
        if "viewBox=" not in svg_text and "viewbox=" not in svg_text.lower():
            # 提取 width 和 height
            w_match = re.search(r'width=["\']?(\d+)', svg_text, re.IGNORECASE)
            h_match = re.search(r'height=["\']?(\d+)', svg_text, re.IGNORECASE)
            w = int(w_match.group(1)) if w_match else default_w
            h = int(h_match.group(1)) if h_match else default_h
            
            # 在 <svg 标签后注入 viewBox
            svg_text = re.sub(
                r'<svg\b([^>]*)>',
                rf'<svg\1 viewBox="0 0 {w} {h}">',
                svg_text,
                count=1,
                flags=re.IGNORECASE
            )

        return svg_text.strip()
