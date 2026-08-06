from abc import ABC, abstractmethod
from importlib import import_module
from importlib import util as importlib_util
from dataclasses import dataclass


DEPENDENCY_MODULES = {
    "Pillow": "PIL",
    "PyYAML": "yaml",
    "numpy": "numpy",
}


from .context import RendererContext


class PresentationRenderer(ABC):
    """Extension point for a complete presentation scheme renderer."""

    renderer_id = ""

    @abstractmethod
    def prepare_context(self, photo_path, source_dir, presentation, layout, compression="none"):
        raise NotImplementedError

    @abstractmethod
    def render(self, context):
        raise NotImplementedError

    def apply_overlays(self, canvas, context):
        return canvas


def load_renderer(renderer_path):
    """Load a renderer class from ``package.module:ClassName`` config syntax."""
    try:
        module_name, class_name = str(renderer_path).split(":", 1)
        module = import_module(module_name)
        renderer_class = getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as exc:
        raise ValueError(f"Invalid presentation renderer: {renderer_path}") from exc
    if not isinstance(renderer_class, type) or not issubclass(renderer_class, PresentationRenderer):
        raise ValueError(f"Presentation renderer must extend PresentationRenderer: {renderer_path}")
    renderer = renderer_class()
    if not str(getattr(renderer, "renderer_id", "")).strip():
        raise ValueError(f"Presentation renderer is missing renderer_id: {renderer_path}")
    return renderer


def validate_presentation_requirements(presentation):
    """Validate only the selected scheme's declared config, resources, and dependencies."""
    missing_paths = []
    if presentation.config:
        config_path = presentation.resolve_path(presentation.config)
        if not config_path or not config_path.exists():
            missing_paths.append(("config", presentation.config, config_path))

    for name, raw_path in presentation.resources.items():
        path = presentation.resolve_path(raw_path)
        if not path or not path.exists():
            missing_paths.append((f"resource:{name}", raw_path, path))

    if missing_paths:
        detail = "; ".join(f"{kind} {raw!r} -> {resolved}" for kind, raw, resolved in missing_paths)
        raise FileNotFoundError(f"Presentation scheme {presentation.scheme_id!r} has missing requirements: {detail}")

    missing_dependencies = []
    for dependency in presentation.dependencies:
        module_name = DEPENDENCY_MODULES.get(dependency, dependency)
        if importlib_util.find_spec(module_name) is None:
            missing_dependencies.append(dependency)
    if missing_dependencies:
        names = ", ".join(missing_dependencies)
        raise RuntimeError(f"Presentation scheme {presentation.scheme_id!r} is missing dependencies: {names}")
