"""证据链构建 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class EvidenceChainBuilderSkill(BaseSkill):
    name = "EvidenceChainBuilder"
    description = "构建假设证据链结构"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = input_data.get("hypothesis", "")
        supporting = input_data.get("supporting_evidence", [])
        counter = input_data.get("counter_evidence", [])
        revision_history = input_data.get("revision_history", [])
        final_version = input_data.get("final_version") or hypothesis
        counter_empty_reason = input_data.get("counter_empty_reason", "")

        support_scores = [e.get("relevance_score", 0) * e.get("reliability_score", 0) for e in supporting]
        counter_scores = [e.get("relevance_score", 0) * e.get("reliability_score", 0) for e in counter]
        support_avg = sum(support_scores) / len(support_scores) if support_scores else 0.0
        counter_avg = sum(counter_scores) / len(counter_scores) if counter_scores else 0.0
        balance = round(support_avg - counter_avg * 0.8, 4)

        completeness = min(1.0, len(supporting) / 3.0)
        if counter or counter_empty_reason:
            completeness = min(1.0, completeness + 0.15)
        if revision_history:
            completeness = min(1.0, completeness + 0.1)

        rel_scores = [e.get("reliability_score", 0) for e in supporting + counter]
        citation_reliability = round(sum(rel_scores) / len(rel_scores), 4) if rel_scores else 0.0

        chain = {
            "hypothesis": hypothesis,
            "supporting_evidence": supporting,
            "counter_evidence": counter,
            "evidence_balance_score": balance,
            "revision_history": revision_history,
            "final_version": final_version,
            "chain_completeness": round(completeness, 4),
            "citation_reliability": citation_reliability,
            "support_count": len(supporting),
            "counter_count": len(counter),
            "counter_evidence_empty_reason": counter_empty_reason,
        }
        result.data = {"evidence_chain": chain}
        return result
