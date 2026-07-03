"""报告格式与投稿规范类学术 Skills。"""
from __future__ import annotations

from typing import Any, Dict, Type

from app.skills.academic._academic_runner import run_academic_llm
from app.skills.base import BaseSkill, SkillResult


def _make_format_skill(
    name: str,
    description: str,
    spec_key: str,
    source_reference: str,
) -> Type[BaseSkill]:
    class _Skill(BaseSkill):
        async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
            result = SkillResult(success=True)
            data = run_academic_llm(
                spec_key,
                input_data,
                context,
                prompt_version=f"academic_{spec_key}",
            )
            result.data = {**data, "skill": name, "spec_key": spec_key}
            if data.get("warnings"):
                for w in data["warnings"]:
                    result.add_warning(str(w))
            return result

    _Skill.name = name
    _Skill.description = description
    _Skill.source_reference = source_reference
    return _Skill


EmpiricalPaperSkill = _make_format_skill(
    "EmpiricalPaper",
    "按实证研究规范审查变量、对照、样本与统计方法",
    "empirical_paper",
    "Empirical-Paper — 实证论文规范能力适配",
)
NaturePaperSkill = _make_format_skill(
    "NaturePaper",
    "按顶刊短论文叙事结构优化摘要与核心论述",
    "nature_paper",
    "Nature-Paper — 顶刊叙事能力适配",
)
CCFASkill = _make_format_skill(
    "CCFASkill",
    "按 CCF-A 会议规范审查 baseline、消融与实验公平性",
    "ccfa_skill",
    "CCFA-Skill — 顶会论文规范能力适配",
)
PaperPilotSkill = _make_format_skill(
    "PaperPilot",
    "生成从研究计划到可投稿论文的分阶段路线图",
    "paper_pilot",
    "Paper-Pilot — 论文写作路线图能力适配",
)
