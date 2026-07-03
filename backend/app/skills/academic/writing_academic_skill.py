"""写作类学术 Skills。"""
from __future__ import annotations

from typing import Any, Dict, Type

from app.skills.academic._academic_runner import run_academic_llm
from app.skills.base import BaseSkill, SkillResult


def _make_writing_skill(
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


AcademicWritingSkills = _make_writing_skill(
    "AcademicWritingSkills",
    "学术写作逻辑与论证强度诊断，给出段落级修改建议",
    "academic_writing",
    "Academic-Writing-Skills — 学术写作能力适配",
)
WriteChineseSkill = _make_writing_skill(
    "WriteChinese",
    "中文学术表达优化：术语规范、去口语化与翻译腔",
    "write_chinese",
    "Write-Chinese — 中文学术写作能力适配",
)
PaperWriterSkill = _make_writing_skill(
    "PaperWriter",
    "根据已有内容起草或补全报告/论文章节",
    "paper_writer",
    "Paper-Writer — 论文章节起草能力适配",
)
AcademicPaperSkills = _make_writing_skill(
    "AcademicPaperSkills",
    "检查报告是否符合 IMRaD 学术论文结构规范",
    "academic_paper",
    "Academic-Paper-Skills — 论文结构能力适配",
)
