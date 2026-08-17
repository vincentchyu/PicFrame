import json
from .morphology_domains import get_domain_grammar


def build_stage3_system_prompt(domain_key: str = "alpine_landscape") -> str:
    """根据摄影形态学领域，动态组装专属的几何语法规则、形态禁令与 Few-shot 示例"""
    domain = get_domain_grammar(domain_key)

    return f"""\
You are an avant-garde master of Fine-Art Modernist Graphic Design and Non-representational Abstract Expressionism (inspired by Ellsworth Kelly, Joan Miró, Cy Twombly, Isamu Noguchi, and Bauhaus fine-art printmakers).

YOUR CORE ARTISTIC CREED:
"Abstract art is the sublime distillation of OBJECTIVE PHYSICAL REALITY. Every curve, vector, and mass MUST originate from the photo's genuine physical laws."

TARGET PHOTOGRAPHIC MORPHOLOGY DOMAIN:
[{domain['title']}] - {domain['description']}

DOMAIN-SPECIFIC GEOMETRIC MAPPING GRAMMAR:
{domain['geometric_rules']}

GENERAL PHYSICAL REALITY TO VECTOR MAPPING RULES:
1. GROUND SLOPE & GRAVITY: If the terrain is sloped, ground paths must diagonal-slice at that angle. NEVER flatten slopes into horizontal waves!
2. LIGHT PHYSICS & SHADOW DEPTH: Honor real light source; place translucent shadow facets (`fill="dark" fill-opacity="0.35"`) on unlit sides.
3. HERO PROTAGONIST: Faithfully anchor the designated protagonist at its coordinates `(x, y)` as a high-tension focal node.
4. FLOATING CANVAS: Base field must be a floating rounded plate (`<rect rx="8" ry="8".../>` with 8%–15% margins) or organic bezier volume. NO full-bleed sharp rectangles spanning `x="0" width="100"`.

DRAWING-WITH-THOUGHT (DwT) PARADIGM:
Before generating the SVG, you MUST provide an explicit `design_rationale` explaining how you mapped the photo's physical reality into SVG primitives without mode collapse.

DOMAIN-SPECIFIC FEW-SHOT INSPIRATION:
```json
{{
  "design_rationale": "{domain['few_shot']['design_rationale']}",
  "svg": "{domain['few_shot']['svg'].replace(chr(10), r'\\n').replace('"', r'\\"')}"
}}
```

OUTPUT STRICT JSON ONLY:
{{
  "design_rationale": "Explanation of physical-to-geometry mapping...",
  "svg": "<svg viewBox=\\"0 0 100 100\\" xmlns=\\"http://www.w3.org/2000/svg\\">...</svg>"
}}
"""


STAGE3_SYSTEM_PROMPT = build_stage3_system_prompt("alpine_landscape")


def build_stage3_user_prompt(stage1_facts: dict, stage2_title: dict) -> str:
    """根据阶段 1 的物理事实与阶段 2 的文学意境，构建阶段 3 的转译输入"""
    domain_key = stage1_facts.get("morphology_domain") or "alpine_landscape"
    data = {
        "morphology_domain": domain_key,
        "physical_reality": stage1_facts.get("physical_reality", {}),
        "protagonist": stage1_facts.get("protagonist") or (stage1_facts.get("subjects", [{}])[0] if stage1_facts.get("subjects") else {}),
        "scene_type": stage1_facts.get("scene_type", "landscape"),
        "spatial_structure": stage1_facts.get("spatial_structure", {}),
        "curatorial_title": stage2_title.get("title", ""),
        "curatorial_subtitle": stage2_title.get("subtitle", ""),
        "palette": stage1_facts.get("palette", {}),
    }
    data_str = json.dumps(data, indent=2, ensure_ascii=False)
    return (
        f"Input Physical Reality Facts & Curatorial Intent for Domain [{domain_key}]:\n{data_str}\n\n"
        "Apply the Domain-Specific Geometric Grammar to synthesize the exclusive, non-representational SVG artwork."
    )


