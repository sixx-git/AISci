"""
文献挖掘智能体 (LiteratureMiningAgent)
——基于项目文献库真实检索结果提取事实，提供可引用证据。
"""
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.vector_store import (
    search_vector_store,
    SearchResult,
    get_vector_store,
)
from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.skills.literature.pdf_evidence_extraction_skill import PdfEvidenceExtractionSkill
from app.skills.literature.arxiv_search_skill import ArxivSearchSkill
from app.skills.literature.citation_grounding_skill import CitationGroundingSkill
from app.skills.literature.search_papers_skill import SearchPapersSkill
from app.skills.data.multimodal_linking_skill import MultimodalDataLinkingSkill

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class ScienceFact(BaseModel):
    """科学事实 —— 每条事实必须绑定真实文献来源"""
    fact_id: str = Field(..., description="事实 ID")
    content: str = Field(..., description="事实陈述（归纳后的简洁版本）")
    fact_text: Optional[str] = Field(None, description="事实的详细文本，长篇")
    source_chunk_id: str = Field(..., description="来源 Chunk ID")
    document_id: Optional[str] = Field(None, description="来源文档 ID")
    source_paper_title: Optional[str] = Field(None, description="来源论文标题")
    page_number: Optional[int] = Field(None, description="来源页码")
    quote_text: Optional[str] = Field(None, description="原文引用片段（来自 chunk 原文）")
    relevance_score: Optional[float] = Field(None, description="与研究问题的相关性评分 0.0~1.0")


class EvidenceItem(BaseModel):
    """证据项 —— 从原文中提取的引用片段"""
    evidence_id: str = Field(..., description="证据 ID")
    fact_id: str = Field(..., description="关联的事实 ID")
    text: str = Field(..., description="证据原文引用")
    source_chunk_id: str = Field(..., description="来源 Chunk ID")
    document_id: Optional[str] = Field(None, description="来源文档 ID")
    page_number: Optional[int] = Field(None, description="来源页码")
    relevance_score: Optional[float] = Field(None, description="相关性评分 0.0~1.0")


class CitationMapItem(BaseModel):
    """引用映射项 —— 供 ReportGenerationAgent 生成 References"""
    document_id: str = Field(..., description="文档 ID")
    paper_title: Optional[str] = Field(None, description="论文标题")
    title: Optional[str] = Field(None, description="论文标题（别名）")
    authors: Optional[str] = Field(None, description="作者")
    year: Optional[int] = Field(None, description="发表年份")
    source_type: Optional[str] = Field(None, description="来源类型: upload / arxiv / bibtex")
    source_url: Optional[str] = Field(None, description="来源 URL")
    doi: Optional[str] = Field(None, description="DOI")
    external_id: Optional[str] = Field(None, description="外部 ID（arXiv ID 等）")
    fact_ids: List[str] = Field(default_factory=list, description="引用的事实 ID 列表")
    chunk_ids: List[str] = Field(default_factory=list, description="涉及的 Chunk ID 列表")


class LiteratureMiningRequest(BaseModel):
    """文献挖掘请求"""
    project_id: str = Field(..., description="项目 ID")
    research_question: str = Field(..., description="研究问题")
    top_k: int = Field(10, ge=1, le=30, description="检索的文献片段数量")


class LiteratureMiningResponse(BaseModel):
    """文献挖掘响应"""
    facts: List[ScienceFact] = Field(default_factory=list, description="关键科学事实列表")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="证据列表")
    source_papers: List[str] = Field(default_factory=list, description="来源论文标题列表")
    citation_map: List[CitationMapItem] = Field(default_factory=list, description="引用映射")
    uncertain_points: List[str] = Field(default_factory=list, description="不确定的点")
    warning: Optional[str] = Field(None, description="警告信息（文献库为空 / 无检索结果时）")
    skill_outputs: Dict[str, Any] = Field(default_factory=dict, description="Skill 执行输出")


# ==================== Agent 实现 ====================

