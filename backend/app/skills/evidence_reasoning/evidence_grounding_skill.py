"""证据接地 Skill — 将主张/证据绑定到可验证来源"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.evidence_reasoning._utils import PLACEHOLDER_TITLES, normalize_text

logger = logging.getLogger(__name__)


class EvidenceGroundingSkill(BaseSkill):
    """证据接地 Skill

    输入:
      - hypothesis: str
      - claims: List[str]               待接地主张（可选）
      - evidence_list: List[dict]       支持/反驳证据
      - rag_passages: List[dict]        PaperFullTextRAG 输出片段（可选）
      - facts: List[dict]               文献事实白名单

    输出 (SkillResult.data):
      - grounded_evidence: List[dict]   带来源绑定的证据
      - ungrounded_evidence: List[dict] 无法验证来源的证据
      - grounding_score: float          0-1 接地完整度
      - passed: bool
    """

    name = "EvidenceGrounding"
    description = "将假设与证据主张绑定到 chunk/文献来源，拒绝无出处证据"
    source_reference = "PaperQA — evidence grounding; AI Scientist — claim verification"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = (input_data.get("hypothesis") or "").strip()
        evidence_list: List[dict] = list(input_data.get("evidence_list") or [])
        supporting = list(input_data.get("supporting_evidence") or [])
        counter = list(input_data.get("counter_evidence") or [])
        if not evidence_list:
            evidence_list = supporting + counter

        rag_passages = list(input_data.get("rag_passages") or [])
        facts = list(input_data.get("facts") or [])
        fact_titles = {
            normalize_text(f.get("source_paper_title") or f.get("source_title") or "")
            for f in facts
        }
        rag_chunk_ids = {p.get("chunk_id") for p in rag_passages if p.get("chunk_id")}

        grounded: List[dict] = []
        ungrounded: List[dict] = []

        for ev in evidence_list:
            if not isinstance(ev, dict):
                continue
            enriched = dict(ev)
            score, reason = self._grounding_score(enriched, fact_titles, rag_chunk_ids)
            enriched["grounding_score"] = score
            enriched["grounding_reason"] = reason
            if score >= 0.5:
                grounded.append(enriched)
            else:
                ungrounded.append(enriched)

        total = len(evidence_list) or 1
        grounding_score = round(len(grounded) / total, 4)
        passed = len(ungrounded) == 0 and len(grounded) >= min(3, total)

        if ungrounded:
            result.add_warning(f"检测到 {len(ungrounded)} 条无法接地的证据")
        if hypothesis and len(grounded) < 3:
            result.add_warning("接地证据不足 3 条，建议补充 PDF/文献导入")

        result.data = {
            "hypothesis": hypothesis,
            "grounded_evidence": grounded,
            "ungrounded_evidence": ungrounded,
            "grounding_score": grounding_score,
            "passed": passed,
            "grounded_count": len(grounded),
            "ungrounded_count": len(ungrounded),
        }
        return result

    @staticmethod
    def _grounding_score(
        ev: dict,
        fact_titles: set[str],
        rag_chunk_ids: set[str],
    ) -> tuple[float, str]:
        chunk_id = ev.get("source_chunk_id") or ev.get("chunk_id")
        doc_id = ev.get("document_id") or ev.get("paper_id")
        title = normalize_text(ev.get("source_title") or ev.get("source_paper_title") or "")

        if chunk_id and (chunk_id in rag_chunk_ids or doc_id):
            return 0.95, "chunk_bound"
        if doc_id and ev.get("quote_or_summary"):
            return 0.85, "document_quote"
        if title and title not in PLACEHOLDER_TITLES:
            if title in fact_titles or any(title in t or t in title for t in fact_titles if t):
                return 0.8, "fact_whitelist"
            if len(title) >= 12 and ev.get("doi") or ev.get("arxiv_id"):
                return 0.75, "external_id"
            if len(title) >= 12:
                return 0.6, "title_only"
        if ev.get("claim") and ev.get("reliability_score", 0) >= 0.7:
            return 0.45, "weak_claim"
        return 0.2, "ungrounded"
