"""科学实体抽取 Skill"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph._utils import (
    DATASET_PATTERNS,
    METRIC_PATTERNS,
    METHOD_PATTERNS,
    extract_by_patterns,
    merge_nodes,
    new_node_id,
    normalize_label,
)


class ScientificEntityExtractionSkill(BaseSkill):
    name = "ScientificEntityExtraction"
    description = "从文献/假设/报告中抽取有来源的科研实体"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        facts = input_data.get("facts", []) or []
        citation_map = input_data.get("citation_map", []) or []
        documents = input_data.get("documents", []) or []
        hypotheses = input_data.get("hypotheses", []) or []
        report_sections = input_data.get("report_sections", {}) or {}

        index: Dict[str, Dict] = {}
        nodes: List[Dict[str, Any]] = []

        for cit in citation_map:
            doc_id = cit.get("document_id") or cit.get("paper_id") or ""
            title = cit.get("paper_title") or cit.get("title") or ""
            if not doc_id and not title:
                continue
            source_id = doc_id or f"paper:{title[:40]}"
            node = {
                "id": new_node_id("paper"),
                "type": "Paper",
                "label": title or doc_id,
                "description": cit.get("abstract", "")[:300],
                "source_ids": [source_id],
                "confidence": 0.9,
                "metadata": {"year": cit.get("year"), "doi": cit.get("doi", "")},
            }
            nodes.append(merge_nodes(index, node))

        for fact in facts:
            content = fact.get("content") or fact.get("fact_text") or ""
            if not content.strip():
                continue
            source_id = fact.get("fact_id") or fact.get("document_id") or ""
            if not source_id:
                result.add_warning(f"跳过无 source 的事实: {content[:40]}")
                continue
            doc_title = fact.get("source_paper_title") or fact.get("title") or ""

            for method in extract_by_patterns(content, METHOD_PATTERNS):
                nodes.append(merge_nodes(index, {
                    "id": new_node_id("method"),
                    "type": "Method",
                    "label": method,
                    "description": content[:200],
                    "source_ids": [source_id],
                    "confidence": 0.75,
                    "metadata": {"source_title": doc_title},
                }))

            for ds in extract_by_patterns(content, DATASET_PATTERNS):
                nodes.append(merge_nodes(index, {
                    "id": new_node_id("dataset"),
                    "type": "Dataset",
                    "label": ds,
                    "description": content[:200],
                    "source_ids": [source_id],
                    "confidence": 0.7,
                    "metadata": {"source_title": doc_title},
                }))

            for metric in extract_by_patterns(content, METRIC_PATTERNS):
                nodes.append(merge_nodes(index, {
                    "id": new_node_id("metric"),
                    "type": "Metric",
                    "label": normalize_label(metric),
                    "description": content[:200],
                    "source_ids": [source_id],
                    "confidence": 0.65,
                    "metadata": {"source_title": doc_title},
                }))

            if any(k in content.lower() for k in ("limitation", "failure", "drawback", "不足", "限制")):
                nodes.append(merge_nodes(index, {
                    "id": new_node_id("lim"),
                    "type": "Limitation",
                    "label": content[:80],
                    "description": content[:300],
                    "source_ids": [source_id],
                    "confidence": 0.6,
                    "metadata": {"source_title": doc_title},
                }))

            nodes.append(merge_nodes(index, {
                "id": new_node_id("ev"),
                "type": "Evidence",
                "label": content[:80],
                "description": content[:400],
                "source_ids": [source_id],
                "confidence": 0.8,
                "metadata": {"page": fact.get("page_number"), "source_title": doc_title},
            }))

        for hypo in hypotheses:
            text = hypo.get("hypothesis") or hypo.get("content") or ""
            hid = hypo.get("id") or hypo.get("hypothesis_id") or new_node_id("hypo")
            if not text:
                continue
            nodes.append(merge_nodes(index, {
                "id": new_node_id("hypothesis"),
                "type": "Hypothesis",
                "label": text[:100],
                "description": text[:500],
                "source_ids": [f"hypothesis:{hid}"],
                "confidence": 0.85,
                "metadata": {"hypothesis_id": hid},
            }))

        for doc in documents:
            title = doc.get("title") or doc.get("filename") or ""
            doc_id = doc.get("id") or ""
            if doc_id and title:
                nodes.append(merge_nodes(index, {
                    "id": new_node_id("paper"),
                    "type": "Paper",
                    "label": title,
                    "description": (doc.get("abstract") or "")[:300],
                    "source_ids": [doc_id],
                    "confidence": 0.88,
                    "metadata": {},
                }))

        rq = report_sections.get("research_question") or input_data.get("research_question", "")
        if rq:
            nodes.append(merge_nodes(index, {
                "id": new_node_id("problem"),
                "type": "Problem",
                "label": rq[:100],
                "description": rq[:500],
                "source_ids": ["project:research_question"],
                "confidence": 0.95,
                "metadata": {},
            }))

        dedup = list({n["id"]: n for n in nodes if n.get("source_ids")}.values())
        result.data = {"entities": dedup, "count": len(dedup)}
        return result
