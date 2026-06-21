"""项目级科研知识图谱服务"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.project_modes import normalize_project_mode
from app.models.project import Document
from app.models.research import Hypothesis
from app.services.project_service import ProjectService
from app.skills.knowledge_graph.domain_profiles import (
    get_scenario_catalog,
    resolve_domain_scenario,
)
from app.skills.knowledge_graph.evidence_graph_builder_skill import EvidenceGraphBuilderSkill
from app.skills.knowledge_graph.graph_community_summary_skill import GraphCommunitySummarySkill
from app.skills.knowledge_graph.graph_reasoning_skill import GraphReasoningSkill
from app.skills.knowledge_graph.human_feedback_update_skill import HumanFeedbackUpdateSkill
from app.skills.knowledge_graph.incremental_graph_update_skill import IncrementalGraphUpdateSkill
from app.skills.knowledge_graph.kg_quality_review_skill import KgQualityReviewSkill
from app.skills.knowledge_graph.kg_schema_generation_skill import KgSchemaGenerationSkill
from app.skills.knowledge_graph.scientific_entity_extraction_skill import ScientificEntityExtractionSkill
from app.skills.knowledge_graph.scientific_relation_extraction_skill import ScientificRelationExtractionSkill

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class KnowledgeGraphService:
    def __init__(self, db: Session):
        self.db = db
        self.storage_root = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "knowledge_graph",
        )

    def _project_dir(self, project_id: str) -> str:
        path = os.path.join(self.storage_root, project_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _graph_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "graph.json")

    def load_graph(self, project_id: str) -> Optional[Dict[str, Any]]:
        path = self._graph_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_graph(self, project_id: str, graph: Dict[str, Any]) -> str:
        graph["updated_at"] = datetime.now(CHINA_TZ).isoformat()
        path = self._graph_path(project_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2, default=str)
        return path

    def _load_documents(self, project_id: str) -> List[Dict[str, Any]]:
        docs = self.db.query(Document).filter(Document.project_id == project_id).all()
        return [
            {
                "id": d.id,
                "title": d.title or d.filename,
                "filename": d.filename,
                "abstract": d.abstract or "",
                "raw_text": (d.raw_text or "")[:8000],
            }
            for d in docs
        ]

    def _load_hypotheses(self, project_id: str) -> List[Dict[str, Any]]:
        hypos = self.db.query(Hypothesis).filter(Hypothesis.project_id == project_id).all()
        out = []
        for h in hypos:
            out.append({
                "id": h.id,
                "hypothesis_id": h.id,
                "hypothesis": h.hypothesis or "",
                "evidence_chain": {},
            })
        return out

    def _resolve_project_mode(self, project_id: str, override: Optional[str] = None) -> str:
        if override:
            return normalize_project_mode(override)
        project = ProjectService(self.db).get_project(project_id)
        if project:
            return normalize_project_mode(getattr(project, "project_mode", None) or "general")
        return "general"

    async def build_graph(
        self,
        project_id: str,
        literature_mining: Optional[Dict[str, Any]] = None,
        knowledge_gap: Optional[Dict[str, Any]] = None,
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        report_sections: Optional[Dict[str, Any]] = None,
        project_mode: Optional[str] = None,
        research_question: str = "",
    ) -> Dict[str, Any]:
        mode = self._resolve_project_mode(project_id, project_mode)
        ctx = {"project_id": project_id, "stage": "knowledge_graph"}

        lm = literature_mining or {}
        facts = lm.get("facts", []) or []
        citation_map = lm.get("citation_map", []) or []
        kg_gap = knowledge_gap or {}
        hypos = hypotheses or self._load_hypotheses(project_id)
        documents = self._load_documents(project_id)
        sections = report_sections or {}
        if research_question and not sections.get("research_question"):
            sections["research_question"] = research_question

        schema_skill = KgSchemaGenerationSkill()
        schema_res = await schema_skill.run({"project_mode": mode}, ctx)
        schema = schema_res.data.get("schema", {})

        entity_skill = ScientificEntityExtractionSkill()
        entity_res = await entity_skill.run(
            {
                "facts": facts,
                "citation_map": citation_map,
                "documents": documents,
                "hypotheses": hypos,
                "report_sections": sections,
                "research_question": research_question,
            },
            ctx,
        )
        entities = entity_res.data.get("entities", [])

        relation_skill = ScientificRelationExtractionSkill()
        relation_res = await relation_skill.run(
            {
                "entities": entities,
                "facts": facts,
                "citation_map": citation_map,
                "knowledge_gap": kg_gap,
            },
            ctx,
        )
        edges = relation_res.data.get("edges", [])
        candidate_edges = relation_res.data.get("candidate_edges", [])

        ev_skill = EvidenceGraphBuilderSkill()
        ev_res = await ev_skill.run(
            {"hypotheses": hypos, "evidence_chains": lm.get("evidence_chains", [])},
            ctx,
        )
        ev_graph = ev_res.data.get("evidence_graph", {})
        ev_nodes = ev_graph.get("nodes", [])
        ev_edges = ev_graph.get("edges", [])

        all_nodes = {n["id"]: n for n in entities}
        for n in ev_nodes:
            all_nodes[n["id"]] = n
        all_edges = edges + ev_edges

        graph = {
            "project_id": project_id,
            "project_mode": mode,
            "domain_scenario": resolve_domain_scenario(mode),
            "schema": schema,
            "nodes": list(all_nodes.values()),
            "edges": all_edges,
            "candidate_edges": candidate_edges,
            "evidence_graph": ev_graph,
            "quality_report": {},
            "communities": [],
        }

        comm_skill = GraphCommunitySummarySkill()
        comm_res = await comm_skill.run(
            {"graph": graph, "research_question": research_question},
            ctx,
        )
        graph["communities"] = comm_res.data.get("communities", [])

        quality_skill = KgQualityReviewSkill()
        q_res = await quality_skill.run({"graph": graph}, ctx)
        graph["quality_report"] = q_res.data.get("quality_report", {})

        self.save_graph(project_id, graph)
        return graph

    def build_graph_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.build_graph(**kwargs))

    async def query_graph(
        self,
        project_id: str,
        query: str,
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        education_level: str = "undergraduate",
        retrieval_mode: str = "hybrid",
    ) -> Dict[str, Any]:
        graph = self.load_graph(project_id)
        if not graph:
            return {
                "answer": "尚未构建知识图谱，请先调用 build",
                "graph_paths": [],
                "supporting_sources": [],
                "limitations": ["graph_not_found"],
            }
        skill = GraphReasoningSkill()
        res = await skill.run(
            {
                "query": query,
                "graph": graph,
                "hypotheses": hypotheses or self._load_hypotheses(project_id),
                "education_level": education_level,
                "retrieval_mode": retrieval_mode,
            },
            {"project_id": project_id},
        )
        return res.data

    async def incremental_update(
        self,
        project_id: str,
        new_facts: Optional[List[Dict[str, Any]]] = None,
        new_citation_map: Optional[List[Dict[str, Any]]] = None,
        research_question: str = "",
    ) -> Dict[str, Any]:
        graph = self.load_graph(project_id)
        if not graph:
            raise FileNotFoundError(f"项目 {project_id} 尚无知识图谱，请先 build")

        skill = IncrementalGraphUpdateSkill()
        res = await skill.run(
            {
                "graph": graph,
                "new_facts": new_facts or [],
                "new_citation_map": new_citation_map or [],
            },
            {"project_id": project_id},
        )
        updated = res.data.get("graph", graph)

        comm_skill = GraphCommunitySummarySkill()
        comm_res = await comm_skill.run(
            {"graph": updated, "research_question": research_question},
            {"project_id": project_id},
        )
        updated["communities"] = comm_res.data.get("communities", [])

        quality_skill = KgQualityReviewSkill()
        q_res = await quality_skill.run({"graph": updated}, {"project_id": project_id})
        updated["quality_report"] = q_res.data.get("quality_report", {})
        self.save_graph(project_id, updated)
        return {"graph": updated, "incremental": res.data.get("incremental", {})}

    def get_scenario_catalog(self) -> Dict[str, Any]:
        return get_scenario_catalog()

    def query_graph_sync(self, project_id: str, query: str) -> Dict[str, Any]:
        return asyncio.run(self.query_graph(project_id, query))

    async def apply_feedback(self, project_id: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
        graph = self.load_graph(project_id)
        if not graph:
            raise FileNotFoundError(f"项目 {project_id} 尚无知识图谱")

        skill = HumanFeedbackUpdateSkill()
        res = await skill.run({"graph": graph, "feedback": feedback}, {"project_id": project_id})
        updated = res.data.get("graph", graph)

        quality_skill = KgQualityReviewSkill()
        q_res = await quality_skill.run({"graph": updated}, {"project_id": project_id})
        updated["quality_report"] = q_res.data.get("quality_report", {})
        self.save_graph(project_id, updated)
        return {"graph": updated, "feedback_applied": res.data.get("feedback_applied")}

    def apply_feedback_sync(self, project_id: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self.apply_feedback(project_id, feedback))

    async def rebuild_graph(
        self,
        project_id: str,
        literature_mining: Optional[Dict[str, Any]] = None,
        knowledge_gap: Optional[Dict[str, Any]] = None,
        project_mode: Optional[str] = None,
        research_question: str = "",
    ) -> Dict[str, Any]:
        existing = self.load_graph(project_id) or {}
        graph = await self.build_graph(
            project_id=project_id,
            literature_mining=literature_mining,
            knowledge_gap=knowledge_gap,
            project_mode=project_mode,
            research_question=research_question,
        )
        if existing.get("feedback_history"):
            graph["feedback_history"] = existing["feedback_history"]
            self.save_graph(project_id, graph)
        return graph

    def rebuild_graph_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.rebuild_graph(**kwargs))

    def get_kg_context_for_agents(self, project_id: str) -> Dict[str, Any]:
        graph = self.load_graph(project_id)
        if not graph:
            return {}
        return {
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "quality_report": graph.get("quality_report", {}),
            "evidence_graph": graph.get("evidence_graph", {}),
            "schema": graph.get("schema", {}),
            "communities": graph.get("communities", [])[:5],
            "domain_scenario": graph.get("domain_scenario"),
            "graph_summary": self._summarize_graph(graph),
        }

    @staticmethod
    def _summarize_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        by_type: Dict[str, int] = {}
        for n in nodes:
            t = n.get("type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1
        rel_counts: Dict[str, int] = {}
        for e in edges:
            r = e.get("relation", "unknown")
            rel_counts[r] = rel_counts.get(r, 0) + 1
        return {"node_types": by_type, "relation_types": rel_counts}


def get_knowledge_graph_service(db: Session) -> KnowledgeGraphService:
    return KnowledgeGraphService(db)
