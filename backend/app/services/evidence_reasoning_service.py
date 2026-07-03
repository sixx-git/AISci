"""科学机制推理与证据链迭代验证服务"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.skills.evidence_reasoning.iterative_hypothesis_loop_skill import IterativeHypothesisLoopSkill

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class EvidenceReasoningService:
    def __init__(self):
        self.storage_root = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "evidence_chains",
        )

    def _chain_path(self, project_id: str, hypothesis_id: str) -> str:
        directory = os.path.join(self.storage_root, project_id)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, f"{hypothesis_id}.json")

    def save_evidence_chain(self, project_id: str, hypothesis_id: str, chain: Dict[str, Any]) -> str:
        path = self._chain_path(project_id, hypothesis_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chain, f, ensure_ascii=False, indent=2, default=str)
        return path

    def load_evidence_chain(self, project_id: str, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        path = self._chain_path(project_id, hypothesis_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def run_for_hypothesis(
        self,
        hypothesis: Dict[str, Any],
        research_question: str,
        literature_mining: Dict[str, Any],
        max_rounds: int = 2,
        multimodal_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        facts = literature_mining.get("facts", []) or []
        citation_map = literature_mining.get("citation_map", []) or []
        uncertain_points = literature_mining.get("uncertain_points", []) or []
        imported_raw = literature_mining.get("imported_documents", [])
        if isinstance(imported_raw, list):
            imported = imported_raw
        else:
            imported = [
                c for c in (literature_mining.get("citation_map") or [])
                if isinstance(c, dict)
            ]
        retrieved = literature_mining.get("retrieved_papers", []) or []
        mm_facts = list(multimodal_facts or literature_mining.get("multimodal_evidence") or [])

        loop_skill = IterativeHypothesisLoopSkill()
        loop_result = await loop_skill.run(
            {
                "hypothesis": hypothesis.get("hypothesis", ""),
                "rationale": hypothesis.get("rationale", ""),
                "research_question": research_question,
                "facts": facts,
                "citation_map": citation_map,
                "uncertain_points": uncertain_points,
                "imported_papers": imported,
                "uploaded_pdfs": [d for d in imported if d.get("source_type") == "uploaded_pdf"],
                "bibtex_docs": [d for d in imported if d.get("source_type") == "bibtex"],
                "multimodal_facts": mm_facts,
                "max_rounds": max_rounds,
            },
            {"stage": "evidence_reasoning"},
        )

        chain = loop_result.data.get("evidence_chain", {})
        final_hypothesis = loop_result.data.get("final_hypothesis") or hypothesis.get("hypothesis", "")

        enriched = dict(hypothesis)
        enriched["evidence_chain"] = chain
        enriched["final_version"] = chain.get("final_version") or final_hypothesis
        enriched["supporting_evidence"] = chain.get("supporting_evidence", [])
        enriched["counter_evidence"] = chain.get("counter_evidence", [])
        enriched["evidence_balance_score"] = chain.get("evidence_balance_score", 0.0)
        enriched["revision_history"] = chain.get("revision_history", [])

        supporting_fact_ids = {
            str(fid)
            for fid in (hypothesis.get("supporting_fact_ids") or [])
            if fid
        }
        for ev in chain.get("supporting_evidence", []):
            eid = ev.get("evidence_id") or ev.get("fact_id")
            if eid:
                supporting_fact_ids.add(str(eid))
        for rev in chain.get("revision_history", []):
            for fid in rev.get("cited_fact_ids", []) or []:
                if fid:
                    supporting_fact_ids.add(str(fid))
        if supporting_fact_ids:
            enriched["supporting_fact_ids"] = list(supporting_fact_ids)

        if final_hypothesis and final_hypothesis != hypothesis.get("hypothesis"):
            enriched["hypothesis"] = final_hypothesis

        if chain.get("support_count", 0) >= 3:
            enriched["evidence_level"] = "high"
        elif chain.get("support_count", 0) >= 1 or supporting_fact_ids:
            enriched["evidence_level"] = "medium"
        else:
            enriched["evidence_level"] = "low"

        return {
            "hypothesis": enriched,
            "evidence_chain": chain,
            "warnings": loop_result.warnings,
            "success": loop_result.success,
        }

    async def run_for_hypotheses(
        self,
        hypotheses: List[Dict[str, Any]],
        research_question: str,
        literature_mining: Dict[str, Any],
        max_rounds: int = 2,
        multimodal_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        enriched_list = []
        all_warnings = []
        chains = []

        for hypo in hypotheses:
            if hypo.get("off_topic"):
                enriched_list.append(hypo)
                continue
            item = await self.run_for_hypothesis(
                hypo, research_question, literature_mining, max_rounds,
                multimodal_facts=multimodal_facts,
            )
            enriched_list.append(item["hypothesis"])
            chains.append(item["evidence_chain"])
            all_warnings.extend(item.get("warnings", []))

        return {
            "hypotheses": enriched_list,
            "evidence_chains": chains,
            "warnings": all_warnings,
            "multimodal_facts_used": len(multimodal_facts or []),
            "processed_at": datetime.now(CHINA_TZ).isoformat(),
        }

    def run_for_hypotheses_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_for_hypotheses(**kwargs))


_evidence_reasoning_service: Optional[EvidenceReasoningService] = None


def get_evidence_reasoning_service() -> EvidenceReasoningService:
    global _evidence_reasoning_service
    if _evidence_reasoning_service is None:
        _evidence_reasoning_service = EvidenceReasoningService()
    return _evidence_reasoning_service
