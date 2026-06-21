"""多轮假设证据链迭代 Skill"""
from __future__ import annotations

from typing import Any, Dict

from app.skills.base import BaseSkill, SkillResult
from app.skills.evidence_reasoning.counter_evidence_retrieval_skill import CounterEvidenceRetrievalSkill
from app.skills.evidence_reasoning.evidence_chain_builder_skill import EvidenceChainBuilderSkill
from app.skills.evidence_reasoning.evidence_retrieval_skill import EvidenceRetrievalSkill
from app.skills.evidence_reasoning.evidence_stance_classification_skill import EvidenceStanceClassificationSkill
from app.skills.evidence_reasoning.hypothesis_revision_skill import HypothesisRevisionSkill
from app.skills.evidence_reasoning.scientific_claim_extraction_skill import ScientificClaimExtractionSkill
from app.skills.evidence_reasoning.citation_integrity_check_skill import CitationIntegrityCheckSkill


class IterativeHypothesisLoopSkill(BaseSkill):
    name = "IterativeHypothesisLoop"
    description = "多轮证据检索、立场判断与假设修正"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        max_rounds = int(input_data.get("max_rounds", 2))
        hypothesis = input_data.get("hypothesis", "")
        research_question = input_data.get("research_question", "")
        facts = input_data.get("facts", [])
        citation_map = input_data.get("citation_map", [])
        uncertain_points = input_data.get("uncertain_points", [])
        imported_papers = input_data.get("imported_papers", [])
        uploaded_pdfs = input_data.get("uploaded_pdfs", [])
        bibtex_docs = input_data.get("bibtex_docs", [])

        current_hypothesis = hypothesis
        revision_history = []
        supporting: list = []
        counter: list = []
        counter_empty_reason = ""

        claim_skill = ScientificClaimExtractionSkill()
        support_skill = EvidenceRetrievalSkill()
        counter_skill = CounterEvidenceRetrievalSkill()
        stance_skill = EvidenceStanceClassificationSkill()
        revision_skill = HypothesisRevisionSkill()
        builder_skill = EvidenceChainBuilderSkill()
        integrity_skill = CitationIntegrityCheckSkill()

        for round_idx in range(1, max_rounds + 1):
            await claim_skill.run(
                {"hypothesis": current_hypothesis, "rationale": input_data.get("rationale", ""), "facts": facts},
                context,
            )

            support_res = await support_skill.run(
                {
                    "hypothesis": current_hypothesis,
                    "research_question": research_question,
                    "facts": facts,
                    "citation_map": citation_map,
                    "imported_papers": imported_papers,
                    "uploaded_pdfs": uploaded_pdfs,
                    "bibtex_docs": bibtex_docs,
                },
                context,
            )
            supporting = support_res.data.get("supporting_evidence", [])

            counter_res = await counter_skill.run(
                {
                    "hypothesis": current_hypothesis,
                    "facts": facts,
                    "citation_map": citation_map,
                    "uncertain_points": uncertain_points,
                },
                context,
            )
            counter = counter_res.data.get("counter_evidence", [])
            counter_empty_reason = counter_res.data.get("empty_reason", "")

            all_evidence = supporting + counter
            stance_res = await stance_skill.run(
                {"hypothesis": current_hypothesis, "evidence_list": all_evidence},
                context,
            )
            classified = stance_res.data.get("classified_evidence", [])
            supporting = [e for e in classified if e.get("stance") == "support"]
            counter = [e for e in classified if e.get("stance") == "refute"]

            revision_res = await revision_skill.run(
                {
                    "hypothesis": current_hypothesis,
                    "supporting_evidence": supporting,
                    "counter_evidence": counter,
                },
                context,
            )
            revision = revision_res.data
            revision["round"] = round_idx
            revision_history.append(revision)
            current_hypothesis = revision.get("revised_hypothesis", current_hypothesis)

            if round_idx >= max_rounds or (supporting and not counter):
                break

        integrity_res = await integrity_skill.run(
            {
                "supporting_evidence": supporting,
                "counter_evidence": counter,
                "citation_map": citation_map,
                "facts": facts,
            },
            context,
        )
        if integrity_res.data:
            supporting = integrity_res.data.get("filtered_supporting", supporting)
            counter = integrity_res.data.get("filtered_counter", counter)

        builder_res = await builder_skill.run(
            {
                "hypothesis": hypothesis,
                "supporting_evidence": supporting,
                "counter_evidence": counter,
                "revision_history": revision_history,
                "final_version": current_hypothesis,
                "counter_empty_reason": counter_empty_reason,
            },
            context,
        )

        chain = builder_res.data.get("evidence_chain", {})
        chain["citation_integrity"] = integrity_res.data

        result.data = {
            "evidence_chain": chain,
            "final_hypothesis": current_hypothesis,
            "rounds_executed": len(revision_history),
        }
        result.warnings.extend(support_res.warnings)
        result.warnings.extend(integrity_res.warnings)
        return result