class LiteratureMiningAgent:
    """文献挖掘智能体

    工作流程：
      1. 检查项目是否有索引 / 有可用文献
      2. FAISS 检索 → 获取 Top-K 相关 Chunk
      3. 格式化 Chunk（含完整文献元数据）→ 送入 LLM
      4. LLM 输出结构化事实 + 证据 + citation_map
      5. 后校验：fact 必须绑定真实 chunk，补充元数据
    """

    def __init__(self):
        pass

    def mine(
        self,
        project_id: str,
        research_question: str,
        top_k: int = 10,
    ) -> LiteratureMiningResponse:
        """
        从项目文献库挖掘相关科学事实

        Args:
            project_id: 项目 ID
            research_question: 研究问题
            top_k: 检索的文献片段数量

        Returns:
            LiteratureMiningResponse
        """
        try:
            # ── 0. 检查项目是否有可检索文献 ──
            vs = get_vector_store()
            if not vs.has_index(project_id):
                return self._empty_response(
                    warning="当前项目缺少可引用文献，请先上传 PDF 或导入 arXiv/BibTeX 文献。"
                )

            # ── 1. FAISS 检索 ──
            logger.info(f"开始检索文献片段: project_id={project_id}, query='{research_question[:60]}...', top_k={top_k}")
            search_results = search_vector_store(
                project_id=project_id,
                query=research_question,
                top_k=top_k,
            )

            if not search_results:
                return self._empty_response(
                    warning="当前项目缺少可引用文献，请先上传 PDF 或导入 arXiv/BibTeX 文献。"
                )

            # ── 2. 格式化，（含完整元数据）→ 送入 Prompt ──
            formatted_chunks = self._format_chunks(search_results)

            # ── 3. 调用 LLM 提取事实 ──
            logger.info(f"开始提取科学事实，共 {len(search_results)} 个片段")
            result = self._extract_facts(research_question, formatted_chunks, search_results)

            # ── 4. 后校验 + 从 search_results 补全元数据 ──
            response = self._validate_and_normalize(result, search_results)

            # ── 5. 运行关联 Skill ──
            response.skill_outputs = self._run_skills_sync(
                project_id, research_question, top_k, search_results
            )

            logger.info(
                f"文献挖掘完成: {len(response.facts)} 个事实, "
                f"{len(response.citation_map)} 篇引用, "
                f"{len(response.evidence)} 条证据"
            )

            return response

        except Exception as e:
            logger.error(f"文献挖掘异常: {e}", exc_info=True)
            raise

    # ────────── 格式化 ──────────

    def _format_chunks(self, search_results: List[SearchResult]) -> str:
        """
        格式化文献片段为 LLM 可读字符串（含完整引用元数据）
        """
        chunks_text: List[str] = []

        for i, r in enumerate(search_results, 1):
            authors = r.authors or "未知作者"
            year_str = f" ({r.year})" if r.year else ""
            page_str = f" p.{r.page_number}" if r.page_number else ""
            source = r.source_type or "unknown"
            doi = f" DOI: {r.doi}" if r.doi else ""
            ext_id = f" arXiv: {r.external_id}" if r.external_id else ""
            url = f" URL: {r.source_url}" if r.source_url else ""
            fb = " [FALLBACK: 本地缓存文献]" if r.fallback else ""

            chunk_text = (
                f"--- 片段 {i} ---\n"
                f"Chunk ID: {r.chunk_id}\n"
                f"Document ID: {r.document_id}\n"
                f"标题: {r.source_title or '未知'}\n"
                f"作者: {authors}{year_str}\n"
                f"来源: {source}{page_str}{doi}{ext_id}{url}{fb}\n"
                f"相似度: {r.similarity_score:.4f}\n"
                f"原文内容:\n{r.content}"
            )
            chunks_text.append(chunk_text)

        return "\n\n".join(chunks_text)

    # ────────── LLM 提取 ──────────

    def _extract_facts(
        self,
        research_question: str,
        formatted_chunks: str,
        search_results: List[SearchResult],
    ) -> dict:
        """
        构建增强 Prompt → 调用 Qwen → 得到结构化事实
        """
        prompt_loader = get_prompt_loader()

        prompt = prompt_loader.render_template(
            "literature_mining",
            {
                "research_question": research_question,
                "literature_chunks": formatted_chunks,
            },
        )

        # ── Schema example（告诉 LLM 期望的输出格式） ──
        schema_example = {
            "facts": [
                {
                    "fact_id": "fact_001",
                    "content": "事实陈述（简洁归纳）",
                    "fact_text": "事实的详细文本，可包含更多上下文",
                    "source_chunk_id": "chunk_id",
                    "document_id": "document_id",
                    "source_paper_title": "论文标题",
                    "page_number": 1,
                    "quote_text": "从 chunk 原文中引用的原句",
                    "relevance_score": 0.85,
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_001",
                    "fact_id": "fact_001",
                    "text": "证据原文引用",
                    "source_chunk_id": "chunk_id",
                    "document_id": "document_id",
                    "page_number": 1,
                    "relevance_score": 0.80,
                }
            ],
            "source_papers": ["论文标题1", "论文标题2"],
            "citation_map": [
                {
                    "document_id": "document_id",
                    "paper_title": "论文标题",
                    "title": "论文标题",
                    "authors": "作者1, 作者2",
                    "year": 2023,
                    "source_type": "arxiv",
                    "source_url": "https://arxiv.org/abs/xxxx.xxxxx",
                    "doi": "10.xxxx/xxxxx",
                    "external_id": "xxxx.xxxxx",
                    "fact_ids": ["fact_001"],
                    "chunk_ids": ["chunk_id"],
                }
            ],
            "uncertain_points": ["不确定或有争议的点1", "不确定或有争议的点2"],
        }

        return qwen_structured_chat(
            prompt=prompt,
            schema_example=schema_example,
            prompt_version="literature_mining",
        )

    # ────────── 后校验 ──────────

    def _validate_and_normalize(
        self,
        result: dict,
        search_results: List[SearchResult],
    ) -> LiteratureMiningResponse:
        """
        验证 LLM 输出：
          - 确保所有事实都绑定到真实的 chunk
          - 补全 citation_map 元数据（从 search_results 中获取）
          - 过滤掉无法验证的事实
        """
        # 确保必要字段存在
        for field in ["facts", "evidence", "source_papers", "citation_map", "uncertain_points"]:
            if field not in result:
                result[field] = []

        # ── 构建 chunk_id → SearchResult 查找表 ──
        chunk_lookup: Dict[str, SearchResult] = {}
        doc_lookup: Dict[str, SearchResult] = {}
        for sr in search_results:
            if sr.chunk_id:
                chunk_lookup[sr.chunk_id] = sr
            if sr.document_id and sr.document_id not in doc_lookup:
                doc_lookup[sr.document_id] = sr

        # ── 校验 facts ──
        validated_facts: List[dict] = []
        for fact in result.get("facts", []):
            chunk_id = fact.get("source_chunk_id", "")
            if not chunk_id or chunk_id not in chunk_lookup:
                # Fact 必须绑定真实 chunk，否则丢弃
                logger.warning(f"丢弃未绑定真实 chunk 的 fact: {fact.get('fact_id', '?')}")
                continue

            sr = chunk_lookup[chunk_id]
            validated_fact = {
                "fact_id": fact.get("fact_id", f"fact_{len(validated_facts) + 1:03d}"),
                "content": fact.get("content") or fact.get("fact_text") or "",
                "fact_text": fact.get("fact_text") or fact.get("content"),
                "source_chunk_id": chunk_id,
                "document_id": fact.get("document_id") or sr.document_id,
                "source_paper_title": fact.get("source_paper_title") or sr.source_title,
                "page_number": fact.get("page_number") or sr.page_number,
                "quote_text": fact.get("quote_text"),
                "relevance_score": fact.get("relevance_score") or sr.similarity_score,
            }
            validated_facts.append(validated_fact)

        result["facts"] = validated_facts

        # ── 校验 evidence ──
        validated_evidence: List[dict] = []
        for ev in result.get("evidence", []):
            chunk_id = ev.get("source_chunk_id", "")
            if not chunk_id or chunk_id not in chunk_lookup:
                continue
            sr = chunk_lookup[chunk_id]
            validated_evidence.append({
                "evidence_id": ev.get("evidence_id", f"ev_{len(validated_evidence) + 1:03d}"),
                "fact_id": ev.get("fact_id", ""),
                "text": ev.get("text", ""),
                "source_chunk_id": chunk_id,
                "document_id": ev.get("document_id") or sr.document_id,
                "page_number": ev.get("page_number") or sr.page_number,
                "relevance_score": ev.get("relevance_score") or sr.similarity_score,
            })

        result["evidence"] = validated_evidence

        # ── 补全 citation_map 元数据 ──
        enriched_citation_map: List[dict] = []
        for item in result.get("citation_map", []):
            doc_id = item.get("document_id", "")
            if not doc_id:
                continue
            # 从 lookup 表补全元数据
            sr = doc_lookup.get(doc_id)
            enriched = {
                "document_id": doc_id,
                "paper_title": item.get("paper_title") or item.get("title") or (sr.source_title if sr else None),
                "title": item.get("title") or item.get("paper_title") or (sr.source_title if sr else None),
                "authors": item.get("authors") or (sr.authors if sr else None),
                "year": item.get("year") or (sr.year if sr else None),
                "source_type": item.get("source_type") or (sr.source_type if sr else None),
                "source_url": item.get("source_url") or (sr.source_url if sr else None),
                "doi": item.get("doi") or (sr.doi if sr else None),
                "external_id": item.get("external_id") or (sr.external_id if sr else None),
                "fallback": item.get("fallback") or (sr.fallback if sr else False),
                "fact_ids": item.get("fact_ids", []),
                "chunk_ids": item.get("chunk_ids", []),
            }

            # 补充 chunk_ids：如果 fact_ids 里有引用，但 chunk_ids 为空，从 validated_facts 补
            if not enriched["chunk_ids"] and enriched["fact_ids"]:
                chunks_set: set = set()
                for f in validated_facts:
                    if f.get("fact_id") in enriched["fact_ids"]:
                        cid = f.get("source_chunk_id")
                        if cid:
                            chunks_set.add(cid)
                enriched["chunk_ids"] = list(chunks_set)

            enriched_citation_map.append(enriched)

        result["citation_map"] = enriched_citation_map

        # ── 确保 source_papers 包含所有去重标题 ──
        seen_titles = set(result.get("source_papers", []))
        for sr in search_results:
            if sr.source_title and sr.source_title not in seen_titles:
                seen_titles.add(sr.source_title)
                result.setdefault("source_papers", []).append(sr.source_title)

        # ── Pydantic 验证 ──
        return LiteratureMiningResponse(**result)

    # ────────── Skills ──────────

    @staticmethod
    def _run_skills_sync(
        project_id: str,
        research_question: str,
        top_k: int,
        search_results: list,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            outputs = {}
            try:
                pdf_skill = PdfEvidenceExtractionSkill()
                pdf_result = await pdf_skill.run(
                    input_data={
                        "project_id": project_id,
                        "research_question": research_question,
                        "top_k": top_k,
                    },
                    context={"stage": "literature_mining"},
                )
                outputs["pdf_evidence_extraction"] = {
                    "success": pdf_result.success,
                    "data": pdf_result.data,
                    "warnings": pdf_result.warnings,
                    "errors": pdf_result.errors,
                }
            except Exception as e:
                logger.warning(f"PdfEvidenceExtractionSkill 运行失败: {e}")
                outputs["pdf_evidence_extraction"] = {"success": False, "error": str(e)}

            try:
                search_skill = SearchPapersSkill()
                search_result = await search_skill.run(
                    input_data={
                        "research_question": research_question,
                        "keywords": [],
                        "max_results": min(top_k, 30),
                    },
                    context={"stage": "literature_mining"},
                )
                outputs["search_papers"] = {
                    "success": search_result.success,
                    "data": search_result.data,
                    "warnings": search_result.warnings,
                    "errors": search_result.errors,
                }
            except Exception as e:
                logger.warning(f"SearchPapersSkill 运行失败: {e}")
                outputs["search_papers"] = {"success": False, "error": str(e)}

            try:
                linking_skill = MultimodalDataLinkingSkill()
                search_facts = [
                    {
                        "fact_id": r.chunk_id,
                        "content": r.content[:300] if r.content else "",
                        "keywords": [],
                    }
                    for r in (search_results or [])
                ]
                linking_result = await linking_skill.run(
                    input_data={
                        "literature_facts": search_facts,
                        "multimodal_datasets": [],
                        "hypothesis": research_question,
                    },
                    context={"stage": "literature_mining"},
                )
                outputs["multimodal_data_linking"] = {
                    "success": linking_result.success,
                    "data": linking_result.data,
                    "warnings": linking_result.warnings,
                    "errors": linking_result.errors,
                }
            except Exception as e:
                logger.warning(f"MultimodalDataLinkingSkill 运行失败: {e}")
                outputs["multimodal_data_linking"] = {"success": False, "error": str(e)}

            return outputs

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"Skills 运行异常: {e}")
            return {}

    # ────────── 空响应 ──────────

    def _empty_response(self, warning: str = "") -> LiteratureMiningResponse:
        """文献库为空时返回的友好提示"""
        default_warning = "未找到相关文献片段"

        return LiteratureMiningResponse(
            facts=[],
            evidence=[],
            source_papers=[],
            citation_map=[],
            uncertain_points=[],
            warning=warning or default_warning,
        )


# ==================== 单例 ====================

_agent_instance: Optional[LiteratureMiningAgent] = None


def get_literature_mining_agent() -> LiteratureMiningAgent:
    """获取 LiteratureMiningAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LiteratureMiningAgent()
    return _agent_instance