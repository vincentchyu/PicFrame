"""
Scheme4 抽象几何母题生成器抽象基类 (Base Motif Generator)
"""
from abc import ABC, abstractmethod
import io
from PIL import Image


class BaseMotifGenerator(ABC):
    """几何母题与艺术抽象图元生成器统一接口规范"""

    @abstractmethod
    def generate_svg(
        self,
        image_input: Image.Image | bytes,
        config: dict | None = None,
        palette: dict | None = None,
        directives: dict | None = None,
    ) -> str:
        """
        根据输入图像生成标准 SVG 代码
        
        :param image_input: PIL Image 对象或 JPEG/PNG 二进制字节流
        :param config: 引擎专属配置字典 (如 points, num_shapes, blur 等)
        :param palette: 画廊调色板 (包含 dominant, dark, neutral, accent 等)
        :param directives: 视觉大模型/CV 提取的结构化指令 (包含 saliency_foci, composition_axis 等)
        :return: 合法且包含完整 viewBox 的 SVG 字符串
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查当前生成器在当前运行环境中是否可用 (例如依赖的 CLI 二进制或库是否存在)"""
        pass

    def prepare_image_bytes(self, image_input: Image.Image | bytes, max_size: int | None = None) -> tuple[bytes, Image.Image]:
        """
        统一图像输入预处理辅助方法
        :return: (image_bytes, pil_image)
        """
        if isinstance(image_input, bytes):
            img_bytes = image_input
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        else:
            pil_img = image_input.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=95)
            img_bytes = buf.getvalue()

        if max_size and max_size > 0:
            w, h = pil_img.size
            if max(w, h) > max_size:
                scale = max_size / max(w, h)
                nw, nh = max(16, int(w * scale)), max(16, int(h * scale))
                resample_filter = getattr(Image.Resampling, "LANCZOS", Image.BILINEAR)
                pil_img = pil_img.resize((nw, nh), resample_filter)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=95)
                img_bytes = buf.getvalue()

        return img_bytes, pil_img
