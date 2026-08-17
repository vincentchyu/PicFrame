"""
Scheme4 Primitive 几何图元生成器包装实现 (Python / Go CLI)
"""
import io
import os
import shutil
import subprocess
import tempfile
from PIL import Image

from .base import BaseMotifGenerator
from ..primitive_engine import PythonPrimitiveOptimizer


class PythonPrimitiveGenerator(BaseMotifGenerator):
    """基于内置 Python / NumPy 爬山退火算法的显著性加权图元拟合生成器"""

    def is_available(self) -> bool:
        return True

    def generate_svg(
        self,
        image_input: Image.Image | bytes,
        config: dict | None = None,
        palette: dict | None = None,
        directives: dict | None = None,
    ) -> str:
        cfg = config or {}
        num_shapes = int(cfg.get("num_shapes", 200))
        shape_type = str(cfg.get("shape_type", "triangle")).strip().lower()
        alpha = int(cfg.get("alpha", 200))
        sample_size = int(cfg.get("sample_size", 256))
        candidate_count = int(cfg.get("candidate_count", 60))
        mutate_steps = int(cfg.get("mutate_steps", 16))

        img_bytes, pil_img = self.prepare_image_bytes(image_input)

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


class PrimitiveCLIGenerator(BaseMotifGenerator):
    """基于外部 Go primitive 命令行工具 (fogleman/primitive) 的生成器"""

    def __init__(self, bin_path: str = "primitive"):
        self.bin_path = bin_path

    def is_available(self) -> bool:
        resolved = shutil.which(self.bin_path) or (
            self.bin_path if os.path.isfile(self.bin_path) and os.access(self.bin_path, os.X_OK) else None
        )
        return resolved is not None

    def generate_svg(
        self,
        image_input: Image.Image | bytes,
        config: dict | None = None,
        palette: dict | None = None,
        directives: dict | None = None,
    ) -> str:
        cfg = config or {}
        bin_path = cfg.get("bin_path") or self.bin_path
        resolved_bin = shutil.which(bin_path) or (
            bin_path if os.path.isfile(bin_path) and os.access(bin_path, os.X_OK) else None
        )
        if not resolved_bin:
            raise FileNotFoundError(f"未找到可执行的 '{bin_path}' 命令")

        num_shapes = int(cfg.get("num_shapes", 200))
        alpha = int(cfg.get("alpha", 200))
        sample_size = int(cfg.get("sample_size", 256))
        shape_type = str(cfg.get("shape_type", "triangle")).strip().lower()
        mode_map = {"combo": 0, "triangle": 1, "rect": 2, "ellipse": 3, "circle": 4, "rotated_rect": 5, "polygon": 8}
        shape_mode = mode_map.get(shape_type, 1)

        img_bytes, _ = self.prepare_image_bytes(image_input)

        with tempfile.TemporaryDirectory(prefix="picframe_primitive_") as tmp_dir:
            in_path = os.path.join(tmp_dir, "input.jpg")
            out_path = os.path.join(tmp_dir, "output.svg")

            with open(in_path, "wb") as f:
                f.write(img_bytes)

            cmd = [
                resolved_bin,
                "-i", in_path,
                "-o", out_path,
                "-n", str(num_shapes),
                "-m", str(shape_mode),
                "-a", str(alpha),
                "-s", str(sample_size),
            ]

            subprocess.run(cmd, capture_output=True, timeout=30, check=True)
            if os.path.exists(out_path):
                with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
                    svg_content = f.read()
                if "<svg" in svg_content:
                    return svg_content

        raise RuntimeError("Primitive CLI 执行未生成有效 SVG")
