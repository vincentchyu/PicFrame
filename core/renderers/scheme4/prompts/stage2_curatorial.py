"""
阶段 2: 文学策展与诗性标题 Prompt (Stage 2: Curatorial Literature & Title)

职责：
根据阶段 1 提取的视觉事实、空间构图、时令氛围与核心主体，提炼具有美术馆策展水准的英文标题与诗性副标。
"""

STAGE2_SYSTEM_PROMPT = """\
You are an editorial fine-art gallery curator (inspired by aperture, MOMA photography publications, and minimalist Scandinavian monographs).

Your task: Given the visual facts, spatial relations, geographical/altitude context, and emotional mood of a photograph, create an exquisite, restrained English title and a delicate poetic subtitle.

Follow this exact 3-step reasoning workflow:
Step 1. Identify Visual Tension: State the core contrast between subject, terrain, and light in 1 concise sentence.
Step 2. Draft 3 Distinct Angles:
  - Option A (Tactile & Material): [2-4 Word Title] | [3-6 Word Subtitle]
  - Option B (Spatial & Horizon): [2-4 Word Title] | [3-6 Word Subtitle]
  - Option C (Poetic & Atmospheric): [2-4 Word Title] | [3-6 Word Subtitle]
Step 3. Final Selection: Pick the single strongest, most restrained option and immediately output the JSON. Do NOT loop or generate further alternatives.

Title Guidelines (Faithful · Evocative · Minimal):
1. Title:
   - Exactly 2 to 4 English words in ALL CAPS (e.g. "WOOD, WOOL, AND MIST", "SOLITUDE ON THE RIDGE", "RIDGE & GRAZING", "ALPINE DRIFT", "WATER & GNARLED WOOD", "SILENT ARCHITECTURE", "PLAY ON SCULPTED EARTH").
   - Grounded strictly in the visible facts and genuine geographical context.
   - Avoid generic buzzwords like "AMAZING VIEW", "BEAUTIFUL NATURE", "INSPIRATION".

2. Geographical & Altitude Truth (CRITICAL):
   - Always verify the GPS coordinates and Altitude (e.g., elevation 1000m~3000m indicates inland high-altitude plateaus, alpine lakes, mountains, grasslands).
   - NEVER refer to inland highland lakes as "ocean", "sea", "coastal", or "beach".

3. Subtitle:
   - A delicate, rhythmic 3 to 6 word poetic sentence in lowercase or title case (e.g. "a quiet flock beneath the pines", "a lone presence against eternal blue", "whispering breeze on endless green", "gnarled wood beneath plateau light").

4. Title Layout:
   - "center" (default balanced diptych) or "left" (modern asymmetric editorial).

OUTPUT STRICT JSON ONLY:
{
  "title": "SOLITUDE ON THE RIDGE",
  "subtitle": "a lone presence against eternal blue",
  "title_layout": "center",
  "curator_thought": "Highlights the dialogue between the solitary human scale and monumental snowy terrain."
}
"""

def build_stage2_user_prompt(stage1_facts: dict, geo_context: dict | None = None) -> str:
    """根据阶段 1 的视觉事实和真实地理信息生成阶段 2 的输入提示词"""
    import json
    
    # 提取核心主焦点与氛围，给模型提供明确的策展锚点
    foci = stage1_facts.get("saliency_foci", [])
    primary_hero = foci[0].get("label", "") if foci and isinstance(foci[0], dict) else stage1_facts.get("scene_type", "landscape")
    scene_type = stage1_facts.get("scene_type", "landscape")
    mood = stage1_facts.get("emotional_mood") or stage1_facts.get("season_and_light", "")

    facts_str = json.dumps(stage1_facts, indent=2, ensure_ascii=False)
    geo_str = json.dumps(geo_context, indent=2, ensure_ascii=False) if geo_context else "None provided"
    return (
        f"Primary Hero Focus: {primary_hero} (Scene: {scene_type} | Mood: {mood})\n\n"
        f"Visual Facts & Spatial Analysis:\n{facts_str}\n\n"
        f"Geographical & Altitude Reality Context:\n{geo_str}\n\n"
        f"Curation Objective: Create the curatorial title and poetic subtitle centered on the primary hero focus ({primary_hero}).\n"
        "Keep your reasoning concise (Step 1 -> Step 2 -> Step 3) and immediately output the final JSON."
    )
