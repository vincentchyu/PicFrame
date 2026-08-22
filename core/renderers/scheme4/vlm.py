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
# ---------------------------------------------------------------------------
# 环境变量与 .env 自动加载辅助工具
# ---------------------------------------------------------------------------

_ENV_LOADED = False

def _load_env_file_if_needed(force: bool = False):
    """
    自动从项目根目录或当前工作目录加载 .env 文件中的环境变量 (如 GEMINI_API_KEY, MLX_API_KEY, OPENAI_API_KEY)
    """
    global _ENV_LOADED
    if _ENV_LOADED and not force:
        return

    # 1. 优先使用 python-dotenv
    try:
        import dotenv
        cur = Path(__file__).resolve().parent
        for _ in range(5):
            candidate = cur / ".env"
            if candidate.exists():
                dotenv.load_dotenv(candidate, override=force)
                _ENV_LOADED = True
                return
            cur = cur.parent
        dotenv.load_dotenv(override=force)
        _ENV_LOADED = True
        return
    except ImportError:
        pass

    # 2. 内置纯 Python .env 解析器兜底
    cur = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = cur / ".env"
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and (k not in os.environ or force):
                            os.environ[k] = v
                _ENV_LOADED = True
            except Exception:
                pass
            return
        cur = cur.parent
    _ENV_LOADED = True


# ---------------------------------------------------------------------------
# 思考与内容解析辅助工具
# ---------------------------------------------------------------------------

def _parse_content_and_thinking(raw_content: str, raw_thinking: str) -> tuple[str, str]:
    """
    智能归一化思考内容与最终输出：
    若服务商将 <think>...</think> 标签直接嵌入在 content 中，自动分离并提炼为 (content, thinking)
    """
    content = raw_content or ""
    thinking = raw_thinking or ""

    if not thinking and "<think>" in content:
        think_match = re.search(r"<think>([\s\S]*?)</think>", content, re.IGNORECASE)
        if think_match:
            thinking = think_match.group(1).strip()
            content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()

    return content, thinking


# ---------------------------------------------------------------------------
# 抽象 Provider 接口契约
# ---------------------------------------------------------------------------

class BaseVLMProvider(ABC):
    """视觉大模型 Provider 抽象基类"""

    @abstractmethod
    def generate(
        self,
        img_bytes: bytes,
        system_prompt: str,
        user_prompt: str,
        cfg: dict,
        stage_options: dict | None = None,
    ) -> tuple[str, str]:
        """
        调用视觉模型，返回 (content_text, thinking_text)
        支持透传 stage_options (含 temperature, max_thinking_tokens, reasoning_effort 等)
        """
        pass


# ---------------------------------------------------------------------------
# 实现 1: MLX / OpenAI 兼容端点 Provider (Apple Silicon 极速推理)
# ---------------------------------------------------------------------------

class MLXProvider(BaseVLMProvider):
    """
    MLX (OpenAI 兼容端点) Provider
    针对本地运行的 Youssofal--Qwen3.8-27B-MTPLX-Optimized-Speed-FP16 / Qwen3-VL 等模型。
    内置双模引擎：若安装了 openai SDK 则调用，否则使用零依赖的 urllib 发送 HTTP 请求。
    """

    def generate(
        self,
        img_bytes: bytes,
        system_prompt: str,
        user_prompt: str,
        cfg: dict,
        stage_options: dict | None = None,
    ) -> tuple[str, str]:
        _load_env_file_if_needed()

        mlx_cfg = cfg.get("mlx", {})
        base_url = mlx_cfg.get("base_url", "http://127.0.0.1:8000/v1").rstrip("/")
        api_key = (
            mlx_cfg.get("api_key")
            or os.environ.get("MLX_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or "dummy"
        )
        model_name = mlx_cfg.get("model", "Youssofal--Qwen3.8-27B-MTPLX-Optimized-Speed-FP16")
        timeout = int(mlx_cfg.get("timeout") or os.environ.get("MLX_TIMEOUT") or 60)

        # 合并阶段特异性参数 (Stage-specific Options)
        opts = stage_options or {}
        is_default = bool(opts.get("is_default", False))

        temperature = None
        max_tokens = None
        reasoning_effort = None
        extra_body = None

        if not is_default:
            temp_val = opts.get("temperature")
            temperature = float(temp_val) if temp_val is not None else 0.2
            max_thinking_tokens = opts.get("max_thinking_tokens")
            reasoning_effort = opts.get("reasoning_effort")
            max_tokens = int(opts.get("max_tokens", 8192))
            if max_thinking_tokens:
                max_tokens = max(max_tokens, int(max_thinking_tokens) + 4096)
                extra_body = {
                    "max_thinking_tokens": int(max_thinking_tokens),
                    "thinking": {"budget_tokens": int(max_thinking_tokens)},
                }

        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_img}"

        # 优先尝试使用 openai SDK，若异常则使用显式绕过代理的 urllib 直连
        try:
            import httpx
            from openai import OpenAI
            http_client = httpx.Client(trust_env=False, timeout=timeout)
            client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)

            kwargs = {
                "model": model_name,
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
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            if reasoning_effort is not None:
                kwargs["reasoning_effort"] = reasoning_effort
            if extra_body:
                kwargs["extra_body"] = extra_body

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            content = getattr(msg, "content", "") or ""
            thinking = getattr(msg, "reasoning_content", "") or getattr(msg, "thinking", "") or ""
            return _parse_content_and_thinking(content, thinking)
        except Exception:
            return self._urllib_post(
                base_url,
                api_key,
                model_name,
                system_prompt,
                user_prompt,
                data_url,
                timeout,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
            )

    def _urllib_post(
        self,
        base_url,
        api_key,
        model,
        system_prompt,
        user_prompt,
        data_url,
        timeout,
        temperature=None,
        max_tokens=None,
        reasoning_effort=None,
        extra_body=None,
    ):
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
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        if extra_body:
            payload.update(extra_body)

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
            return _parse_content_and_thinking(content, thinking)


# ---------------------------------------------------------------------------
# 实现 2: Ollama Provider
# ---------------------------------------------------------------------------

class OllamaProvider(BaseVLMProvider):
    """Ollama 本地多模态模型 Provider"""

    def generate(
        self,
        img_bytes: bytes,
        system_prompt: str,
        user_prompt: str,
        cfg: dict,
        stage_options: dict | None = None,
    ) -> tuple[str, str]:
        ollama_cfg = cfg.get("ollama", {})
        model_name = ollama_cfg.get("model", cfg.get("model", "qwen3-vl:latest"))
        opts = stage_options or {}
        temperature = float(opts.get("temperature", 0.2))
        max_thinking = int(opts.get("max_thinking_tokens", 4096))

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
            options={"num_predict": max_thinking + 2048, "temperature": temperature},
        )
        content = getattr(response.message, "content", "") or ""
        thinking = getattr(response.message, "thinking", "") or ""
        return _parse_content_and_thinking(content, thinking)



