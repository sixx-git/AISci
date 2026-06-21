"""知识图谱质量审查 Skill"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult


class KgQualityReviewSkill(BaseSkill):
    name = "KgQualityReview"
    description = "检查孤立节点、重复实体、低置信边等"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        graph = input_data.get("graph", {}) or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        candidate_edges = graph.get("candidate_edges", [])

        connected: Set[str] = set()
        for e in edges:
            connected.add(e.get("source"))
            connected.add(e.get("target"))

        isolated = [n for n in nodes if n.get("id") not in connected]

        label_counts = Counter(
            f"{n.get('type')}::{(n.get('label') or '').lower()}" for n in nodes
        )
        duplicates = [k for k, v in label_counts.items() if v > 1]

        low_conf = [e for e in edges if e.get("confidence", 1) < 0.5]
        missing_sources = [
            n for n in nodes if not n.get("source_ids")
        ] + [
            e for e in edges if not e.get("source_title") or not e.get("evidence")
        ]

        contradict_pairs: List[Dict] = []
        edge_map: Dict[str, List] = {}
        for e in edges:
            key = f"{e['source']}::{e['target']}"
            edge_map.setdefault(key, []).append(e)
        for key, elist in edge_map.items():
            rels = {e.get("relation") for e in elist}
            if "supports" in rels and "contradicts" in rels:
                contradict_pairs.append({"pair": key, "relations": list(rels)})

        quality_report = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "candidate_edge_count": len(candidate_edges),
            "isolated_nodes": [{"id": n["id"], "label": n.get("label"), "type": n.get("type")} for n in isolated[:20]],
            "isolated_count": len(isolated),
            "duplicate_entities": duplicates[:20],
            "duplicate_count": len(duplicates),
            "low_confidence_edges": low_conf[:20],
            "low_confidence_count": len(low_conf),
            "missing_sources_count": len(missing_sources),
            "contradictory_edges": contradict_pairs[:10],
            "overall_score": round(max(0.0, 1.0 - (
                len(isolated) * 0.02 + len(low_conf) * 0.03 + len(missing_sources) * 0.05
            ) / max(len(nodes), 1)), 4),
        }

        result.data = {"quality_report": quality_report}
        if isolated:
            result.add_warning(f"存在 {len(isolated)} 个孤立节点")
        if low_conf:
            result.add_warning(f"存在 {len(low_conf)} 条低置信边")
        return result
