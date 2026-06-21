"""支持证据检索 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.evidence_reasoning._utils import fact_to_evidence, score_relevance


class EvidenceRetrievalSkill(BaseSkill):
    name = "EvidenceRetrieval"
    description = "检索支持假设的真实文献/数据证据，禁止编造来源"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = input_data.get("hypothesis", "")
        research_question = input_data.get("research_question", "")
        facts = input_data.get("facts", [])
        citation_map = input_data.get("citation_map", [])
        imported_papers = input_data.get("imported_papers", [])
        uploaded_pdfs = input_data.get("uploaded_pdfs", [])
        bibtex_docs = input_data.get("bibtex_docs", [])

        query = f"{hypothesis} {research_question}".strip()
        scored: List[Dict[str, Any]] = []

        for fact in facts:
            ev = fact_to_evidence(fact, "support", hypothesis, citation_map)
            if not ev:
                continue
            ev["relevance_score"] = max(
                ev.get("relevance_score", 0),
                score_relevance(query, ev.get("claim", "")),
            )
            scored.append(ev)

        scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        supporting = scored[: max(3, min(8, len(scored)))]

        if len(supporting) < 3:
            result.add_warning(
                f"支持证据仅 {len(supporting)} 条，低于要求的 3 条；未编造文献，需补充导入 BibTeX/PDF"
            )

        for paper in imported_papers + uploaded_pdfs + bibtex_docs:
            title = paper.get("title") or paper.get("paper_title") or paper.get("filename") or ""
            if not title or len(title) < 8:
                continue
            if any(title.lower() in (s.get("source_title") or "").lower() for s in supporting):
                continue
            if score_relevance(query, title) < 0.15:
                continue
            supporting.append(
                {
                    "evidence_id": paper.get("document_id") or paper.get("paper_id") or f"paper_{len(supporting)}",
                    "claim": f"已导入文献《{title}》与研究问题相关",
                    "stance": "support",
                    "source_title": title,
                    "source_type": paper.get("source_type") or "paper",
                    "year": paper.get("year"),
                    "doi": paper.get("doi", ""),
                    "arxiv_id": paper.get("arxiv_id") or paper.get("external_id", ""),
                    "paper_id": paper.get("paper_id") or paper.get("document_id", ""),
                    "quote_or_summary": paper.get("abstract", "")[:300],
                    "relevance_score": score_relevance(query, title),
                    "reliability_score": 0.75,
                    "used_in_revision": False,
                }
            )
            if len(supporting) >= 3:
                break

        result.data = {
            "supporting_evidence": supporting[:8],
            "count": len(supporting[:8]),
            "minimum_met": len(supporting) >= 3,
        }
        return result
