"""图谱推理 Skill — 融合 GraphRAG / KAG / Youtu-GraphRAG 推理与解释"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph.domain_profiles import (
    normalize_education_level,
    normalize_retrieval_mode,
)
from app.skills.knowledge_graph.graph_rag_retrieval_skill import GraphRagRetrievalSkill
from app.skills.knowledge_graph.kg_explanation_skill import KgExplanationSkill


class GraphReasoningSkill(BaseSkill):
    name = "GraphReasoning"
    description = "自然语言图谱查询、多跳路径推理与分层解释"

    QUERY_PATTERNS = [
        (r"哪些方法.*(数据集|dataset|evaluat)", "method_datasets"),
        (r"哪些论文.*支持.*假设|support.*hypothesis", "papers_support_hypothesis"),
        (r"缺少.*证据|missing.*evidence", "missing_evidence"),
        (r"缓解.*non[- ]?iid|handles.*non", "non_iid_methods"),
        (r"通信成本|communication cost|comm cost", "comm_cost_methods"),
        (r"使用了哪些数据集|method.*dataset", "method_datasets"),
        (r"领域.*概览|整体.*研究|summary|overview", "global_overview"),
    ]

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        query = input_data.get("query", "")
        graph = input_data.get("graph", {}) or {}
        hypotheses = input_data.get("hypotheses", []) or []
        education_level = normalize_education_level(input_data.get("education_level"))
        retrieval_mode = normalize_retrieval_mode(input_data.get("retrieval_mode"))

        ql = query.lower()
        intent = "general"
        for pat, name in self.QUERY_PATTERNS:
            if re.search(pat, ql, re.I):
                intent = name
                break

        if intent == "global_overview":
            retrieval_mode = "global"

        rag = GraphRagRetrievalSkill()
        rag_res = await rag.run(
            {
                "graph": graph,
                "query": query,
                "max_depth": 3,
                "retrieval_mode": retrieval_mode,
                "communities": graph.get("communities", []),
            },
            context,
        )
        subgraph = rag_res.data.get("subgraph", {})
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        edges = graph.get("edges", [])

        paths: List = []
        sources: List[str] = []
        limitations: List[str] = []
        answer_parts: List[str] = []

        if intent == "method_datasets":
            for e in edges:
                if e.get("relation") in ("uses", "evaluates_on"):
                    src = nodes.get(e["source"], {})
                    tgt = nodes.get(e["target"], {})
                    if src.get("type") == "Method" and tgt.get("type") == "Dataset":
                        paths.append([src.get("label"), e["relation"], tgt.get("label")])
                        sources.append(e.get("source_title", ""))
            answer_parts.append(f"找到 {len(paths)} 条方法-数据集关系")

        elif intent == "papers_support_hypothesis":
            for e in edges:
                if e.get("relation") == "supports":
                    src = nodes.get(e["source"], {})
                    if src.get("type") == "Hypothesis":
                        paths.append([src.get("label"), "supports", e.get("evidence", "")[:60]])
                        sources.append(e.get("source_title", ""))
            answer_parts.append(f"找到 {len(paths)} 条支持假设的证据边")

        elif intent == "missing_evidence":
            for n in graph.get("nodes", []):
                if n.get("type") == "Hypothesis":
                    has_support = any(
                        e.get("relation") == "supports" and e.get("source") == n["id"] for e in edges
                    )
                    if not has_support:
                        paths.append([n.get("label"), "missing", "supporting_evidence"])
            answer_parts.append(f"检测到 {len(paths)} 条假设缺少支持证据")

        elif intent == "non_iid_methods":
            keywords = ("non-iid", "non iid", "fedprox", "scaffold", "fedmd", "personalized")
            for n in graph.get("nodes", []):
                if n.get("type") == "Method":
                    text = f"{n.get('label')} {n.get('description')}".lower()
                    if any(k in text for k in keywords):
                        paths.append([n.get("label"), "algorithm_handles_non_iid", "Non-IID"])
                        sources.extend(n.get("source_ids", []))
            answer_parts.append(f"找到 {len(paths)} 个与 Non-IID 相关的方法/关系")

        elif intent == "comm_cost_methods":
            for e in edges:
                if e.get("relation") in ("algorithm_increases_comm_cost", "measured_by"):
                    paths.append([
                        nodes.get(e["source"], {}).get("label", ""),
                        e["relation"],
                        nodes.get(e["target"], {}).get("label", ""),
                    ])
                    sources.append(e.get("source_title", ""))
            answer_parts.append(f"找到 {len(paths)} 条通信成本相关路径")

        elif intent == "global_overview":
            comms = graph.get("communities", [])
            for comm in comms[:3]:
                paths.append(["社区", comm.get("dominant_type"), comm.get("summary", "")[:80]])
            answer_parts.append(f"图谱含 {len(comms)} 个主题社区")

        else:
            answer_parts.append(
                f"检索子图含 {len(subgraph.get('nodes', []))} 个节点、"
                f"{len(subgraph.get('edges', []))} 条边"
            )

        raw_answer = "；".join(answer_parts) or "未找到匹配路径"

        explain_skill = KgExplanationSkill()
        explain_res = await explain_skill.run(
            {
                "query": query,
                "graph": graph,
                "graph_paths": paths[:20],
                "supporting_sources": list(dict.fromkeys(s for s in sources if s))[:15],
                "subgraph": subgraph,
                "communities": graph.get("communities", []),
                "retrieval_mode": rag_res.data.get("retrieval_mode", retrieval_mode),
                "education_level": education_level,
                "intent": intent,
                "raw_answer": raw_answer,
            },
            context,
        )
        explanation = explain_res.data

        result.data = {
            "answer": explanation.get("answer", raw_answer),
            "raw_answer": raw_answer,
            "graph_paths": paths[:20],
            "supporting_sources": list(dict.fromkeys(s for s in sources if s))[:15],
            "limitations": limitations + explanation.get("limitations", []),
            "intent": intent,
            "subgraph": subgraph,
            "retrieval_mode": rag_res.data.get("retrieval_mode", retrieval_mode),
            "education_level": education_level,
            "reasoning_chain": explanation.get("reasoning_chain", []),
            "provenance": explanation.get("provenance", {}),
            "global_context": explanation.get("global_context", ""),
            "local_context": explanation.get("local_context", ""),
            "citation_spans": explanation.get("citation_spans", []),
            "global_hit": rag_res.data.get("global_hit", {}),
            "local_hit": rag_res.data.get("local_hit", {}),
        }
        return result
