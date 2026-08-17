"""
Scheme4 抽象几何母题生成器注册中心与工厂 (Motif Generators Registry & Factory)
"""
from typing import Dict, Type
from PIL import Image

from .base import BaseMotifGenerator
from .triangle_generator import TriangleCLIGenerator
from .primitive_generator import PythonPrimitiveGenerator, PrimitiveCLIGenerator
from .color_filter import apply_selective_color_filter, apply_selective_color_pipeline

# 默认注册表
_GENERATOR_REGISTRY: Dict[str, Type[BaseMotifGenerator]] = {
    "triangle": TriangleCLIGenerator,
    "delaunay": TriangleCLIGenerator,
    "primitive": PythonPrimitiveGenerator,
    "primitive_py": PythonPrimitiveGenerator,
    "primitive_cli": PrimitiveCLIGenerator,
}


def register_generator(name: str, generator_cls: Type[BaseMotifGenerator]):
    """动态注册新的几何生成器"""
    _GENERATOR_REGISTRY[name.lower().strip()] = generator_cls


def get_motif_generator(name: str = "triangle", **kwargs) -> BaseMotifGenerator:
    """
    根据引擎名称获取生成器实例
    
    :param name: 生成器名称，如 "triangle", "primitive", "primitive_cli"
    :return: 具体的 BaseMotifGenerator 实例
    """
    key = str(name).lower().strip()
    generator_cls = _GENERATOR_REGISTRY.get(key)
    if not generator_cls:
        # 默认回退至 python primitive
        generator_cls = PythonPrimitiveGenerator
    return generator_cls(**kwargs)


def generate_motif_svg(
    image_input: Image.Image | bytes,
    generator_type: str = "triangle",
    generator_config: dict | None = None,
    palette: dict | None = None,
    directives: dict | None = None,
) -> str:
    """
    几何抽象母题生成统一调度入口
    
    具备自动平滑降级机制：
    1. 优先尝试请求的生成器 (如 triangle CLI)
    2. 若生成器不可用或执行异常，自动降级至内置 PythonPrimitiveGenerator 确保批处理不中断
    """
    cfg = generator_config or {}
    req_type = str(generator_type).lower().strip()
    
    primary_gen = get_motif_generator(req_type)
    
    # 检查可用性
    if primary_gen.is_available():
        try:
            return primary_gen.generate_svg(
                image_input=image_input,
                config=cfg,
                palette=palette,
                directives=directives,
            )
        except Exception as e:
            print(f"[Motif Generator] ⚠️ '{req_type}' 执行异常 ({e})，正在平滑回退至内置 Python 图元优化器...")
    else:
        print(f"[Motif Generator] ⚠️ '{req_type}' 未在当前环境安装或不可用，自动平滑切换至内置 Python 图元优化器")

    fallback_gen = PythonPrimitiveGenerator()
    return fallback_gen.generate_svg(
        image_input=image_input,
        config=cfg,
        palette=palette,
        directives=directives,
    )


__all__ = [
    "BaseMotifGenerator",
    "TriangleCLIGenerator",
    "PythonPrimitiveGenerator",
    "PrimitiveCLIGenerator",
    "get_motif_generator",
    "register_generator",
    "generate_motif_svg",
    "apply_selective_color_filter",
    "apply_selective_color_pipeline",
]
