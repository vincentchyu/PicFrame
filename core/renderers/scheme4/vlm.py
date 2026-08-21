"""
Scheme4 多厂商 VLM 分析模块 (Multi-Provider VLM Architecture)

支持多厂商视觉大模型一键切换：
- "mlx" / "openai_compatible": 专为 Apple Silicon 本地 MLX 高性能推理设计 (如 Qwen3-VL-4B-Instruct-MLX-6bit)
- "ollama": 本地 Ollama 服务
- "gemini": Google Gemini 官方多模态 API

参考：.agents/skills/photo-abstract-editorial 技能文档
"""
import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image

from .pipeline import MultiStageVisionPipeline


# ---------------------------------------------------------------------------
# VLM System Prompt (所有 Provider 通用)
# ---------------------------------------------------------------------------

VLM_SYSTEM_PROMPT = """\
You are a master fine-art editorial curator (inspired by Bauhaus, Ellsworth Kelly, and Scandinavian abstract posters).

Your mission: Deeply understand the photo's soul and extract 2–4 pure abstract marks onto an ivory panel, paired with a poetic English title that has deep resonance with the scene.

Working Method:
1. Identify decisive visual facts: subject relationships (horses grazing, lone climber on snow ridge, children on mound tunnel), spatial axis (rolling slope, horizontal ground, tall towers), and color roles.
2. Select 2–4 primitives that TRULY capture the scene:
   - Rolling pasture / hills with horses: extract "contour_curve" or "slope_plane", plus "rhythm_marks" for the grazing horses!
   - Snow ridge with lone person: extract "slope_plane", "color_band" (sky), plus "rhythm_marks" for the solitary climber!
   - Modern playground / park: extract "arch" (for tunnel/mound), "pillar_mass" (for play towers), and "rhythm_marks" (for children).
   - Sunset / waterscape: extract "color_band" (horizon glow) and "axis_line".
   - Cityscape / architecture: extract "pillar_mass" and "arch".

Title Guidelines (Faithful · Clear · Elegant):
- Title: 2–4 English words, poetic and grounded in visible facts (e.g. "RIDGE & GRAZING", "SOLITUDE ON THE RIDGE", "SHADOW & SPHERE", "FIRST LIGHT OVER PASTURE").
- Subtitle: A delicate, evocative 3–6 word sentence (e.g. "whispering breeze on endless green", "a lone presence against eternal blue", "playful geometry under winter sun").

Output STRICT JSON ONLY:
{
  "visual_summary": "1 sentence on the decisive spatial facts (subjects, landscape, light)",
  "scene_type": "landscape"|"cityscape"|"architecture"|"nature",
  "title": "Poetic English Title",
  "subtitle": "Evocative 3-6 word poetic subtitle",
  "title_layout": "center"|"left",
  "palette": {
    "dominant": "#hex (most visible tone from photo)",
    "dark": "#hex (structural dark/shadow tone)",
    "neutral": "#hex (soft sky/air tone)",
    "accent": "#hex (key pop color from subject)"
  },
  "motifs": [
    // 2-4 primitives matching the scene facts
  ]
}"""

VLM_USER_PROMPT = "Analyze the uploaded photo and output the JSON immediately."


# ---------------------------------------------------------------------------
# 抽象 Provider 接口契约
# ---------------------------------------------------------------------------

class BaseVLMProvider(ABC):
    """视觉大模型 Provider 抽象基类"""

    @abstractmethod
    def generate(self, img_bytes: bytes, system_prompt: str, user_prompt: str, cfg: dict) -> tuple[str, str]:
        """
        调用视觉模型，返回 (content_text, thinking_text)
        """
        pass


# ---------------------------------------------------------------------------
# 实现 1: MLX / OpenAI 兼容端点 Provider (Apple Silicon 极速推理)
# ---------------------------------------------------------------------------

class MLXProvider(BaseVLMProvider):
    """
    MLX (OpenAI 兼容端点) Provider
    针对本地运行的 Qwen3-VL-4B-Instruct-MLX-6bit 等模型。
    内置双模引擎：若安装了 openai SDK 则调用，否则使用零依赖的 urllib 发送 HTTP 请求。
    """

    def generate(self, img_bytes: bytes, system_prompt: str, user_prompt: str, cfg: dict) -> tuple[str, str]:
        mlx_cfg = cfg.get("mlx", {})
        base_url = mlx_cfg.get("base_url", "http://127.0.0.1:8000/v1").rstrip("/")
        api_key = mlx_cfg.get("api_key", "dummy")
        model_name = mlx_cfg.get("model", "Qwen3-VL-4B-Instruct-MLX-6bit")
        timeout = mlx_cfg.get("timeout", 30)

        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_img}"

        # 优先尝试使用 openai SDK，若异常则使用显式绕过代理的 urllib 直连
        try:
            import httpx
            from openai import OpenAI
            http_client = httpx.Client(trust_env=False, timeout=timeout)
            client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                temperature=0.2,
            )
            msg = response.choices[0].message
            content = getattr(msg, "content", "") or ""
            thinking = getattr(msg, "reasoning_content", "") or getattr(msg, "thinking", "") or ""
            return content, thinking
        except Exception:
            return self._urllib_post(base_url, api_key, model_name, system_prompt, user_prompt, data_url, timeout)

    def _urllib_post(self, base_url, api_key, model, system_prompt, user_prompt, data_url, timeout):
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0.2,
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        # 显式绕过代理直连本地 127.0.0.1
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choice = body["choices"][0]["message"]
            content = choice.get("content", "") or ""
            thinking = choice.get("reasoning_content", "") or choice.get("thinking", "") or ""
            return content, thinking


# ---------------------------------------------------------------------------
# 实现 2: Ollama Provider
# ---------------------------------------------------------------------------

