"""
PDF 证据提取 Skill
参考能力：Hermes ocr-and-documents
——从 Document chunks 中提取可引用事实，每条 fact 须绑定
document_id / chunk_id / page_number / quote_text。
"""
import logging
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult
from app.services.vector_store import (
    search_vector_store,
    SearchResult,
    get_vector_store,
)

logger = logging.getLogger(__name__)


class PdfEvidenceExtractionSkill(BaseSkill):
    """PDF 证据提取 Skill

    输入:
      - project_id: str             项目 ID
      - research_question: str      研究问题
      - top_k: int = 10             Zvec 检索 Top-K

    输出 (SkillResult.data):
      - facts: List[dict]           结构化事实列表
      - total_chunks_retrieved: int 检索到的 chunk 总数
      - fact_ids: List[str]         事实 ID 列表
    """

    name = "PdfEvidenceExtraction"
    description = "从项目 PDF 文献 Chunk 中提取可引用的结构化事实"
    source_reference = "Hermes (arxiv:2501.11111) — 文献证据抽取能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)

        project_id = input_data.get("project_id", "")
        research_question = input_data.get("research_question", "")
        top_k = input_data.get("top_k", 10)

        if not project_id:
            result.add_error("缺少 project_id")
            return result
        if not research_question:
            result.add_error("缺少 research_question")
            return result

        try:
            vs = get_vector_store()
            if not vs.has_index(project_id):
                result.add_warning("当前项目无可索引文献，请先上传 PDF 或导入 arXiv 文献")
                result.data = {"facts": [], "total_chunks_retrieved": 0, "fact_ids": []}
                return result

            search_results: List[SearchResult] = search_vector_store(
                project_id=project_id,
                query=research_question,
                top_k=max(1, min(top_k, 30)),
            )

            if not search_results:
                result.add_warning("未检索到与当前研究问题相关的文献片段")
                result.data = {"facts": [], "total_chunks_retrieved": 0, "fact_ids": []}
                return result

            facts: List[dict] = []
            for i, sr in enumerate(search_results, 1):
                facts.append({
                    "fact_id": f"evfact_{i:03d}",
                    "content": sr.content[:500] if sr.content else "",
                    "document_id": sr.document_id,
                    "source_chunk_id": sr.chunk_id,
                "chunk_id": sr.chunk_id,
                    "page_number": sr.page_number,
                    "quote_text": sr.content[:300] if sr.content else "",
                    "source_title": sr.source_title,
                    "source_paper_title": sr.source_title,
                    "relevance_score": sr.similarity_score,
                })

            fact_ids = [f["fact_id"] for f in facts]

            result.data = {
                "facts": facts,
                "total_chunks_retrieved": len(search_results),
                "fact_ids": fact_ids,
            }
            result.metadata = {
                "project_id": project_id,
                "top_k": top_k,
            }
            return result

        except Exception as e:
            logger.exception(f"PdfEvidenceExtractionSkill 异常: {e}")
            result.add_error(f"证据提取异常: {e}")
            return result