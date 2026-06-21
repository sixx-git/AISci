"""人工反馈更新 Skill"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph._utils import new_edge_id, new_node_id

CHINA_TZ = timezone(timedelta(hours=8))


class HumanFeedbackUpdateSkill(BaseSkill):
    name = "HumanFeedbackUpdate"
    description = "应用人工确认/删除/修改节点和边"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        graph = dict(input_data.get("graph", {}) or {})
        feedback = input_data.get("feedback", {}) or {}
        action = feedback.get("action", "")
        target_type = feedback.get("target_type", "edge")

        history: List[Dict] = graph.get("feedback_history", [])
        entry = {
            "action": action,
            "target_type": target_type,
            "target_id": feedback.get("target_id"),
            "payload": feedback.get("payload", {}),
            "timestamp": datetime.now(CHINA_TZ).isoformat(),
        }
        history.append(entry)

        nodes = list(graph.get("nodes", []))
        edges = list(graph.get("edges", []))

        if action == "delete" and target_type == "node":
            tid = feedback.get("target_id")
            nodes = [n for n in nodes if n.get("id") != tid]
            edges = [e for e in edges if e.get("source") != tid and e.get("target") != tid]

        elif action == "delete" and target_type == "edge":
            tid = feedback.get("target_id")
            edges = [e for e in edges if e.get("id") != tid]

        elif action == "verify" and target_type == "edge":
            tid = feedback.get("target_id")
            for e in edges:
                if e.get("id") == tid:
                    e["human_verified"] = True
                    e["confidence"] = min(1.0, e.get("confidence", 0.5) + 0.15)

        elif action == "update" and target_type == "node":
            tid = feedback.get("target_id")
            payload = feedback.get("payload", {})
            for n in nodes:
                if n.get("id") == tid:
                    n.update({k: v for k, v in payload.items() if k in ("label", "description", "type")})

        elif action == "add" and target_type == "edge":
            payload = feedback.get("payload", {})
            if payload.get("source") and payload.get("target") and payload.get("evidence"):
                edges.append({
                    "id": new_edge_id(),
                    "source": payload["source"],
                    "target": payload["target"],
                    "relation": payload.get("relation", "supports"),
                    "evidence": payload["evidence"],
                    "source_title": payload.get("source_title", "human_feedback"),
                    "paper_id": payload.get("paper_id", ""),
                    "page": payload.get("page"),
                    "confidence": 0.95,
                    "human_verified": True,
                })

        elif action == "add" and target_type == "node":
            payload = feedback.get("payload", {})
            if payload.get("label") and payload.get("type"):
                nodes.append({
                    "id": new_node_id(),
                    "type": payload["type"],
                    "label": payload["label"],
                    "description": payload.get("description", ""),
                    "source_ids": payload.get("source_ids", ["human:feedback"]),
                    "confidence": 0.95,
                    "metadata": {"human_added": True},
                })

        graph["nodes"] = nodes
        graph["edges"] = edges
        graph["feedback_history"] = history[-100:]

        result.data = {"graph": graph, "feedback_applied": entry}
        return result
