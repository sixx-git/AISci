"""
论文全文 RAG Skill
参考能力：PaperQA / PaperQA2、OpenScholar
——基于项目向量索引检索论文全文片段，返回带引用的上下文 passages。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult
from app.services.vector_store import SearchResult, get_vector_store, search_vector_store

logger = logging.getLogger(__name__)


class PaperFullTextRAGSkill(BaseSkill):
    """论文全文 RAG 检索 Skill

    输入:
      - project_id: str
      - query: str                    检索查询（默认 research_question）
      - research_question: str        备选查询
      - top_k: int = 8
      - min_score: float = 0.0        最低相似度阈值

    输出 (SkillResult.data):
      - passages: List[dict]          检索片段（含引用元数据）
      - context_text: str               拼接后的 RAG 上下文
      - total: int
      - sources: List[str]              去重后的来源标题
    """

    name = "PaperFullTextRAG"
    description = "基于项目文献向量索引检索论文全文片段，构建带引用的 RAG 上下文"
    source_reference = (
        "PaperQA / PaperQA2 (arxiv:2312.07559) — full-text RAG; "
        "OpenScholar — citation-backed retrieval"
    )

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        project_id = input_data.get("project_id", "") or context.get("project_id", "")
        query = (
            input_data.get("query")
            or input_data.get("research_question")
            or context.get("research_question")
            or ""
        ).strip()
        top_k = max(1, min(int(input_data.get("top_k", 8)), 20))
        min_score = float(input_data.get("min_score", 0.0))

        if not project_id:
            result.add_error("缺少 project_id")
            return result
        if not query:
            result.add_error("缺少 query / research_question")
            return result

        try:
            vs = get_vector_store()
            if not vs.has_index(project_id):
                result.add_warning("项目尚未构建文献向量索引，请先上传 PDF 或导入文献")
                result.data = {"passages": [], "context_text": "", "total": 0, "sources": []}
                return result

            hits: List[SearchResult] = search_vector_store(
                project_id=project_id,
                query=query,
                top_k=top_k,
            )
            if min_score > 0:
                hits = [h for h in hits if h.similarity_score >= min_score]

            passages = [self._to_passage(i, h) for i, h in enumerate(hits, 1)]
            sources = list(dict.fromkeys(p["source_title"] for p in passages if p.get("source_title")))
            context_text = self._build_context(passages)

            result.data = {
                "passages": passages,
                "context_text": context_text,
                "total": len(passages),
                "sources": sources,
            }
            if not passages:
                result.add_warning("未检索到与查询相关的全文片段")
            return result

        except Exception as e:
            logger.exception("PaperFullTextRAGSkill 异常: %s", e)
            result.add_error(f"全文 RAG 检索异常: {e}")
            return result

    @staticmethod
    def _to_passage(rank: int, sr: SearchResult) -> Dict[str, Any]:
        return {
            "passage_id": f"rag_{rank:03d}",
            "rank": rank,
            "content": (sr.content or "")[:1200],
            "chunk_id": sr.chunk_id,
            "document_id": sr.document_id,
            "page_number": sr.page_number,
            "source_title": sr.source_title,
            "authors": sr.authors,
            "year": sr.year,
            "doi": sr.doi,
            "external_id": sr.external_id,
            "source_url": sr.source_url,
            "similarity_score": sr.similarity_score,
        }

    @staticmethod
    def _build_context(passages: List[Dict[str, Any]]) -> str:
        blocks: List[str] = []
        for p in passages:
            title = p.get("source_title") or "Unknown"
            page = p.get("page_number")
            page_hint = f", p.{page}" if page else ""
            blocks.append(
                f"[{p.get('passage_id')}] 《{title}》{page_hint}\n{p.get('content', '')}"
            )
        return "\n\n---\n\n".join(blocks)
