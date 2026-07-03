"""文献类学术 Skills — PaperReading / DeepResearch / SourceTracing 等。"""
from __future__ import annotations

from typing import Any, Dict, Type

from app.skills.academic._academic_runner import run_academic_llm
from app.skills.base import BaseSkill, SkillResult


def _make_literature_skill(
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


PaperReadingSkill = _make_literature_skill(
    "PaperReading",
    "结构化精读论文摘要与片段，提取方法、结果与局限",
    "paper_reading",
    "Paper-Reading — 论文精读能力适配",
)
DeepResearchSkill = _make_literature_skill(
    "DeepResearch",
    "基于研究问题与文献事实进行深度调研与空白分析",
    "deep_research",
    "Deep-Research — 深度文献调研能力适配",
)
SourceTracingSkill = _make_literature_skill(
    "SourceTracing",
    "追溯主张与引用来源的对应关系，标注可追溯性",
    "source_tracing",
    "Source-Tracing — 来源追溯能力适配",
)
ResearchGenealogySkill = _make_literature_skill(
    "ResearchGenealogy",
    "梳理研究问题的学术谱系与演进脉络",
    "research_genealogy",
    "Research-Genealogy — 研究谱系能力适配",
)
ClaudeScholarSkill = _make_literature_skill(
    "ClaudeScholar",
    "跨文献综合机制解释与可检验推论",
    "claude_scholar",
    "Claude-Scholar — 学术综合能力适配",
)
PaperSkill = _make_literature_skill(
    "PaperSkill",
    "提取论文核心贡献与可复用实验方法",
    "paper_skill",
    "Paper-Skill — 论文分析能力适配",
)