# ---------------------------------------------------------------------------
# 实现 3: Gemini Provider (Google 官方多模态大模型)
# ---------------------------------------------------------------------------

class GeminiProvider(BaseVLMProvider):
    """
    Google Gemini 官方视觉模型 Provider
    集成官方最新 google-genai SDK (from google import genai)，并提供零依赖 REST API 兜底。
    支持自动加载 .env 密钥、gemini-3.7-flash / gemini-2.5-flash / gemini-2.0-flash、
    多模态图片传输、thinking_budget 思考预算与 5 分钟超时保障。
    """

    def generate(
        self,
        img_bytes: bytes,
        system_prompt: str,
        user_prompt: str,
        cfg: dict,
        stage_options: dict | None = None,
    ) -> tuple[str, str]:
        # 自动探测并注入 .env 环境变量
        _load_env_file_if_needed()

        gemini_cfg = cfg.get("gemini", {})
        api_key = (
            gemini_cfg.get("api_key")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        model_name = (
            gemini_cfg.get("model")
            or os.environ.get("GEMINI_MODEL")
            or "gemini-3.7-flash"
        )
        timeout = int(gemini_cfg.get("timeout") or os.environ.get("GEMINI_TIMEOUT") or 300)

        opts = stage_options or {}
        temperature = float(opts.get("temperature", 0.2))
        max_thinking_tokens = opts.get("max_thinking_tokens")

        if not api_key:
            raise ValueError(
                "未检测到 GEMINI_API_KEY。请在项目根目录 .env 文件中配置 'GEMINI_API_KEY=your_key' "
                "(可参考 .env.example)，或设置系统环境变量 GEMINI_API_KEY。"
            )

        # 优先使用官方 google-genai SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            config_kwargs = {
                "system_instruction": system_prompt,
                "temperature": temperature,
                "response_mime_type": "application/json",
                # 显式禁用自动函数调用 (AFC)，遵循单次结构化多模态调用的官方最佳实践，消除 Warning
                "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
                "http_options": types.HttpOptions(timeout=timeout * 1000),
            }

            if max_thinking_tokens:
                try:
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=int(max_thinking_tokens)
                    )
                except Exception:
                    pass

            config = types.GenerateContentConfig(**config_kwargs)

            image_part = types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/jpeg",
            )

            response = client.models.generate_content(
                model=model_name,
                contents=[image_part, user_prompt],
                config=config,
            )

            content = getattr(response, "text", "") or ""
            thinking = ""

            # 提取思考内容 (若存在)
            if hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]
                if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                    for part in cand.content.parts:
                        if getattr(part, "thought", False) or getattr(part, "thinking", False):
                            thinking += (getattr(part, "text", "") or "")

            return _parse_content_and_thinking(content, thinking)

        except ImportError:
            # 环境未安装 google-genai 时使用 REST API 兜底
            return self._urllib_post(
                api_key=api_key,
                model_name=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                img_bytes=img_bytes,
                timeout=timeout,
                temperature=temperature,
                max_thinking_tokens=max_thinking_tokens,
            )

    def _urllib_post(
        self,
        api_key: str,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        img_bytes: bytes,
        timeout: int = 300,
        temperature: float = 0.2,
        max_thinking_tokens: int | None = None,
    ) -> tuple[str, str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        b64_img = base64.b64encode(img_bytes).decode("utf-8")

        gen_config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
        }
        if max_thinking_tokens:
            gen_config["thinkingConfig"] = {"thinkingBudget": int(max_thinking_tokens)}

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{
                "parts": [
                    {"text": user_prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                ]
            }],
            "generationConfig": gen_config,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidate = body["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_content_and_thinking(candidate, "")



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

