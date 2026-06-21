"""引用完整性检查 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.literature.citation_grounding_skill import CitationGroundingSkill
from app.skills.evidence_reasoning._utils import PLACEHOLDER_TITLES, normalize_text


class CitationIntegrityCheckSkill(BaseSkill):
    name = "CitationIntegrityCheck"
    description = "检查证据链引用是否来自可验证来源，拒绝虚构文献"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        supporting = input_data.get("supporting_evidence", [])
        counter = input_data.get("counter_evidence", [])
        citation_map = input_data.get("citation_map", [])
        facts = input_data.get("facts", [])

        refs = []
        for ev in supporting + counter:
            title = ev.get("source_title", "")
            if title and normalize_text(title) not in PLACEHOLDER_TITLES:
                refs.append(title)

        grounding = CitationGroundingSkill()
        ground_res = await grounding.run(
            {
                "references": refs,
                "citation_map": citation_map,
                "literature_facts": facts,
                "evidence_facts": facts,
            },
            context,
        )

        verified = ground_res.data.get("verified_references", []) if ground_res.data else []
        rejected = ground_res.data.get("rejected_references", []) if ground_res.data else []

        if rejected:
            result.add_warning(f"检测到 {len(rejected)} 条不可验证引用，已从证据链剔除")
            rejected_set = {normalize_text(r) for r in rejected}
            supporting = [
                e for e in supporting
                if normalize_text(e.get("source_title", "")) not in rejected_set
            ]
            counter = [
                e for e in counter
                if normalize_text(e.get("source_title", "")) not in rejected_set
            ]

        result.data = {
            "verified_count": len(verified),
            "rejected_count": len(rejected),
            "verified_references": verified,
            "rejected_references": rejected,
            "filtered_supporting": supporting,
            "filtered_counter": counter,
            "passed": len(rejected) == 0,
        }
        return result
