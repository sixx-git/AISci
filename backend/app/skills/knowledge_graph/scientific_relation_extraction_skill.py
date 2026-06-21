"""科学关系抽取 Skill"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph._utils import new_edge_id, normalize_label


class ScientificRelationExtractionSkill(BaseSkill):
    name = "ScientificRelationExtraction"
    description = "按 schema 抽取有证据来源的关系"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        entities: List[Dict] = input_data.get("entities", []) or []
        facts = input_data.get("facts", []) or []
        citation_map = input_data.get("citation_map", []) or []
        knowledge_gap = input_data.get("knowledge_gap", {}) or {}

        by_type: Dict[str, List[Dict]] = {}
        by_label: Dict[str, Dict] = {}
        for e in entities:
            by_type.setdefault(e.get("type", ""), []).append(e)
            by_label[f"{e.get('type')}::{normalize_label(e.get('label','')).lower()}"] = e

        edges: List[Dict] = []
        candidate_edges: List[Dict] = []

        def add_edge(source, target, relation, evidence, source_title, paper_id, page, confidence):
            if not source or not target or not evidence or not source_title:
                return
            edge = {
                "id": new_edge_id(),
                "source": source,
                "target": target,
                "relation": relation,
                "evidence": evidence[:500],
                "source_title": source_title,
                "paper_id": paper_id or "",
                "page": page,
                "confidence": round(confidence, 4),
                "human_verified": False,
            }
            if confidence >= 0.5:
                edges.append(edge)
            else:
                candidate_edges.append(edge)

        for fact in facts:
            content = fact.get("content") or fact.get("fact_text") or ""
            source_title = fact.get("source_paper_title") or fact.get("title") or ""
            paper_id = fact.get("document_id") or fact.get("paper_id") or ""
            page = fact.get("page_number")
            fact_id = fact.get("fact_id") or ""
            if not source_title or not fact_id:
                continue

            ev_node = self._find_entity(by_type, "Evidence", content[:80])
            paper_node = self._find_entity(by_type, "Paper", source_title)

            for method in by_type.get("Method", []):
                if method.get("label", "").lower() in content.lower():
                    for ds in by_type.get("Dataset", []):
                        if ds.get("label", "").lower() in content.lower():
                            add_edge(
                                method["id"], ds["id"], "evaluates_on", content,
                                source_title, paper_id, page, 0.72,
                            )
                    add_edge(
                        method["id"], paper_node["id"] if paper_node else method["id"],
                        "cites", content, source_title, paper_id, page, 0.68,
                    ) if paper_node else None

            if re.search(r"\b(use[sd]?|employ|based on)\b", content, re.I):
                for method in by_type.get("Method", []):
                    if method.get("label", "").lower() in content.lower():
                        for ds in by_type.get("Dataset", []):
                            if ds.get("label", "").lower() in content.lower():
                                add_edge(method["id"], ds["id"], "uses", content, source_title, paper_id, page, 0.7)

            if any(k in content.lower() for k in ("support", "confirm", "improve", "outperform")):
                for hypo in by_type.get("Hypothesis", []):
                    if any(w in content.lower() for w in hypo.get("label", "").lower().split()[:3] if len(w) > 3):
                        tgt = ev_node["id"] if ev_node else (by_type.get("Evidence", [{}])[0].get("id") if by_type.get("Evidence") else "")
                        if tgt:
                            add_edge(hypo["id"], tgt, "supports", content, source_title, paper_id, page, 0.65)

            if any(k in content.lower() for k in ("contradict", "fail", "worse", "does not")):
                for hypo in by_type.get("Hypothesis", []):
                    tgt = ev_node["id"] if ev_node else ""
                    if tgt:
                        add_edge(hypo["id"], tgt, "contradicts", content, source_title, paper_id, page, 0.62)

            for metric in by_type.get("Metric", []):
                if metric.get("label", "").lower() in content.lower():
                    for method in by_type.get("Method", []):
                        if method.get("label", "").lower() in content.lower():
                            add_edge(method["id"], metric["id"], "measured_by", content, source_title, paper_id, page, 0.71)

        for conn in knowledge_gap.get("possible_connections", []) or []:
            desc = conn.get("description", "")
            conf = float(conn.get("confidence", 0.5))
            fids = conn.get("fact_ids", [])
            if len(fids) >= 2 and desc:
                add_edge(fids[0], fids[1], "improves", desc, "knowledge_gap_analysis", "", None, conf)

        for contra in knowledge_gap.get("contradictions", []) or []:
            desc = contra.get("description", "")
            fids = contra.get("fact_ids", [])
            if len(fids) >= 2 and desc:
                add_edge(fids[0], fids[1], "contradicts", desc, "knowledge_gap_analysis", "", None, 0.55)

        result.data = {"edges": edges, "candidate_edges": candidate_edges, "edge_count": len(edges)}
        return result

    @staticmethod
    def _find_entity(by_type: Dict, etype: str, hint: str) -> Optional[Dict]:
        hint_l = (hint or "").lower()[:60]
        for e in by_type.get(etype, []):
            if hint_l in (e.get("label") or "").lower() or (e.get("label") or "").lower() in hint_l:
                return e
        return by_type.get(etype, [None])[0] if by_type.get(etype) else None
