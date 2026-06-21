"""图谱 RAG 检索 Skill — LightRAG Local/Global/Hybrid + GraphRAG 社区摘要"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph.domain_profiles import normalize_retrieval_mode


class GraphRagRetrievalSkill(BaseSkill):
    name = "GraphRagRetrieval"
    description = "双级图谱检索：local 实体邻域 / global 社区主题 / hybrid 融合"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        graph = input_data.get("graph", {}) or {}
        query = (input_data.get("query") or "").lower()
        node_type = input_data.get("node_type")
        max_depth = int(input_data.get("max_depth", 2))
        retrieval_mode = normalize_retrieval_mode(input_data.get("retrieval_mode"))
        communities = graph.get("communities", []) or input_data.get("communities", []) or []

        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        edges = graph.get("edges", [])

        local_sub = self._local_retrieval(nodes, edges, query, node_type, max_depth)
        global_hits = self._global_retrieval(communities, query) if retrieval_mode in ("global", "hybrid") else []

        if retrieval_mode == "local":
            subgraph = local_sub
            mode_used = "local"
        elif retrieval_mode == "global":
            subgraph = self._community_subgraph(nodes, edges, global_hits)
            mode_used = "global"
        else:
            subgraph = self._merge_subgraphs(local_sub, self._community_subgraph(nodes, edges, global_hits))
            mode_used = "hybrid"

        result.data = {
            "subgraph": subgraph,
            "retrieval_mode": mode_used,
            "local_hit": {
                "seed_count": local_sub.get("seed_count", 0),
                "node_count": len(local_sub.get("nodes", [])),
            },
            "global_hit": {
                "community_count": len(global_hits),
                "communities": global_hits[:5],
            },
        }
        return result

    def _local_retrieval(
        self,
        nodes: Dict[str, Dict],
        edges: List[Dict],
        query: str,
        node_type: str | None,
        max_depth: int,
    ) -> Dict[str, Any]:
        seed_ids: Set[str] = set()
        tokens = [t for t in query.split() if len(t) > 2]

        for nid, node in nodes.items():
            if node_type and node.get("type") != node_type:
                continue
            label = (node.get("label") or "").lower()
            desc = (node.get("description") or "").lower()
            if not query:
                if node_type:
                    seed_ids.add(nid)
            elif any(tok in label or tok in desc for tok in tokens):
                seed_ids.add(nid)

        if query and not seed_ids:
            for nid, node in nodes.items():
                if any(tok in (node.get("label") or "").lower() for tok in tokens):
                    seed_ids.add(nid)

        visited = set(seed_ids)
        frontier = list(seed_ids)
        sub_edges: List[Dict] = []

        for _ in range(max_depth):
            next_frontier = []
            for e in edges:
                if e["source"] in frontier or e["target"] in frontier:
                    sub_edges.append(e)
                    for nid in (e["source"], e["target"]):
                        if nid not in visited:
                            visited.add(nid)
                            next_frontier.append(nid)
            frontier = next_frontier
            if not frontier:
                break

        sub_nodes = [nodes[nid] for nid in visited if nid in nodes]
        return {"nodes": sub_nodes, "edges": sub_edges, "seed_count": len(seed_ids)}

    @staticmethod
    def _global_retrieval(communities: List[Dict], query: str) -> List[Dict]:
        if not communities:
            return []
        tokens = [t for t in query.split() if len(t) > 2]
        scored: List[tuple] = []
        for comm in communities:
            text = (
                f"{comm.get('summary', '')} "
                f"{' '.join(comm.get('top_entities', []))} "
                f"{' '.join(comm.get('keywords', []))}"
            ).lower()
            score = sum(1 for t in tokens if t in text) if tokens else comm.get("node_count", 0)
            if score > 0 or not tokens:
                scored.append((score, comm))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:3]]

    @staticmethod
    def _community_subgraph(
        nodes: Dict[str, Dict],
        edges: List[Dict],
        communities: List[Dict],
    ) -> Dict[str, Any]:
        member_ids: Set[str] = set()
        for comm in communities:
            member_ids.update(comm.get("node_ids", []))
        sub_nodes = [nodes[nid] for nid in member_ids if nid in nodes]
        sub_edges = [
            e for e in edges
            if e.get("source") in member_ids and e.get("target") in member_ids
        ]
        return {"nodes": sub_nodes, "edges": sub_edges}

    @staticmethod
    def _merge_subgraphs(a: Dict, b: Dict) -> Dict[str, Any]:
        node_map = {n["id"]: n for n in a.get("nodes", []) + b.get("nodes", [])}
        edge_map = {e["id"]: e for e in a.get("edges", []) + b.get("edges", []) if e.get("id")}
        for e in a.get("edges", []) + b.get("edges", []):
            if not e.get("id"):
                edge_map[f"{e.get('source')}::{e.get('target')}"] = e
        return {"nodes": list(node_map.values()), "edges": list(edge_map.values())}
