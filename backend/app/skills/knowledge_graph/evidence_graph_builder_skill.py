"""证据图构建 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph._utils import new_edge_id, new_node_id


class EvidenceGraphBuilderSkill(BaseSkill):
    name = "EvidenceGraphBuilder"
    description = "构建 Hypothesis→Evidence→Paper→Result 证据链子图"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypotheses = input_data.get("hypotheses", []) or []
        evidence_chains = input_data.get("evidence_chains", []) or []

        nodes: List[Dict] = []
        edges: List[Dict] = []

        for hypo in hypotheses:
            hid = hypo.get("id") or new_node_id("hypothesis")
            htext = hypo.get("hypothesis") or hypo.get("final_version") or ""
            h_node = {
                "id": f"evg_hyp_{hid}",
                "type": "Hypothesis",
                "label": htext[:100],
                "description": htext,
                "source_ids": [f"hypothesis:{hid}"],
                "confidence": 0.9,
                "metadata": {"subgraph": "evidence_graph"},
            }
            nodes.append(h_node)

            chain = hypo.get("evidence_chain") or {}
            if not chain and evidence_chains:
                chain = next((c for c in evidence_chains if c.get("hypothesis_id") == hid), {})

            for ev in (chain.get("supporting_evidence") or []) + (chain.get("counter_evidence") or []):
                ev_id = ev.get("evidence_id") or new_node_id("ev")
                claim = ev.get("claim") or ""
                ev_node = {
                    "id": f"evg_ev_{ev_id}",
                    "type": "Evidence",
                    "label": claim[:80],
                    "description": claim,
                    "source_ids": [ev_id],
                    "confidence": ev.get("reliability_score", 0.7),
                    "metadata": {"stance": ev.get("stance"), "subgraph": "evidence_graph"},
                }
                nodes.append(ev_node)
                rel = "supports" if ev.get("stance") != "refute" else "contradicts"
                edges.append({
                    "id": new_edge_id("evg"),
                    "source": h_node["id"],
                    "target": ev_node["id"],
                    "relation": rel,
                    "evidence": claim[:300],
                    "source_title": ev.get("source_title", ""),
                    "paper_id": ev.get("paper_id", ""),
                    "page": None,
                    "confidence": ev.get("relevance_score", 0.6),
                    "human_verified": False,
                })

                paper_title = ev.get("source_title") or ""
                if paper_title:
                    p_node = {
                        "id": f"evg_paper_{ev_id}",
                        "type": "Paper",
                        "label": paper_title[:120],
                        "description": ev.get("quote_or_summary", "")[:300],
                        "source_ids": [ev.get("paper_id") or paper_title],
                        "confidence": 0.85,
                        "metadata": {"subgraph": "evidence_graph"},
                    }
                    nodes.append(p_node)
                    edges.append({
                        "id": new_edge_id("evg"),
                        "source": ev_node["id"],
                        "target": p_node["id"],
                        "relation": "cites",
                        "evidence": claim[:200],
                        "source_title": paper_title,
                        "paper_id": ev.get("paper_id", ""),
                        "page": None,
                        "confidence": 0.8,
                        "human_verified": False,
                    })

        result.data = {"evidence_graph": {"nodes": nodes, "edges": edges}}
        return result
