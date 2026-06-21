"""反对证据检索 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.evidence_reasoning._utils import COUNTER_KEYWORDS, fact_to_evidence, normalize_text


class CounterEvidenceRetrievalSkill(BaseSkill):
    name = "CounterEvidenceRetrieval"
    description = "检索反例、限制条件与失败案例证据"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = input_data.get("hypothesis", "")
        facts = input_data.get("facts", [])
        citation_map = input_data.get("citation_map", [])
        uncertain_points = input_data.get("uncertain_points", [])

        counter: List[Dict[str, Any]] = []

        for fact in facts:
            text = normalize_text(
                f"{fact.get('content', '')} {fact.get('fact_text', '')} {fact.get('quote_text', '')}"
            )
            if not any(kw in text for kw in COUNTER_KEYWORDS):
                continue
            ev = fact_to_evidence(fact, "refute", hypothesis, citation_map)
            if ev:
                counter.append(ev)

        for point in uncertain_points[:3]:
            if isinstance(point, str) and point.strip():
                counter.append(
                    {
                        "evidence_id": f"uncertain_{len(counter)}",
                        "claim": point.strip()[:500],
                        "stance": "refute",
                        "source_title": "文献不确定点",
                        "source_type": "paper",
                        "year": None,
                        "doi": "",
                        "arxiv_id": "",
                        "paper_id": "",
                        "quote_or_summary": point.strip()[:500],
                        "relevance_score": 0.5,
                        "reliability_score": 0.6,
                        "used_in_revision": False,
                    }
                )

        counter = counter[:3]
        empty_reason = ""
        if not counter:
            empty_reason = "当前文献库中未检索到可验证的反例或限制条件证据，文献不足，未编造反对证据"

        result.data = {
            "counter_evidence": counter,
            "count": len(counter),
            "empty": len(counter) == 0,
            "empty_reason": empty_reason,
        }
        return result
