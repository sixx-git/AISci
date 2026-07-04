"""中文写作 Skill 包"""
from app.skills.chinese_writing.chinese_writing_skills import (
    ChineseStyleDiagnosisSkill,
    HumanizeRewriteSkill,
    RevisionReasonSkill,
    MultiVersionRewriteSkill,
    ChineseGECCheckSkill,
    ToneControlSkill,
)

__all__ = [
    "ChineseStyleDiagnosisSkill",
    "HumanizeRewriteSkill",
    "RevisionReasonSkill",
    "MultiVersionRewriteSkill",
    "ChineseGECCheckSkill",
    "ToneControlSkill",
]
