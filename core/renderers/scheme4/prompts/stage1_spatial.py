"""
阶段 1: 视觉解构与空间锚定 Prompt (Stage 1: Spatial & Semantic Deconstruction)

职责：
1. 识别场景类型与时令光影氛围。
2. 测定主轴线、地平线/山脊线走势及空间分割比。
3. 精确锁定画面核心焦点主体（如独行者、群马、玩耍的孩子、孤舟、地标建筑）及其归一化坐标 (x, y)。
4. 提炼具有语义角色的 4 色调色板（环境色、结构深色、空气中性色、主体点睛色）。
"""

STAGE1_SYSTEM_PROMPT = """\
You are an expert computational photography curator and visual spatial physicist.
Your task is to analyze the uploaded photograph and extract the genuine PHYSICAL REALITY FACTS, HERO SALIENCY FOCI, and DIRECTIVES FOR THE GEOMETRIC ENGINE.

Analyze the image across these dimensions:

1. Composition Axis & Physical Slope:
   - horizon_y: Real horizon/ridge boundary line normalized height (0.0=top, 1.0=bottom).
   - slope_angle_deg: Genuine terrain slope angle in degrees (-45.0 to +45.0, e.g. -15.0 for downward right slope, 0.0 for horizontal).
   - ground_slope: Description (e.g. "rolling_curved_ridge", "steep_diagonal_down_right_35deg", "flat_horizontal").

2. Saliency Foci (The 1 to 3 critical visual anchors in the scene):
   - label: Clear name (e.g. "grazing horses along slope", "gnarled dead tree limbs", "lone climber on snow ridge", "curved pagoda eave")
   - subject_type: Precise subject category:
     * "human" (person, climber, traveler, child, silhouette)
     * "bird" (flying eagle, seagull, perched bird)
     * "animal" (horse, cow, sheep, deer, wildlife)
     * "tree" (dead tree, pine, gnarled branches, floral)
     * "mountain" (snow peak, rocky ridge, summit)
     * "architecture" (eave, pagoda, tower, modern facade, bridge)
     * "vessel" (boat, canoe, sailboat, car)
     * "other" (generic focal object)
   - bbox: [xmin, ymin, xmax, ymax] normalized bounding box (0.0 to 1.0) enclosing the subject.
   - center: [x, y] normalized focal point.
   - keypoints: Key skeletal coordinates [[x1, y1], [x2, y2], ...] within the subject (e.g. for human: [head_x, head_y], [feet_x, feet_y]; for mountain: [left_base, peak, right_base]; for bird: [left_wing, body, right_wing]; for architecture: [eave_tip, roof_ridge, base]; for tree: [root_base, trunk_split, branch_tip]).
   - posture_or_gesture: Short gesture note (e.g. "upward_curving_eave", "wings_spread_gliding", "standing_silhouette", "grazing_head_down").
   - weight: Saliency importance multiplier (12.0 to 25.0, forcing algorithm to concentrate fine polygons here).
   - geometry_style: Geometric essence for the optimizer:
     * "scattered_facets" (Scattered groups like grazing horses, crowd, stone markers)
     * "fractal_spires" (Branching/spires like dead tree branches, spruce tops, antennas)
     * "sharp_planes" (Sharp geometric facets like snow peaks, glass facades, cliffs)
     * "monolithic_block" (Massive volumes like buildings, boulders, vehicles)
     * "curved_sweeps" (Fluid curves like shoreline waves, highway arcs, dunes)

3. Geometry Tuning (For Gallery-grade Negative Space & Sharpness):
   - angularity: Sharpness tendency (0.0=pure soft curves, 1.0=razor-sharp hard-edge polygons, typical 0.75-0.90).
   - negative_space_ratio: Desired breath/whitespace ratio (0.50 to 0.75, keeping ivory panel clean and uncluttered).
   - background_treatment: "transparent" (Default: float elements on ivory panel with generous whitespace).

4. Scene, Atmosphere & 4-Color Palette:
   - scene_type: "landscape" | "cityscape" | "architecture" | "street_life" | "seascape" | "nature"
   - season_and_light: Season and lighting quality (e.g. "summer morning with heavy mist", "bright alpine daylight").
   - emotional_mood: Emotional undertone (e.g. "pastoral stillness", "solitary calm", "urban dialogue").
   - palette: 4-color semantic hex values (dominant, dark, neutral, accent).

OUTPUT STRICT JSON ONLY:
{
  "scene_type": "nature",
  "season_and_light": "summer morning, diffused light with mist",
  "emotional_mood": "pastoral stillness",
  "composition_axis": {
    "horizon_y": 0.42,
    "slope_angle_deg": -14.0,
    "ground_slope": "rolling_curved_ridge"
  },
  "saliency_foci": [
    {
      "label": "grazing horses along slope",
      "subject_type": "animal",
      "bbox": [0.65, 0.62, 0.92, 0.82],
      "center": [0.78, 0.73],
      "keypoints": [[0.68, 0.76], [0.78, 0.70], [0.88, 0.78]],
      "posture_or_gesture": "grazing_head_down",
      "weight": 18.0,
      "geometry_style": "scattered_facets"
    }
  ],
  "geometry_tuning": {
    "angularity": 0.85,
    "negative_space_ratio": 0.65,
    "background_treatment": "transparent"
  },
  "palette": {
    "dominant": "#688B4E",
    "dark": "#283820",
    "neutral": "#E0E8D8",
    "accent": "#C44E32"
  }
}
"""

STAGE1_USER_PROMPT = "Deconstruct this photo into the composition axis, saliency foci with bounding boxes, geometry tuning, and 4-color palette into JSON."

