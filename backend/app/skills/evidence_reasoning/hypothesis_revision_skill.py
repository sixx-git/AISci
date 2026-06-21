"""假设修正 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class HypothesisRevisionSkill(BaseSkill):
    name = "HypothesisRevision"
    description = "基于支持/反对证据修正假设"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        original = input_data.get("hypothesis", "")
        supporting = input_data.get("supporting_evidence", [])
        counter = input_data.get("counter_evidence", [])

        refute_claims = [c.get("claim", "") for c in counter if c.get("stance") == "refute"]
        support_titles = [s.get("source_title", "") for s in supporting[:2] if s.get("source_title")]

        what_changed: List[str] = []
        remaining_risks: List[str] = []
        revised = original

        if refute_claims:
            limitation = refute_claims[0][:120]
            revised = (
                f"{original.rstrip('。')}；但在以下条件下仍需谨慎验证：{limitation}"
            )
            what_changed.append("加入反对证据指出的限制条件")
            remaining_risks.extend(refute_claims[:3])
        elif counter:
            remaining_risks.append("存在中性/弱反对证据，假设边界需进一步界定")

        if support_titles and "基于" not in revised[:20]:
            revised = f"基于 {support_titles[0]} 等文献证据，{revised}"
            what_changed.append("补充支持文献来源表述")

        if not what_changed:
            what_changed.append("证据平衡下维持原假设表述")

        revision = {
            "original_hypothesis": original,
            "revision_reason": " ; ".join(refute_claims[:2]) if refute_claims else "支持证据占主导，微调表述",
            "revised_hypothesis": revised,
            "what_changed": what_changed,
            "remaining_risks": remaining_risks or ["需更多独立实验验证"],
        }
        result.data = revision
        return result
