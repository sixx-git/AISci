"""LightRAG 风格增量图谱更新 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph.scientific_entity_extraction_skill import ScientificEntityExtractionSkill
from app.skills.knowledge_graph.scientific_relation_extraction_skill import ScientificRelationExtractionSkill
from app.skills.knowledge_graph._utils import merge_nodes, normalize_label


class IncrementalGraphUpdateSkill(BaseSkill):
    name = "IncrementalGraphUpdate"
    description = "增量合并新文献/事实，无需全量重建（LightRAG incremental update）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        graph = dict(input_data.get("graph", {}) or {})
        new_facts = input_data.get("new_facts", []) or []
        new_citation_map = input_data.get("new_citation_map", []) or []
        new_documents = input_data.get("new_documents", []) or []

        if not new_facts and not new_citation_map and not new_documents:
            result.data = {"graph": graph, "incremental": {"added_nodes": 0, "added_edges": 0}}
            return result

        entity_skill = ScientificEntityExtractionSkill()
        entity_res = await entity_skill.run(
            {
                "facts": new_facts,
                "citation_map": new_citation_map,
                "documents": new_documents,
            },
            context,
        )
        new_entities = entity_res.data.get("entities", [])

        index: Dict[str, Dict] = {}
        existing_nodes = list(graph.get("nodes", []))
        for n in existing_nodes:
            key = f"{n.get('type')}::{normalize_label(n.get('label', '')).lower()}"
            index[key] = n

        added_nodes = 0
        merged_nodes: List[Dict] = []
        id_map: Dict[str, str] = {}

        for ne in new_entities:
            old_id = ne["id"]
            before = len(index)
            merged = merge_nodes(index, ne)
            if len(index) > before:
                added_nodes += 1
            id_map[old_id] = merged["id"]
            if merged not in merged_nodes:
                merged_nodes.append(merged)

        graph["nodes"] = list(index.values())

        relation_skill = ScientificRelationExtractionSkill()
        rel_res = await relation_skill.run(
            {
                "entities": graph["nodes"],
                "facts": new_facts,
                "citation_map": new_citation_map,
            },
            context,
        )
        new_edges = rel_res.data.get("edges", [])
        existing_edge_keys = {
            f"{e['source']}::{e['target']}::{e['relation']}" for e in graph.get("edges", [])
        }
        added_edges = 0
        for e in new_edges:
            key = f"{e['source']}::{e['target']}::{e['relation']}"
            if key not in existing_edge_keys:
                graph.setdefault("edges", []).append(e)
                existing_edge_keys.add(key)
                added_edges += 1

        candidate = graph.get("candidate_edges", [])
        for ce in rel_res.data.get("candidate_edges", []):
            candidate.append(ce)
        graph["candidate_edges"] = candidate[-200:]

        graph.setdefault("incremental_log", []).append({
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "new_fact_count": len(new_facts),
        })
        graph["incremental_log"] = graph["incremental_log"][-50:]

        result.data = {
            "graph": graph,
            "incremental": {
                "added_nodes": added_nodes,
                "added_edges": added_edges,
                "new_fact_count": len(new_facts),
            },
        }
        return result
