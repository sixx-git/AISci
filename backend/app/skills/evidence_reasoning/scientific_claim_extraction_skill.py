"""科学主张提取 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class ScientificClaimExtractionSkill(BaseSkill):
    name = "ScientificClaimExtraction"
    description = "从假设与文献事实中提取可验证科学主张"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = input_data.get("hypothesis", "")
        rationale = input_data.get("rationale", "")
        facts = input_data.get("facts", [])

        claims: List[Dict[str, Any]] = []
        if hypothesis:
            claims.append({"claim_id": "claim_main", "text": hypothesis.strip(), "type": "hypothesis"})
        if rationale:
            for i, part in enumerate([p.strip() for p in rationale.split("。") if p.strip()][:3]):
                claims.append({"claim_id": f"claim_r_{i}", "text": part, "type": "rationale"})

        for fact in facts[:5]:
            text = fact.get("content") or fact.get("fact_text") or ""
            if text:
                claims.append(
                    {
                        "claim_id": fact.get("fact_id", f"claim_f_{len(claims)}"),
                        "text": text[:300],
                        "type": "literature_fact",
                        "source_title": fact.get("source_paper_title", ""),
                    }
                )

        result.data = {"claims": claims, "claim_count": len(claims)}
        return result
