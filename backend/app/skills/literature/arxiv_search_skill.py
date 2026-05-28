"""
ArXiv 搜索 Skill
参考能力：Hermes research / arxiv
——基于 research_question / keywords 检索 arXiv，复用当前 arxiv_source.py，
支持 fallback，输出结构化 JSON。
"""
import logging
from typing import Dict, Any

from app.skills.base import BaseSkill, SkillResult
from app.services.literature_sources.arxiv_source import ArxivSource, ArxivPaper

logger = logging.getLogger(__name__)


class ArxivSearchSkill(BaseSkill):
    """arXiv 文献搜索 Skill

    输入:
      - research_question: str        研究问题
      - keywords: List[str] | None   额外关键词
      - max_results: int = 10        最大返回数

    输出 (SkillResult.data):
      - papers: List[dict]           标准化论文元数据
      - fallback: bool               是否使用了本地缓存
      - total: int                   实际返回数量
      - warning: str                 降级警告文本
    """

    name = "ArxivSearch"
    description = "根据研究问题 / 关键词检索 arXiv 文献，支持网络降级到本地缓存"
    source_reference = "Hermes (arxiv:2501.11111) — 学术文献检索能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)

        research_question = input_data.get("research_question", "")
        keywords = input_data.get("keywords", [])
        max_results = input_data.get("max_results", 10)

        if not isinstance(keywords, list):
            keywords = []

        query_terms = [research_question] if research_question else []
        extra = [k for k in keywords if isinstance(k, str) and k]
        if extra:
            query_terms = extra + query_terms

        search_query = " AND ".join(query_terms) if query_terms else ""
        if not search_query:
            result.add_error("搜索关键词为空")
            return result

        try:
            source = ArxivSource()
            papers_raw, fallback, warning_msg = source.search_with_fallback(
                query=search_query, max_results=max_results
            )
        except Exception as e:
            logger.exception(f"ArxivSearchSkill 搜索失败: {e}")
            result.add_error(f"arXiv 搜索异常: {e}")
            return result

        papers: list = []
        for p in papers_raw:
            if isinstance(p, ArxivPaper):
                papers.append(p.to_dict())
            elif isinstance(p, dict):
                papers.append(p)

        if fallback:
            result.add_warning(warning_msg or "已使用本地缓存文献，结果可能不完整")

        result.data = {
            "papers": papers,
            "fallback": fallback,
            "total": len(papers),
            "query": search_query,
            "warning": warning_msg if fallback else "",
        }
        result.metadata = {
            "source": "arxiv",
            "search_query": search_query,
            "max_results": max_results,
        }
        return result