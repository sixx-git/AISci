"""证据推理扩展 Skill"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult
from app.skills.evidence_reasoning.counter_evidence_retrieval_skill import CounterEvidenceRetrievalSkill
from app.skills.evidence_reasoning.hypothesis_revision_skill import HypothesisRevisionSkill
from app.skills.evidence_reasoning.scientific_claim_extraction_skill import ScientificClaimExtractionSkill
from app.skills.literature.search_papers_skill import SearchPapersSkill
from app.skills.literature.paper_full_text_rag_skill import PaperFullTextRAGSkill

logger = logging.getLogger(__name__)


class LiteratureEvidenceRetrievalSkill(BaseSkill):
    name = "LiteratureEvidenceRetrieval"
    description = "从 PDF/arXiv/OpenAlex/S2 检索证据片段"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        rq = input_data.get("research_question", "")
        project_id = input_data.get("project_id", "")

        search = SearchPapersSkill()
        search_res = await search.run(
            {"research_question": rq, "keywords": input_data.get("keywords", []), "max_results": 20},
            context,
        )
        papers = search_res.data.get("papers", []) if search_res.data else []

        rag_passages: List[dict] = []
        if project_id:
            rag = PaperFullTextRAGSkill()
            rag_res = await rag.run({"project_id": project_id, "research_question": rq}, context)
            rag_passages = (rag_res.data or {}).get("passages", [])

        result.data = {
            "papers": papers[:20],
            "paper_count": len(papers),
            "rag_passages": rag_passages,
            "sources": list({p.get("_source") for p in papers if p.get("_source")}),
        }
        result.warnings.extend(search_res.warnings)
        return result


class ClaimExtractionSkill(BaseSkill):
    name = "ClaimExtraction"
    description = "从论文中抽取 claim、method、result、limitation"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = ScientificClaimExtractionSkill()
        res = await inner.run(input_data, context)
        claims_raw = (res.data or {}).get("claims", [])
        structured = {"claims": [], "methods": [], "results": [], "limitations": []}
        for c in claims_raw:
            if not isinstance(c, dict):
                continue
            text = c.get("claim") or c.get("content") or str(c)
            cat = (c.get("category") or c.get("type") or "claim").lower()
            if "method" in cat:
                structured["methods"].append(text)
            elif "result" in cat or "finding" in cat:
                structured["results"].append(text)
            elif "limit" in cat:
                structured["limitations"].append(text)
            else:
                structured["claims"].append(text)
        res.data = {**(res.data or {}), "structured_claims": structured}
        return res


class CounterEvidenceSearchSkill(BaseSkill):
    name = "CounterEvidenceSearch"
    description = "主动寻找反例和相反结论"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = CounterEvidenceRetrievalSkill()
        return await inner.run(input_data, context)


class HypothesisRefinementSkill(BaseSkill):
    name = "HypothesisRefinement"
    description = "根据正反证据更新假设"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = HypothesisRevisionSkill()
        return await inner.run(input_data, context)


class MechanismReasoningSkill(BaseSkill):
    name = "MechanismReasoning"
    description = "把证据转成机制解释链"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = input_data.get("hypothesis", "")
        evidence = input_data.get("supporting_evidence") or input_data.get("evidence_list") or []
        ev_text = "\n".join(
            f"- {e.get('claim', e.get('content', ''))[:200]} (来源: {e.get('source_title', '?')})"
            for e in evidence[:8]
        )
        try:
            llm = qwen_structured_chat(
                prompt=(
                    f"假设: {hypothesis}\n\n证据:\n{ev_text or '—'}\n\n"
                    "请构建机制解释链：现象 → 中间机制 → 可检验预测。"
                ),
                schema_example={
                    "mechanism_chain": [
                        {"step": 1, "node": "现象", "explanation": "..."},
                        {"step": 2, "node": "机制", "explanation": "..."},
                    ],
                    "testable_predictions": ["预测1"],
                    "summary": "机制总结",
                },
                prompt_version="mechanism_reasoning",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result
