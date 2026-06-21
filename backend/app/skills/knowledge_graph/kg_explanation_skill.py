"""KAG / Youtu-GraphRAG 风格多跳推理与溯源解释 Skill"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult
from app.skills.knowledge_graph.domain_profiles import EDUCATION_PROFILES, normalize_education_level


class KgExplanationSkill(BaseSkill):
    name = "KgExplanation"
    description = "生成面向不同教育层级的可解释回答与溯源链"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        query = input_data.get("query", "")
        graph = input_data.get("graph", {}) or {}
        graph_paths = input_data.get("graph_paths", []) or []
        supporting_sources = input_data.get("supporting_sources", []) or []
        subgraph = input_data.get("subgraph", {}) or {}
        communities = input_data.get("communities", []) or []
        retrieval_mode = input_data.get("retrieval_mode", "hybrid")
        education_level = normalize_education_level(input_data.get("education_level"))
        profile = EDUCATION_PROFILES[education_level]
        intent = input_data.get("intent", "general")
        raw_answer = input_data.get("raw_answer", "")

        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        edges = graph.get("edges", [])

        reasoning_chain = self._build_reasoning_chain(
            graph_paths, nodes, edges, max_steps=profile["max_path_steps"]
        )
        provenance = self._build_provenance(reasoning_chain, supporting_sources, subgraph)
        explanation = self._adapt_explanation(
            query, raw_answer, reasoning_chain, provenance, communities,
            education_level, profile, retrieval_mode, intent,
        )

        result.data = {
            "answer": explanation["narrative"],
            "reasoning_chain": reasoning_chain,
            "provenance": provenance,
            "education_level": education_level,
            "education_label": profile["label"],
            "retrieval_mode": retrieval_mode,
            "global_context": explanation.get("global_context", ""),
            "local_context": explanation.get("local_context", ""),
            "limitations": explanation.get("limitations", []),
            "citation_spans": provenance.get("citation_spans", []),
        }
        return result

    def _build_reasoning_chain(
        self,
        graph_paths: List,
        nodes: Dict[str, Dict],
        edges: List[Dict],
        max_steps: int,
    ) -> List[Dict[str, Any]]:
        chain: List[Dict[str, Any]] = []
        step = 1
        for path in graph_paths[:max_steps]:
            if isinstance(path, list) and len(path) >= 2:
                chain.append({
                    "step": step,
                    "type": "path",
                    "content": " → ".join(str(p) for p in path),
                    "inference": f"由「{path[0]}」经关系推导至「{path[-1]}」",
                })
                step += 1
            elif isinstance(path, str):
                chain.append({"step": step, "type": "note", "content": path, "inference": "图谱检索命中"})
                step += 1

        for e in edges[:3]:
            if step > max_steps:
                break
            src = nodes.get(e.get("source"), {})
            tgt = nodes.get(e.get("target"), {})
            if e.get("evidence"):
                chain.append({
                    "step": step,
                    "type": "evidence",
                    "content": e.get("evidence", "")[:200],
                    "inference": (
                        f"{src.get('label', '?')} --[{e.get('relation')}]--> "
                        f"{tgt.get('label', '?')}"
                    ),
                    "source_title": e.get("source_title", ""),
                    "confidence": e.get("confidence"),
                })
                step += 1
        return chain

    @staticmethod
    def _build_provenance(
        reasoning_chain: List[Dict],
        supporting_sources: List[str],
        subgraph: Dict[str, Any],
    ) -> Dict[str, Any]:
        citation_spans = []
        for item in reasoning_chain:
            if item.get("source_title"):
                citation_spans.append({
                    "text": item.get("content", "")[:120],
                    "source_title": item["source_title"],
                    "confidence": item.get("confidence"),
                })
        for src in supporting_sources[:10]:
            if src and not any(c["source_title"] == src for c in citation_spans):
                citation_spans.append({"text": "", "source_title": src, "confidence": None})

        return {
            "source_count": len(citation_spans),
            "citation_spans": citation_spans,
            "subgraph_nodes": len(subgraph.get("nodes", [])),
            "subgraph_edges": len(subgraph.get("edges", [])),
            "traceability": "每条推理步骤均可回溯至 source_title / source_ids",
        }

    def _adapt_explanation(
        self,
        query: str,
        raw_answer: str,
        chain: List[Dict],
        provenance: Dict,
        communities: List[Dict],
        level: str,
        profile: Dict,
        retrieval_mode: str,
        intent: str,
    ) -> Dict[str, Any]:
        limitations: List[str] = []
        global_ctx = ""
        local_ctx = ""

        if communities and retrieval_mode in ("global", "hybrid"):
            top = communities[0] if communities else {}
            global_ctx = top.get("summary", "")
            if retrieval_mode == "global" and not chain:
                limitations.append("当前为全局主题检索，细节需切换到 local/hybrid 模式")

        if chain:
            local_ctx = "；".join(c.get("inference", "") for c in chain[:3])

        if level in ("primary", "secondary"):
            narrative = self._plain_narrative(query, raw_answer, chain, global_ctx)
        elif level == "undergraduate":
            narrative = (
                f"关于「{query}」：{raw_answer}。"
                f"{' 局部证据：' + local_ctx + '。' if local_ctx else ''}"
                f"{' 领域背景：' + global_ctx[:120] + '…' if global_ctx else ''}"
            )
        else:
            conf_parts = []
            if profile.get("show_confidence"):
                for c in chain:
                    if c.get("confidence") is not None:
                        conf_parts.append(f"{c.get('inference', '')}(conf={c['confidence']})")
            narrative = (
                f"【{profile['label']}级回答】{raw_answer}。"
                f" 推理链 {len(chain)} 步；溯源 {provenance.get('source_count', 0)} 条。"
                f"{' 置信标注：' + ' | '.join(conf_parts[:3]) + '。' if conf_parts else ''}"
                f"{' 全局社区：' + global_ctx[:150] if global_ctx else ''}"
            )

        if provenance.get("source_count", 0) == 0:
            limitations.append("部分结论缺少可验证文献来源，请补充论文或教材")

        return {
            "narrative": narrative.strip(),
            "global_context": global_ctx,
            "local_context": local_ctx,
            "limitations": limitations,
        }

    @staticmethod
    def _plain_narrative(query: str, raw_answer: str, chain: List[Dict], global_ctx: str) -> str:
        simple = raw_answer.replace("supports", "支持").replace("evaluates_on", "在…上测试")
        parts = [f"你问的是：{query}", f"简要回答：{simple}"]
        if chain:
            parts.append(f"依据：{chain[0].get('content', '')[:80]}")
        if global_ctx:
            parts.append(f"背景：{global_ctx[:100]}")
        parts.append("以上信息来自已导入的论文和资料，可点击图谱中的边查看原文出处。")
        return " ".join(parts)
