"""研究框架类学术 Skills。"""
from __future__ import annotations

from typing import Any, Dict, Type

from app.skills.academic._academic_runner import run_academic_llm
from app.skills.base import BaseSkill, SkillResult


def _make_research_skill(
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


QuestionValidatorSkill = _make_research_skill(
    "QuestionValidator",
    "校验研究问题是否具体、可检验、边界清晰",
    "question_validator",
    "Question-Validator — 研究问题校验能力适配",
)
AcademicResearchSkills = _make_research_skill(
    "AcademicResearchSkills",
    "将研究问题拆解为可验证子问题与知识增量框架",
    "academic_research",
    "Academic-Research-Skills — 学术研究框架能力适配",
)
ResearchSkills = _make_research_skill(
    "ResearchSkills",
    "列出研究所需能力、资源与验证里程碑",
    "research_skills",
    "Research-Skills — 研究设计要点能力适配",
)
