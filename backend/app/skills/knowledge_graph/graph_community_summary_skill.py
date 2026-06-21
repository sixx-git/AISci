"""GraphRAG 风格社区发现与主题摘要 Skill"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult


class GraphCommunitySummarySkill(BaseSkill):
    name = "GraphCommunitySummary"
    description = "对知识图谱做社区划分并生成面向全局检索的主题摘要"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        graph = input_data.get("graph", {}) or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        research_question = input_data.get("research_question", "")

        parent: Dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        node_map = {n["id"]: n for n in nodes}
        for n in nodes:
            find(n["id"])
        for e in edges:
            if e.get("source") in node_map and e.get("target") in node_map:
                union(e["source"], e["target"])

        communities: Dict[str, List[str]] = defaultdict(list)
        for nid in node_map:
            communities[find(nid)].append(nid)

        summaries: List[Dict[str, Any]] = []
        for idx, (root, member_ids) in enumerate(communities.items()):
            member_nodes = [node_map[mid] for mid in member_ids]
            type_counts: Dict[str, int] = defaultdict(int)
            labels: List[str] = []
            source_titles: Set[str] = set()
            for mn in member_nodes:
                type_counts[mn.get("type", "Unknown")] += 1
                if mn.get("label"):
                    labels.append(mn["label"])
                for sid in mn.get("source_ids", []):
                    if sid.startswith("paper:") or sid.startswith("doc"):
                        source_titles.add(sid)

            rel_in_comm = [
                e for e in edges
                if e.get("source") in member_ids and e.get("target") in member_ids
            ]
            rel_summary = defaultdict(int)
            for e in rel_in_comm:
                rel_summary[e.get("relation", "related")] += 1

            dominant_type = max(type_counts, key=type_counts.get) if type_counts else "Mixed"
            top_labels = labels[:6]
            summary_text = self._compose_summary(
                dominant_type, top_labels, rel_summary, research_question
            )

            summaries.append({
                "community_id": f"comm_{idx}",
                "root": root,
                "node_count": len(member_ids),
                "node_ids": member_ids,
                "dominant_type": dominant_type,
                "type_distribution": dict(type_counts),
                "top_entities": top_labels,
                "relation_summary": dict(rel_summary),
                "source_count": len(source_titles),
                "summary": summary_text,
                "keywords": self._extract_keywords(top_labels, rel_summary),
            })

        summaries.sort(key=lambda x: x["node_count"], reverse=True)
        result.data = {
            "communities": summaries,
            "community_count": len(summaries),
        }
        return result

    @staticmethod
    def _compose_summary(
        dominant_type: str,
        labels: List[str],
        rel_summary: Dict[str, int],
        research_question: str,
    ) -> str:
        entity_part = "、".join(labels[:4]) if labels else "若干相关实体"
        rel_part = "；".join(f"{k}×{v}" for k, v in list(rel_summary.items())[:3])
        rq_hint = f"（与研究问题「{research_question[:40]}…」相关）" if research_question else ""
        return (
            f"本社区以 {dominant_type} 为主，核心实体包括 {entity_part}。"
            f"{' 关系分布：' + rel_part + '。' if rel_part else ''}"
            f"{rq_hint}"
        ).strip()

    @staticmethod
    def _extract_keywords(labels: List[str], rel_summary: Dict[str, int]) -> List[str]:
        kws = list(labels[:5])
        kws.extend(list(rel_summary.keys())[:3])
        return list(dict.fromkeys(kws))
