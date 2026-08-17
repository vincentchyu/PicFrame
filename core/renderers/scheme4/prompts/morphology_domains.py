"""
8 大摄影视觉形态学领域专属语法库 (The 8 Photographic Morphology Domains Grammar Library)

为彻底消解大模型在通用抽象生成时的“模式坍塌”（如将所有建筑画成山峰、将古塔画成方块、将老树画成帆船），
根据 Stage 1 识别出的形态领域，动态组装专属的几何语法规则、负向形态禁令与针对性 Few-shot 示范。
"""

DOMAIN_GRAMMARS = {
    # ── 1. 现代都市 / 摩天楼 / 天际线 / 桥梁 ─────────────────────────────────
    "urban_architecture": {
        "title": "Modern Urban & Architectural Skyline",
        "description": "Modern skyscrapers, high-rise towers, layered city grids, bridge geometry, glass facade reflections.",
        "geometric_rules": """\
- USE VERTICAL RECTILINEAR MASSES: Layer stepped, varying-height vertical columns and trapezoids (`<rect x="..." y="..." width="..." height="..." rx="2"/>` or `<polygon points="..."/>`).
- USE PARALLEL LIGHT HATCHING: Echo window grids and structural lines using subtle vertical/horizontal line arrays (`<line x1="..." y1="..." x2="..." y2="..." stroke="neutral" stroke-width="0.8" stroke-opacity="0.6"/>`).
- PERSPECTIVE FACETS & SUNLIT SIDES: Split skyscraper faces into sunlit and shadow facets using crisp geometric polygons.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to draw triangular mountain peaks, organic rolling grass waves, or fluid floral curves for skyscrapers!""",
        "few_shot": {
            "design_rationale": "Deconstructed the city skyline into layered vertical geometric monoliths with high-contrast sunlight facets and subtle grid vectors.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="14" width="84" height="72" rx="8" fill="neutral" fill-opacity="0.25"/>
  <rect x="18" y="45" width="14" height="42" rx="2" fill="dark" fill-opacity="0.85"/>
  <polygon points="36,87 36,30 48,22 48,87" fill="dominant" fill-opacity="0.85"/>
  <polygon points="48,87 48,22 56,26 56,87" fill="dark" fill-opacity="0.90"/>
  <rect x="60" y="38" width="12" height="49" rx="2" fill="dominant" fill-opacity="0.70"/>
  <line x1="12" y1="87" x2="88" y2="87" stroke="dark" stroke-width="1.2"/>
  <circle cx="52" cy="24" r="2.2" fill="accent"/>
</svg>"""
        }
    },

    # ── 2. 东方古建 / 寺庙 / 佛塔 / 飞檐 / 雕塑 ──────────────────────────────
    "classical_heritage": {
        "title": "Classical Heritage & Asian Architecture",
        "description": "Ancient temples, tiered pagodas, sweeping upward curved eaves (飞檐), dragon ridge roofs, stone statues.",
        "geometric_rules": """\
- USE SWEEPING UPWARD EAVE ARCS: Render traditional roofs using upward-flaring quadratic/bezier curves (`<path d="M 25 45 Q 50 48 75 45 C 78 42, 82 40, 84 38 L 78 48 Q 50 50 22 48 Z"/>`).
- TIERED PAGODA SILHOUETTE: Stack progressively tapering tiered roof levels with horizontal rhythm and vertical central axis.
- GESTURAL STATUE FLUIDITY: Represent Buddha/statues with continuous serene vertical calligraphic arcs (`stroke-linecap="round"`), not blocky robots.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to render ancient pagodas as single-story plain flat boxes or simple house icons!""",
        "few_shot": {
            "design_rationale": "Distilled the tiered wooden pagoda into three ascending sweeping eave arcs paired with a serene vertical statue presence curve.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="14" width="80" height="72" rx="8" fill="neutral" fill-opacity="0.30"/>
  <path d="M 46 22 L 54 22 L 50 16 Z" fill="dark"/>
  <path d="M 38 32 Q 50 35 62 32 C 65 30, 68 28, 70 26 L 66 35 Q 50 37 34 35 Z" fill="dark" fill-opacity="0.90"/>
  <path d="M 32 46 Q 50 50 68 46 C 72 43, 76 40, 78 38 L 74 49 Q 50 52 26 49 Z" fill="dominant" fill-opacity="0.85"/>
  <path d="M 26 62 Q 50 67 74 62 C 80 58, 85 54, 88 51 L 82 66 Q 50 70 18 66 Z" fill="dark" fill-opacity="0.95"/>
  <path d="M 22 78 C 22 55, 28 45, 30 38" fill="none" stroke="accent" stroke-width="2.2" stroke-linecap="round"/>
</svg>"""
        }
    },

    # ── 3. 树木 / 枝桠 / 森林生态 ───────────────────────────────────────────
    "botanical_trees": {
        "title": "Botanical Trees & Skeletal Branching",
        "description": "Ancient solitary trees, winter branching limbs, conifer spruce forests, organic canopy masses.",
        "geometric_rules": """\
- SKELETAL RADIAL BRANCHING: For bare/solitary trees, synthesize upward-spreading calligraphic stroke paths (`<path d="M 48 85 L 48 55 M 48 55 L 32 35 M 48 55 L 65 38 M 32 35 L 24 22 M 32 35 L 38 18 M 65 38 L 76 25" stroke="dark" stroke-width="2" stroke-linecap="round"/>`).
- CONIFER / SPRUCE SPIRES: For pine forests, synthesize vertical upward jagged spires (`<path d="M 35 60 L 38 36 L 41 58 L 45 30 L 49 55 L 53 38 L 56 60 Z"/>`).
- ORGANIC CANOPY MASSES: Soft rounded cloud-like bezier color fields for lush deciduous trees.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to draw a single hollow triangle or sailboat shape for an ancient branching tree!""",
        "few_shot": {
            "design_rationale": "Captured the ancient tree's dramatic skeletal branching vectors ascending toward the sky with calligraphic stroke tension.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="14" width="80" height="72" rx="8" fill="neutral" fill-opacity="0.30"/>
  <path d="M 8 72 C 35 68, 65 76, 92 70 L 92 86 L 8 86 Z" fill="dominant" fill-opacity="0.40"/>
  <path d="M 46 84 C 47 70, 45 58, 48 48 M 48 48 C 42 38, 30 30, 24 20 M 48 48 C 55 36, 68 28, 76 18 M 32 34 L 20 32 M 35 26 L 38 14 M 60 38 L 74 42 M 66 26 L 68 12" fill="none" stroke="dark" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="68" cy="46" r="2.4" fill="accent"/>
</svg>"""
        }
    },

    # ── 4. 高山 / 地貌 / 冰川 / 峡谷 ─────────────────────────────────────────
    "alpine_landscape": {
        "title": "Alpine Mountains & Geological Slopes",
        "description": "Snow peaks, glacial ridges, steep slopes, mountain roads, rocky precipices.",
        "geometric_rules": """\
- FAITHFUL GROUND SLOPE: Honor true slope angle (e.g. 25°–40° diagonal slice across the canvas). Do NOT flatten steep ridges!
- GLACIAL FACETS & RIDGE VECTORS: Crisp angular lines separating sunlit snow from deep shadow faces (`<polygon points="..."/>` or sharp `<path d="M...L..."/>`).
- ROAD VECTORS: Fluid curving baseline lines tracing mountain passes (`<path d="M ... Q ..." fill="none" stroke="dark" stroke-width="1.8"/>`).
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to use symmetrical mini-pyramids for asymmetrical natural mountain ranges!""",
        "few_shot": {
            "design_rationale": "Translated the 35-degree ascending mountain ridge with sunlit snow facet and the sweeping curving pass road.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="14" width="84" height="72" rx="8" fill="neutral" fill-opacity="0.30"/>
  <path d="M 8 75 C 32 68, 65 46, 92 34 L 92 86 L 8 86 Z" fill="dominant" fill-opacity="0.80"/>
  <polygon points="42,56 68,36 92,34 92,60 55,70" fill="dark" fill-opacity="0.35"/>
  <path d="M 12 78 Q 45 74 72 58 T 90 42" fill="none" stroke="dark" stroke-width="2.0" stroke-linecap="round"/>
  <circle cx="48" cy="72" r="2.5" fill="accent"/>
</svg>"""
        }
    },

    # ── 5. 海洋 / 湖泊 / 水系 / 倒影 ─────────────────────────────────────────
    "water_seascape": {
        "title": "Water, Lakes & Seascape Horizons",
        "description": "Oceans, calm lakes, water surface reflections, horizontal horizon datums, shores.",
        "geometric_rules": """\
- HORIZONTAL DATUM LINES: Crisp, expansive horizontal waterlines balancing sky and depth.
- LAYERED REFLECTIVE BANDS: Staggered, translucent horizontal bands representing shimmering water planes (`fill-opacity="0.25"` to `0.70"`).
- DELICATE SHORE ARCS: Sweeping gentle coastline bezier curves.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to create tall jagged vertical spires for calm flat water surfaces!""",
        "few_shot": {
            "design_rationale": "Established a tranquil horizontal datum line layered with soft reflective light bands and a solitary boat/focal anchor.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="16" width="84" height="68" rx="8" fill="neutral" fill-opacity="0.30"/>
  <rect x="8" y="52" width="84" height="32" rx="4" fill="dominant" fill-opacity="0.65"/>
  <path d="M 15 62 C 40 58, 65 65, 85 60" fill="none" stroke="neutral" stroke-width="1.2" stroke-opacity="0.8"/>
  <path d="M 22 72 C 45 68, 60 74, 80 70" fill="none" stroke="dark" stroke-width="0.8" stroke-opacity="0.5"/>
  <circle cx="65" cy="48" r="2.8" fill="accent"/>
  <line x1="8" y1="52" x2="92" y2="52" stroke="dark" stroke-width="1.0" stroke-opacity="0.7"/>
</svg>"""
        }
    },

    # ── 6. 街头纪实 / 人物动能 / 对话与情绪 ─────────────────────────────────
    "human_street_life": {
        "title": "Street Documentary, Human Gestures & Emotional Dialogue",
        "description": "Street figures, lively conversation, shared laughter, kinetic gestures, reaching hands, labor, crowd interaction.",
        "geometric_rules": """\
- SKELETAL GESTURAL VECTORS (THE CORE ESSENCE OF HUMAN PRESENCE):
  * Human cognitive recognition relies on: HEAD CIRCLE (`<circle cx=".." cy=".." r="2.8"/>`) + KINETIC TORSO/LIMB PATHS (`<path d="M .. L .. L .." stroke="dark" stroke-width="2.2" stroke-linecap="round"/>`).
  * Express human presence via clean, calligraphic stick-figure gestures that capture posture and weight!
- EMOTIONAL DYNAMICS & CONVERSATIONAL ENERGY:
  * **Lively Conversation / Shared Laughter**: Two figures with heads slightly tilted, bodies leaning into each other, connected by a vibrant upward conversational energy arc (`<path d="M 38 46 Q 48 34 58 44" fill="none" stroke="accent" stroke-width="1.8" stroke-linecap="round"/>`) or a luminous warm spark node (`<circle fill="accent"/>`).
  * **Solitary Wanderer / Climber**: Torso leaning forward 15° into the ascent, rooted on the terrain datum.
  * **Bending Labor / Craft**: Curved arching spine (`Q` downward bezier) with downward-reaching arm vectors.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to reduce humans into unrecognizable shapeless pink blobs or generic gray boxes! You MUST draw the expressive skeletal gestures (head + dynamic limb vectors) so human emotion and interaction are instantly recognized!""",
        "few_shot": {
            "design_rationale": "Translated two figures engaged in lively laughter using tilted head nodes, converging gestural body vectors, and a joyful conversational tension arc connecting them.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="14" width="84" height="72" rx="8" fill="neutral" fill-opacity="0.25"/>
  <!-- Figure A (Tilting head back in laughter): Head + Expressive Torso/Legs -->
  <circle cx="32" cy="36" r="3.2" fill="accent"/>
  <path d="M 32 40 L 29 58 L 22 78 M 29 58 L 36 78 M 30 48 L 40 54" fill="none" stroke="dark" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- Figure B (Leaning forward listening/talking): Head + Torso/Legs -->
  <circle cx="58" cy="38" r="3.0" fill="dark"/>
  <path d="M 58 42 L 60 60 L 54 78 M 60 60 L 68 78 M 59 50 L 48 56" fill="none" stroke="dark" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- Conversational laughter arc connecting them -->
  <path d="M 36 44 Q 45 32 54 42" fill="none" stroke="accent" stroke-width="1.6" stroke-linecap="round" stroke-dasharray="0.5 3"/>
  <line x1="12" y1="80" x2="88" y2="80" stroke="dark" stroke-width="1.0" stroke-opacity="0.4"/>
</svg>"""
        }
    },

    # ── 7. 动物群落 / 牧场牲畜 / 生态体态 ───────────────────────────────────
    "animal_wildlife": {
        "title": "Pasture Herds, Quadruped Gestures & Wildlife Ecology",
        "description": "Grazing horses, cattle, sheep flocks, low-head feeding posture, wildlife motion.",
        "geometric_rules": """\
- QUADRUPED SKELETAL ARCHITECTURE (HOW HUMANS RECOGNIZE ANIMALS):
  * Quadruped essence consists of: HORIZONTAL SPINE BEAM (`<line>`/`<path>`) + LOW-DOWN REACHING NECK (`neck down to ground level`) + STANCE LEG PILLARS (`<line>`/`<path>`).
- LOW-HEAD GRAZING POSTURE (HORSES / CATTLE / SHEEP):
  * **Grazing Horse**: Horizontal back line (`M 68 64 L 78 64`), elongated neck slanting down to ground (`M 68 64 L 60 74`), head circle at pasture level, and clean leg lines down to terrain!
  * **Contour Sheep Stream**: White/light organic nodes arranged in a descending stream along the slope contour line, anchored by a leading grazing silhouette.
- TOPOGRAPHICAL INTEGRATION: Animals must stand firmly on or graze along the pasture bezier slope.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to draw animals as tiny isolated round dots or flat solid domes! You MUST synthesize the authentic low-head grazing quadruped skeletal gestures!""",
        "few_shot": {
            "design_rationale": "Rendered rolling pasture slopes with authentic low-head grazing horse skeletal gestures (spine beam, downward neck, leg pillars) anchored on the green terrain.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="14" width="84" height="72" rx="8" fill="neutral" fill-opacity="0.30"/>
  <!-- Rolling pasture slope -->
  <path d="M 8 52 C 35 38, 68 60, 92 46 L 92 86 L 8 86 Z" fill="dominant" fill-opacity="0.80"/>
  <path d="M 8 68 C 40 58, 70 76, 92 64 L 92 86 L 8 86 Z" fill="dominant" fill-opacity="0.90"/>
  <!-- Grazing Horse 1 (Spine + Low neck to ground + Legs) -->
  <path d="M 68 60 L 78 60 M 68 60 L 61 70 M 61 70 L 59 73" fill="none" stroke="accent" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="68" y1="60" x2="67" y2="74" stroke="accent" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="77" y1="60" x2="78" y2="74" stroke="accent" stroke-width="1.8" stroke-linecap="round"/>
  <circle cx="59" cy="72" r="1.6" fill="accent"/>
  <!-- Grazing Horse 2 (Smaller on distance) -->
  <path d="M 44 52 L 51 52 M 44 52 L 39 60" fill="none" stroke="dark" stroke-width="1.8" stroke-linecap="round"/>
  <line x1="44" y1="52" x2="43" y2="63" stroke="dark" stroke-width="1.4" stroke-linecap="round"/>
  <line x1="50" y1="52" x2="51" y2="63" stroke="dark" stroke-width="1.4" stroke-linecap="round"/>
  <circle cx="38" cy="61" r="1.2" fill="dark"/>
</svg>"""
        }
    },

    # ── 8. 空灵留白 / 极简光影 ───────────────────────────────────────────────
    "minimalist_fine_art": {
        "title": "Minimalist Fine Art & Negative Space",
        "description": "Spiritual negative space, solitary shadows, monolithic light cuts, extreme minimalist compositions.",
        "geometric_rules": """\
- EXTREME NEGATIVE SPACE: Maintain 75%–85% pure open breathing space.
- SINGLE HIGH-TENSION VECTOR / WEDGE: A single decisive angled shadow slice, pure geometric aperture, or monolithic beam of light.
- MASTERFUL CHROMATIC DIALOGUE: High-contrast pairing between dominant atmosphere and a solitary accent spark.
- CRITICAL NEGATIVE CONSTRAINT: STRICTLY FORBIDDEN to clutter the canvas with multiple decorative objects!""",
        "few_shot": {
            "design_rationale": "Distilled the composition into an immense field of negative space pierced by a single diagonal shadow wedge and a luminous focal node.",
            "svg": """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="12" y="16" width="76" height="68" rx="10" fill="neutral" fill-opacity="0.25"/>
  <polygon points="20,80 50,30 62,30 35,80" fill="dark" fill-opacity="0.85"/>
  <circle cx="56" cy="30" r="3.2" fill="accent"/>
</svg>"""
        }
    },
}


def get_domain_grammar(domain_key: str) -> dict:
    """获取指定形态领域的语法规则与 Few-shot，带健全回退"""
    if not domain_key or domain_key not in DOMAIN_GRAMMARS:
        domain_key = "alpine_landscape"
    return DOMAIN_GRAMMARS[domain_key]
