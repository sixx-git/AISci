"""
Ideation 新颖性检查 Skill（对齐 AI Scientist v2 ideation）
——在假设生成前，通过 OpenAlex + Semantic Scholar 检索相近工作，
评估研究空白与可探索方向。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.literature.search_papers_skill import SearchPapersSkill
from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)


class IdeationNoveltySkill(BaseSkill):
    """基于外部文献库（OpenAlex / Semantic Scholar）的 ideation 新颖性预检。"""

    name = "IdeationNovelty"
    description = "假设生成前检索 OpenAlex/S2，识别相似工作与新颖角度"
    source_reference = "AI Scientist v2 ideation + OpenAlex/Semantic Scholar"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = (input_data.get("research_question") or "").strip()
        knowledge_gaps = input_data.get("knowledge_gaps") or []
        keywords = input_data.get("keywords") or []
        num_ideas = int(input_data.get("num_ideas") or 3)

        if not research_question:
            result.add_warning("研究问题为空，跳过 ideation 新颖性检查")
            result.data = self._empty_payload(num_ideas)
            return result

        query = self._build_query(research_question, knowledge_gaps, keywords)
        papers: List[dict] = []
        try:
            search_skill = SearchPapersSkill()
            search_res = await search_skill.run(
                input_data={
                    "research_question": query,
                    "keywords": keywords,
                    "max_results": 20,
                    "sources": ["openalex", "semantic_scholar"],
                },
                context={"stage": "ideation_novelty"},
            )
            papers = (search_res.data or {}).get("papers") or []
            result.metadata["search_warnings"] = search_res.warnings
        except Exception as exc:
            logger.warning(f"Ideation 文献检索失败: {exc}")
            result.add_warning(f"外部文献检索失败: {exc}")

        overlap_stats = self._compute_overlap(research_question, papers)
        llm_block = self._llm_synthesize(
            research_question, papers[:12], knowledge_gaps, num_ideas, overlap_stats
        )

        result.data = {
            "research_question": research_question,
            "query_used": query,
            "external_papers_count": len(papers),
            "top_similar_works": overlap_stats.get("top_similar", [])[:8],
            "novelty_score": llm_block.get("novelty_score", overlap_stats.get("heuristic_novelty", 6.5)),
            "novelty_risk": llm_block.get("novelty_risk", "medium"),
            "research_gaps": llm_block.get("research_gaps", []),
            "suggested_angles": llm_block.get("suggested_angles", [])[:num_ideas],
            "avoid_topics": llm_block.get("avoid_topics", []),
            "num_ideas_requested": num_ideas,
            "sources_used": ["openalex", "semantic_scholar"],
            "assessment": llm_block.get("assessment", ""),
        }
        if result.data["novelty_risk"] == "high":
            result.add_warning("外部文献显示高度重叠，建议在 ideation 阶段调整方向")
        return result

    @staticmethod
    def _build_query(research_question: str, knowledge_gaps: List[Any], keywords: List[str]) -> str:
        parts = [research_question[:200]]
        for kw in keywords[:5]:
            if kw:
                parts.append(str(kw))
        for gap in knowledge_gaps[:3]:
            if isinstance(gap, dict):
                parts.append(str(gap.get("gap") or gap.get("description") or "")[:80])
            elif gap:
                parts.append(str(gap)[:80])
        return " ".join(p for p in parts if p.strip())[:400]

    @staticmethod
    def _tokenize(text: str) -> set:
        text = text.lower()
        tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", text))
        stop = {"the", "and", "for", "with", "using", "based", "study", "research", "analysis"}
        return {t for t in tokens if t not in stop}

    def _compute_overlap(self, research_question: str, papers: List[dict]) -> Dict[str, Any]:
        q_tokens = self._tokenize(research_question)
        scored: List[dict] = []
        for p in papers:
            title = p.get("title") or ""
            abstract = p.get("abstract") or ""
            blob = f"{title} {abstract}"
            p_tokens = self._tokenize(blob)
            if not q_tokens or not p_tokens:
                overlap = 0.0
            else:
                overlap = len(q_tokens & p_tokens) / max(len(q_tokens), 1)
            scored.append({
                "title": title,
                "year": p.get("year"),
                "source": p.get("source"),
                "overlap_ratio": round(overlap, 3),
                "citation_count": p.get("citation_count"),
                "url": p.get("url") or p.get("doi"),
            })
        scored.sort(key=lambda x: x["overlap_ratio"], reverse=True)
        top = scored[:10]
        avg_overlap = sum(x["overlap_ratio"] for x in top) / max(len(top), 1)
        heuristic = round(max(2.0, min(10.0, 10.0 - avg_overlap * 12)), 2)
        risk = "low" if heuristic >= 7.5 else ("high" if heuristic < 5.5 else "medium")
        return {
            "top_similar": top,
            "avg_overlap": round(avg_overlap, 3),
            "heuristic_novelty": heuristic,
            "novelty_risk": risk,
        }

    @staticmethod
    def _llm_synthesize(
        research_question: str,
        papers: List[dict],
        knowledge_gaps: List[Any],
        num_ideas: int,
        overlap_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        papers_text = "\n".join(
            f"- [{p.get('year', '?')}] {p.get('title', '')} (overlap={p.get('overlap_ratio', '?')})"
            for p in papers[:10]
        ) or "（未检索到外部论文）"
        gaps_text = "\n".join(
            f"- {g.get('gap', g) if isinstance(g, dict) else g}" for g in knowledge_gaps[:5]
        ) or "（无）"

        prompt = f"""你是科研 ideation 顾问。基于 OpenAlex/Semantic Scholar 检索结果，在正式生成假设前给出新颖性评估与 {num_ideas} 个可探索方向。

研究问题：{research_question}

知识缺口：
{gaps_text}

相似外部工作（Top）：
{papers_text}

启发式新颖性分：{overlap_stats.get('heuristic_novelty')}，风险：{overlap_stats.get('novelty_risk')}

请输出 JSON：novelty_score(0-10)、novelty_risk、suggested_angles(恰好{num_ideas}条具体方向)、research_gaps、avoid_topics、assessment。"""

        schema = {
            "novelty_score": 7.0,
            "novelty_risk": "medium",
            "suggested_angles": [f"方向{i+1}" for i in range(num_ideas)],
            "research_gaps": ["gap1"],
            "avoid_topics": ["已饱和方向"],
            "assessment": "整体评估",
        }
        try:
            return qwen_structured_chat(prompt=prompt, schema_example=schema, prompt_version="ideation_novelty")
        except Exception as exc:
            logger.warning(f"Ideation LLM 合成失败: {exc}")
            angles = [f"基于研究问题的探索方向 {i+1}" for i in range(num_ideas)]
            return {
                "novelty_score": overlap_stats.get("heuristic_novelty", 6.5),
                "novelty_risk": overlap_stats.get("novelty_risk", "medium"),
                "suggested_angles": angles,
                "research_gaps": [],
                "avoid_topics": [],
                "assessment": "使用启发式新颖性评估（LLM 不可用）",
            }

    @staticmethod
    def _empty_payload(num_ideas: int) -> Dict[str, Any]:
        return {
            "research_question": "",
            "query_used": "",
            "external_papers_count": 0,
            "top_similar_works": [],
            "novelty_score": None,
            "novelty_risk": "unknown",
            "research_gaps": [],
            "suggested_angles": [],
            "avoid_topics": [],
            "num_ideas_requested": num_ideas,
            "sources_used": [],
            "assessment": "",
        }
