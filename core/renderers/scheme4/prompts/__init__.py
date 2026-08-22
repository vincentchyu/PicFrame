"""
Scheme4 独立四阶段 Prompt 模块包
"""
from .stage1_spatial import STAGE1_SYSTEM_PROMPT, STAGE1_USER_PROMPT, build_stage1_user_prompt
from .stage2_curatorial import STAGE2_SYSTEM_PROMPT, build_stage2_user_prompt
from .stage3_features import STAGE3_FEATURES_SYSTEM_PROMPT, build_stage3_features_user_prompt
from .stage3_synthesis import STAGE3_SYSTEM_PROMPT as STAGE4_SYSTEM_PROMPT, build_stage3_system_prompt as build_stage4_system_prompt, build_stage3_user_prompt as build_stage4_user_prompt
from .fast_unified import FAST_UNIFIED_SYSTEM_PROMPT, FAST_UNIFIED_USER_PROMPT

__all__ = [
    "STAGE1_SYSTEM_PROMPT",
    "STAGE1_USER_PROMPT",
    "build_stage1_user_prompt",
    "STAGE2_SYSTEM_PROMPT",
    "build_stage2_user_prompt",
    "STAGE3_FEATURES_SYSTEM_PROMPT",
    "build_stage3_features_user_prompt",
    "STAGE4_SYSTEM_PROMPT",
    "build_stage4_system_prompt",
    "build_stage4_user_prompt",
    "FAST_UNIFIED_SYSTEM_PROMPT",
    "FAST_UNIFIED_USER_PROMPT",
]


