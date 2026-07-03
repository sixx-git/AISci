"""衍生输出类学术 Skills — 专利 / 故事板 / Beamer。"""
from __future__ import annotations

from typing import Any, Dict, Type

from app.skills.academic._academic_runner import run_academic_llm
from app.skills.base import BaseSkill, SkillResult


def _make_derivative_skill(
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


PaperToPatentSkill = _make_derivative_skill(
    "PaperToPatent",
    "从研究内容提取可专利技术方案与权利要求方向",
    "paper_to_patent",
    "Paper-to-Patent — 论文转专利要点能力适配",
)
PaperToStoryboardSkill = _make_derivative_skill(
    "PaperToStoryboard",
    "将研究叙事转化为汇报故事板分镜",
    "paper_to_storyboard",
    "Paper-to-Storyboard — 故事板生成能力适配",
)
Paper2BeamerSkill = _make_derivative_skill(
    "Paper2Beamer",
    "生成 Beamer 学术演示文稿大纲与每页要点",
    "paper2beamer",
    "Paper2Beamer — 幻灯片大纲能力适配",
)