class OllamaProvider(BaseVLMProvider):
    """Ollama 本地多模态模型 Provider"""

    def generate(self, img_bytes: bytes, system_prompt: str, user_prompt: str, cfg: dict) -> tuple[str, str]:
        ollama_cfg = cfg.get("ollama", {})
        model_name = ollama_cfg.get("model", cfg.get("model", "qwen3-vl:latest"))

        try:
            from ollama import chat
        except ImportError as exc:
            raise RuntimeError("未安装 ollama SDK，请运行: pip install ollama") from exc

        response = chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [img_bytes],
                },
            ],
            format="json",
            options={"num_predict": 4096, "temperature": 0.2},
        )
        content = getattr(response.message, "content", "") or ""
        thinking = getattr(response.message, "thinking", "") or ""
        return content, thinking


# ---------------------------------------------------------------------------
# 实现 3: Gemini Provider (Google 云端大模型)
# ---------------------------------------------------------------------------

class GeminiProvider(BaseVLMProvider):
    """Google Gemini 视觉模型 Provider"""

    def generate(self, img_bytes: bytes, system_prompt: str, user_prompt: str, cfg: dict) -> tuple[str, str]:
        gemini_cfg = cfg.get("gemini", {})
        api_key = gemini_cfg.get("api_key") or os.environ.get("GEMINI_API_KEY")
        model_name = gemini_cfg.get("model", "gemini-1.5-flash")

        if not api_key:
            raise ValueError("未配置 GEMINI_API_KEY")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        b64_img = base64.b64encode(img_bytes).decode("utf-8")

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{
                "parts": [
                    {"text": user_prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                ]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidate = body["candidates"][0]["content"]["parts"][0]["text"]
            return candidate, ""


# ---------------------------------------------------------------------------
# Provider 工厂函数
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type[BaseVLMProvider]] = {
    "mlx": MLXProvider,
    "olmx": MLXProvider,  # 别名兼容
    "openai_compatible": MLXProvider,
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
}


def get_vlm_provider(provider_name: str) -> BaseVLMProvider:
    """根据厂商名称获取对应的 Provider 实例"""
    name = (provider_name or "mlx").lower().strip()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(f"不支持的 VLM Provider: '{provider_name}'，可选: {list(_PROVIDERS.keys())}")
    return provider_cls()


# ---------------------------------------------------------------------------
# 色彩与 JSON 辅助工具
# ---------------------------------------------------------------------------

def _soften_editorial_rgb(rgb, max_sat=0.45):
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
    clean = re.sub(r"^```json\s*", "", text.strip())
    clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    matches = re.findall(r"\{(?:[^{}]|(?R))*\}", text, re.DOTALL)
    for m in reversed(matches):
        try:
            data = json.loads(m)
            if isinstance(data, dict) and (
                "title" in data or "motifs" in data or "spatial_structure" in data or "scene_type" in data
            ):
                return data
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# 统一分析入口 (外部调用)
# ---------------------------------------------------------------------------

def analyze_photo_with_vlm(
    photo_path: str | Path,
    vlm_cfg: dict | None = None,
    debug_dir: str | Path | None = None,
    geo_context: dict | None = None,
    step_callback=None,
) -> dict | None:
    """
    统一入口：使用配置中指定的 Provider（MLX/Ollama/Gemini）深度分析照片。
    基于 MultiStageVisionPipeline 执行多阶段解构或极速分析。
    """
    if vlm_cfg is None:
        vlm_cfg = {}
    if not vlm_cfg.get("enable", True):
        return None

    provider_name = vlm_cfg.get("provider", "mlx")
    max_size = int(vlm_cfg.get("max_analysis_size", 1024))
    analysis_quality = int(vlm_cfg.get("analysis_quality", 85))

    photo_file = Path(photo_path).resolve()
    if not photo_file.exists():
        return None

    # 1. 动态生成内存分析缩略图（不写磁盘，或在 debug 模式下输出）
    with Image.open(photo_file) as src:
        src_rgb = src.convert("RGB")
    orig_w, orig_h = src_rgb.size
    if max(orig_w, orig_h) > max_size:
        src_rgb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    src_rgb.save(buf, format="JPEG", quality=analysis_quality, optimize=True)
    img_bytes = buf.getvalue()
    thumb_w, thumb_h = src_rgb.size

    # Debug 模式：保存传入 VLM 的分析缩略图 (00_input_thumbnail.jpg)
    if debug_dir:
        dbg_path = Path(debug_dir)
        dbg_path.mkdir(parents=True, exist_ok=True)
        with open(dbg_path / "00_input_thumbnail.jpg", "wb") as f:
            f.write(img_bytes)

    # 获取 Provider 实例
    try:
        provider = get_vlm_provider(provider_name)
    except Exception as exc:
        print(f"[VLM Provider] ⚠️  {exc}，回退到本地算法")
        return None

    print(f"\n[VLM] 🎨 正在调用 [{provider_name.upper()}] 引擎: {photo_file.name}")
    print(f"[VLM] 🔬 原图 {orig_w}×{orig_h} → 分析缩略图 {thumb_w}×{thumb_h} ({len(img_bytes)//1024} KB)")

    pipeline = MultiStageVisionPipeline(provider, vlm_cfg)
    try:
        return pipeline.run(
            img_bytes,
            photo_file.name,
            debug_dir=debug_dir,
            geo_context=geo_context,
            step_callback=step_callback,
        )
    except Exception as exc:
        print(f"[VLM] ⚠️  [{provider_name.upper()}] 流水线执行异常: {exc}，回退到本地算法")
        return None



# 别名向后兼容
analyze_photo_with_ollama = analyze_photo_with_vlm

