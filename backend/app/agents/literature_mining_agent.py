"""
文献挖掘智能体 (LiteratureMiningAgent)
——基于项目文献库真实检索结果提取事实，提供可引用证据。
"""
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.services.vector_store import (
    search_vector_store,
    SearchResult,
    get_vector_store,
)
from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.skills.literature.pdf_evidence_extraction_skill import PdfEvidenceExtractionSkill
from app.skills.literature.citation_grounding_skill import CitationGroundingSkill
from app.skills.literature.paper_full_text_rag_skill import PaperFullTextRAGSkill
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
    retrieved_papers: List[Dict[str, Any]] = Field(default_factory=list, description="LLM 推荐并校验的论文列表")
    imported_documents: int = Field(0, description="本轮入库的文献文档数")
    literature_search_count: int = Field(0, description="多源检索候选论文数")
    literature_import_count: int = Field(0, description="本轮自动入库论文数")
    literature_selected_count: int = Field(0, description="通过相关性筛选、待入库论文数")
    evidence_facts: int = Field(0, description="从文献中提取的事实数")
    verified_references_count: int = Field(0, description="已验证的引用数")
    candidate_references_count: int = Field(0, description="候选引用数（未导入文献库）")
    retrieval_provenance: Optional[Dict[str, Any]] = Field(None, description="检索→自动入库 provenance")


# ==================== Agent 实现 ====================

class LiteratureMiningAgent:
    """文献挖掘智能体

    工作流程：
      1. LLM 网页式推荐论文（问题 + 领域）→ API 校验 → 自动入库建索引
      2. Zvec 向量检索 → 获取 Top-K 相关 Chunk
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
        db: Optional[Session] = None,
        research_domain: str = "",
    ) -> LiteratureMiningResponse:
        """
        从项目文献库挖掘相关科学事实

        当项目缺少文献或检索无结果时，自动运行 LLM 文献推荐（网页式单次推荐 + API 校验）并导入。

        Args:
            project_id: 项目 ID
            research_question: 研究问题
            top_k: 检索的文献片段数量
            db: 数据库会话（用于自动导入）
            research_domain: 研究领域（来自问题理解，仅传此项给文献推荐）

        Returns:
            LiteratureMiningResponse
        """
        try:
            domain = (research_domain or "").strip()
            keywords = self._domain_keywords(domain)
            discovery_output: Dict[str, Any] = {}
            corpus_meta: Dict[str, Any] = {}

            if db is not None:
                discovery_output, corpus_meta = self._discover_and_import_literature(
                    project_id,
                    research_question,
                    db,
                    research_domain=domain,
                    max_import=self._resolve_max_import(top_k),
                )

            vs = get_vector_store()
            has_index = vs.has_index(project_id)

            if not has_index:
                return self._empty_response(
                    warning=(
                        "当前项目缺少可引用文献，已运行多源文献发现但未获取到有效文献。"
                        "请手动上传 PDF 或导入 BibTeX 文献。"
                    ),
                    discovery_output=discovery_output,
                    corpus_meta=corpus_meta,
                )

            # ── 1. Zvec 向量检索 ──
            logger.info(
                f"开始检索文献片段: project_id={project_id}, "
                f"query='{research_question[:60]}...', top_k={top_k}"
            )
            search_results = search_vector_store(
                project_id=project_id,
                query=research_question,
                top_k=top_k,
            )

            if not search_results:
                fallback_queries: List[str] = []
                for st in discovery_output.get("subtopics") or []:
                    if not isinstance(st, dict):
                        continue
                    for key in ("summary", "label"):
                        text = str(st.get(key) or "").strip()
                        if text:
                            fallback_queries.append(text)
                            break
                for q in discovery_output.get("search_queries") or []:
                    if str(q).strip():
                        fallback_queries.append(str(q).strip())
                for fallback_query in fallback_queries[:3]:
                    logger.info(f"[文献挖掘] 主 query 无结果，尝试子主题 query: {fallback_query[:80]}")
                    search_results = search_vector_store(
                        project_id=project_id,
                        query=fallback_query,
                        top_k=top_k,
                    )
                    if search_results:
                        break

            if not search_results and db is not None:
                logger.info("[文献挖掘] 向量检索仍无结果，二次运行文献推荐")
                discovery_output, corpus_meta = self._discover_and_import_literature(
                    project_id,
                    research_question,
                    db,
                    research_domain=domain,
                    max_import=self._resolve_max_import(top_k),
                )
                if vs.has_index(project_id):
                    search_results = search_vector_store(
                        project_id=project_id,
                        query=research_question,
                        top_k=top_k,
                    )

            if not search_results:
                return self._empty_response(
                    warning=(
                        "已检索并尝试导入外部文献，但未能从文献库中匹配到相关片段。"
                        "请检查研究问题关键词，或手动上传更相关的 PDF。"
                    ),
                    discovery_output=discovery_output,
                    corpus_meta=corpus_meta,
                    retrieved_papers=discovery_output.get("papers") or [],
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
                project_id, research_question, top_k, search_results, keywords=keywords
            )
            response = self._merge_supplementary_facts(response, search_results)

            if discovery_output:
                response.skill_outputs["literature_discovery"] = {
                    "success": True,
                    "data": discovery_output,
                }
            if corpus_meta:
                response.skill_outputs["corpus_auto_import"] = corpus_meta
                if corpus_meta.get("imported", 0) > 0:
                    response.retrieval_provenance = corpus_meta.get("retrieval_provenance")

            if discovery_output.get("papers"):
                response.retrieved_papers = discovery_output["papers"]

            if not response.retrieved_papers:
                discovery_data = (response.skill_outputs.get("literature_discovery") or {}).get("data") or {}
                if isinstance(discovery_data, dict) and discovery_data.get("papers"):
                    response.retrieved_papers = discovery_data["papers"]

            response = self._apply_import_stats(
                response,
                discovery_output=discovery_output,
                corpus_meta=corpus_meta,
            )
            response = self._finalize_literature_stats(response)
            response.evidence_facts = len(response.facts)
            response.verified_references_count = len(response.citation_map)

            if response.literature_search_count:
                stats_msg = (
                    f"检索 {response.literature_search_count} 篇 / "
                    f"入库 {response.literature_import_count} 篇"
                )
                if response.literature_import_count == 0:
                    stats_msg += "（候选未通过相关性筛选或已存在重复）"
                response.warning = (
                    f"{response.warning}; {stats_msg}" if response.warning else stats_msg
                )

            if response.retrieved_papers and not response.citation_map:
                response.warning = (
                    f"当前项目文献不足，自动搜索到 {response.candidate_references_count} "
                    f"篇候选论文，部分可能未导入文献库，不可全部作为 verified references。"
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

    def mine_discovery_refresh(
        self,
        project_id: str,
        research_question: str,
        *,
        refinement_queries: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        previous: Optional[Dict[str, Any]] = None,
        discovery_round: int = 1,
        top_k: int = 15,
        db: Optional[Session] = None,
        research_domain: str = "",
    ) -> LiteratureMiningResponse:
        """Discovery 低分回退：用精炼 query 补充推荐导入、重检索并合并文献事实。"""
        parts = [research_question.strip()]
        for q in refinement_queries or []:
            if q and str(q).strip():
                parts.append(str(q).strip())
        for kw in keywords or []:
            if kw and str(kw).strip():
                parts.append(str(kw).strip())
        search_query = " ".join(dict.fromkeys(parts))[:500]

        logger.info(
            f"[Discovery R{discovery_round}] 文献刷新 search_query='{search_query[:100]}...'"
        )

        prev_fact_count = len((previous or {}).get("facts") or [])
        domain = (research_domain or "").strip()

        discovery_output: Dict[str, Any] = {}
        if db is not None:
            try:
                discovery_output, _ = self._discover_and_import_literature(
                    project_id,
                    search_query,
                    db,
                    research_domain=domain,
                    max_import=self._resolve_max_import(top_k),
                )
            except Exception as exc:
                logger.warning(f"[Discovery R{discovery_round}] 补充文献推荐失败: {exc}")

        vs = get_vector_store()
        if not vs.has_index(project_id):
            if previous:
                merged_empty = self._merge_mining_dicts(
                    previous,
                    self._empty_response(
                        warning="Discovery 刷新：向量索引仍为空，保留上一轮文献结果"
                    ).model_dump(),
                    discovery_round=discovery_round,
                    search_query=search_query,
                    supplementary_import=True,
                )
                return LiteratureMiningResponse(**merged_empty)
            return self._empty_response(warning="Discovery 刷新：项目仍无可检索文献")

        search_results = search_vector_store(
            project_id=project_id,
            query=search_query,
            top_k=top_k,
        )
        if not search_results and search_query != research_question.strip():
            search_results = search_vector_store(
                project_id=project_id,
                query=research_question.strip(),
                top_k=top_k,
            )

        if not search_results:
            if previous:
                merged_empty = self._merge_mining_dicts(
                    previous,
                    self._empty_response(
                        warning="Discovery 刷新未检索到新片段，保留上一轮文献"
                    ).model_dump(),
                    discovery_round=discovery_round,
                    search_query=search_query,
                    supplementary_import=True,
                )
                return LiteratureMiningResponse(**merged_empty)
            return self._empty_response(warning="Discovery 刷新未检索到相关文献片段")

        formatted_chunks = self._format_chunks(search_results)
        result = self._extract_facts(search_query, formatted_chunks, search_results)
        response = self._validate_and_normalize(result, search_results)
        response.skill_outputs = self._run_skills_sync(
            project_id,
            search_query,
            top_k,
            search_results,
            keywords=list(keywords or [])[:8],
        )
        response = self._merge_supplementary_facts(response, search_results)

        if discovery_output.get("papers"):
            response.retrieved_papers = discovery_output["papers"]
            response.candidate_references_count = len(response.retrieved_papers)

        response.evidence_facts = len(response.facts)
        response.verified_references_count = len(response.citation_map)
        if previous:
            response.literature_import_count = int(
                (previous or {}).get("literature_import_count")
                or (previous or {}).get("imported_documents")
                or 0
            )
            response.imported_documents = response.literature_import_count
        response = self._finalize_literature_stats(response)

        fresh_dict = response.model_dump()
        merged_dict = self._merge_mining_dicts(
            previous,
            fresh_dict,
            discovery_round=discovery_round,
            search_query=search_query,
            supplementary_import=True,
        )
        from app.services.literature_bundle_service import enrich_literature_mining

        merged_dict = enrich_literature_mining(merged_dict)
        merged_dict["discovery_refresh"] = {
            **(merged_dict.get("discovery_refresh") or {}),
            "facts_before": prev_fact_count,
            "facts_after": len(merged_dict.get("facts") or []),
            "new_facts": max(0, len(merged_dict.get("facts") or []) - prev_fact_count),
        }
        return LiteratureMiningResponse(**merged_dict)

    @staticmethod
    def _merge_mining_dicts(
        previous: Optional[Dict[str, Any]],
        fresh: Dict[str, Any],
        *,
        discovery_round: int = 0,
        search_query: str = "",
        supplementary_import: bool = False,
    ) -> Dict[str, Any]:
        if not previous:
            out = dict(fresh)
            out["discovery_refresh"] = {
                "round": discovery_round,
                "search_query": search_query,
                "supplementary_arxiv_import": supplementary_import,
                "merged_from_previous": False,
            }
            return out

        def _fact_key(f: dict) -> str:
            return str(f.get("fact_id") or f.get("content") or "")[:120]

        fact_map: Dict[str, dict] = {}
        for f in previous.get("facts") or []:
            if isinstance(f, dict) and _fact_key(f):
                fact_map[_fact_key(f)] = f
        for f in fresh.get("facts") or []:
            if isinstance(f, dict) and _fact_key(f):
                fact_map[_fact_key(f)] = f

        cite_map: Dict[str, dict] = {}
        for c in (previous.get("citation_map") or []) + (fresh.get("citation_map") or []):
            if isinstance(c, dict):
                key = str(c.get("document_id") or c.get("title") or c.get("paper_title") or "")
                if key:
                    cite_map[key] = c

        papers_seen: set = set()
        merged_papers: List[str] = []
        for title in (previous.get("source_papers") or []) + (fresh.get("source_papers") or []):
            t = str(title)
            if t and t not in papers_seen:
                papers_seen.add(t)
                merged_papers.append(t)

        retrieved: Dict[str, dict] = {}
        for p in (previous.get("retrieved_papers") or []) + (fresh.get("retrieved_papers") or []):
            if isinstance(p, dict):
                key = str(p.get("title") or p.get("paper_id") or id(p))
                retrieved[key] = p

        out = dict(fresh)
        out["facts"] = list(fact_map.values())
        out["citation_map"] = list(cite_map.values())
        out["source_papers"] = merged_papers
        out["retrieved_papers"] = list(retrieved.values())
        out["evidence"] = (previous.get("evidence") or []) + [
            e for e in (fresh.get("evidence") or [])
            if e not in (previous.get("evidence") or [])
        ]
        out["uncertain_points"] = list(dict.fromkeys(
            (previous.get("uncertain_points") or []) + (fresh.get("uncertain_points") or [])
        ))
        prev_skills = previous.get("skill_outputs") or {}
        fresh_skills = fresh.get("skill_outputs") or {}
        out["skill_outputs"] = {**prev_skills, **fresh_skills}
        out["discovery_refresh"] = {
            "round": discovery_round,
            "search_query": search_query,
            "supplementary_arxiv_import": supplementary_import,
            "merged_from_previous": True,
            "facts_before": len(previous.get("facts") or []),
            "facts_after": len(out["facts"]),
            "new_facts": max(0, len(out["facts"]) - len(previous.get("facts") or [])),
        }
        if fresh.get("warning"):
            out["warning"] = fresh["warning"]
        return out

    @staticmethod
    def _domain_keywords(research_domain: str) -> List[str]:
        domain = (research_domain or "").strip()
        if not domain:
            return []
        parts = [p.strip() for p in domain.replace("，", ",").replace("、", ",").split(",") if p.strip()]
        return parts[:8]

    def _discover_and_import_literature(
        self,
        project_id: str,
        research_question: str,
        db: Session,
        *,
        research_domain: str = "",
        max_import: int = 8,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """LLM 网页式推荐 → API 校验 → 自动入库建索引。"""
        from app.services.literature_corpus_service import ensure_corpora_from_recommendations
        from app.services.literature_recommendation_service import run_literature_recommendation_sync

        domain = (research_domain or "").strip()
        logger.info(
            f"[文献推荐] 启动 LLM 推荐: project={project_id}, "
            f"question='{research_question[:80]}...', domain='{domain[:60]}'"
        )
        discovery = run_literature_recommendation_sync(research_question, domain)
        corpus_meta = ensure_corpora_from_recommendations(
            project_id,
            research_question,
            discovery,
            db,
            max_import=max_import,
        )
        logger.info(
            f"[文献推荐] 完成: recommended={discovery.get('candidate_count', 0)}, "
            f"verified={discovery.get('verified_count', 0)}, imported={corpus_meta.get('imported', 0)}"
        )
        return discovery, corpus_meta

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
                    "challenge_dimension": "分布偏移",
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

    def _merge_supplementary_facts(
        self,
        response: LiteratureMiningResponse,
        search_results: Optional[List[SearchResult]] = None,
    ) -> LiteratureMiningResponse:
        """合并 Skill 产出与检索 chunk 兜底事实，避免 LLM 校验后 facts 为空。"""
        from app.services.literature_bundle_service import enrich_literature_mining

        merged = enrich_literature_mining(response.model_dump())
        facts = merged.get("facts") or []

        if not facts and search_results:
            fallback_facts: List[dict] = []
            for i, sr in enumerate(search_results[:12], 1):
                content = (sr.content or "").strip()
                if not content or not sr.chunk_id:
                    continue
                fallback_facts.append(
                    {
                        "fact_id": f"chunk_fact_{i:03d}",
                        "content": content[:500],
                        "fact_text": content[:1000],
                        "source_chunk_id": sr.chunk_id,
                        "document_id": sr.document_id,
                        "source_paper_title": sr.source_title,
                        "page_number": sr.page_number,
                        "quote_text": content[:300],
                        "relevance_score": sr.similarity_score,
                        "source": "vector_chunk",
                    }
                )
            if fallback_facts:
                merged["facts"] = fallback_facts
                facts = fallback_facts
                logger.info("LLM 未产出有效 facts，已从向量检索 chunk 生成 %d 条兜底事实", len(fallback_facts))

        payload = {**response.model_dump(), **merged}
        payload["facts"] = facts
        payload["evidence_facts"] = len(facts)
        payload["verified_references_count"] = len(payload.get("citation_map") or [])
        return LiteratureMiningResponse(**payload)

    # ────────── Skills ──────────

    @staticmethod
    def _run_skills_sync(
        project_id: str,
        research_question: str,
        top_k: int,
        search_results: list,
        keywords: Optional[List[str]] = None,
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
                rag_skill = PaperFullTextRAGSkill()
                rag_result = await rag_skill.run(
                    input_data={
                        "project_id": project_id,
                        "research_question": research_question,
                        "query": research_question,
                        "top_k": max(top_k, 8),
                    },
                    context={"stage": "literature_mining", "project_id": project_id},
                )
                outputs["paper_full_text_rag"] = {
                    "success": rag_result.success,
                    "data": rag_result.data,
                    "warnings": rag_result.warnings,
                    "errors": rag_result.errors,
                }
            except Exception as e:
                logger.warning(f"PaperFullTextRAGSkill 运行失败: {e}")
                outputs["paper_full_text_rag"] = {"success": False, "error": str(e)}

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

    @staticmethod
    def _resolve_max_import(top_k: int) -> int:
        from app.core.config import get_settings

        cap = int(getattr(get_settings(), "LITERATURE_IMPORT_MAX", 16) or 16)
        return min(max(top_k, 6), cap)

    @staticmethod
    def _apply_import_stats(
        response: LiteratureMiningResponse,
        *,
        discovery_output: Optional[Dict[str, Any]] = None,
        corpus_meta: Optional[Dict[str, Any]] = None,
    ) -> LiteratureMiningResponse:
        meta = corpus_meta or {}
        discovery = discovery_output or {}
        searched = int(
            meta.get("candidate_count")
            or discovery.get("candidate_count")
            or discovery.get("total")
            or len(discovery.get("papers") or [])
            or 0
        )
        imported = int(meta.get("imported") or 0)
        selected = int(meta.get("selected_count") or 0)

        response.literature_search_count = searched
        response.literature_import_count = imported
        response.literature_selected_count = selected
        response.imported_documents = imported
        if searched:
            response.candidate_references_count = max(response.candidate_references_count or 0, searched)
        return response

    @staticmethod
    def _finalize_literature_stats(response: LiteratureMiningResponse) -> LiteratureMiningResponse:
        searched = int(
            response.literature_search_count
            or response.candidate_references_count
            or len(response.retrieved_papers or [])
            or 0
        )
        if response.retrieved_papers:
            searched = max(searched, len(response.retrieved_papers))

        response.literature_search_count = searched
        response.candidate_references_count = searched
        return response

    # ────────── 空响应 ──────────

    def _empty_response(
        self,
        warning: str = "",
        *,
        discovery_output: Optional[Dict[str, Any]] = None,
        corpus_meta: Optional[Dict[str, Any]] = None,
        retrieved_papers: Optional[List[Dict[str, Any]]] = None,
    ) -> LiteratureMiningResponse:
        """文献库为空时返回的友好提示"""
        default_warning = "未找到相关文献片段"
        skill_outputs: Dict[str, Any] = {}
        if discovery_output:
            skill_outputs["literature_discovery"] = {"success": True, "data": discovery_output}
        if corpus_meta:
            skill_outputs["corpus_auto_import"] = corpus_meta

        resp = LiteratureMiningResponse(
            facts=[],
            evidence=[],
            source_papers=[],
            citation_map=[],
            uncertain_points=[],
            warning=warning or default_warning,
            skill_outputs=skill_outputs,
            retrieved_papers=retrieved_papers or (discovery_output or {}).get("papers") or [],
            candidate_references_count=len(retrieved_papers or (discovery_output or {}).get("papers") or []),
            retrieval_provenance=(corpus_meta or {}).get("retrieval_provenance"),
        )
        return self._apply_import_stats(
            resp,
            discovery_output=discovery_output,
            corpus_meta=corpus_meta,
        )


# ==================== 单例 ====================

_agent_instance: Optional[LiteratureMiningAgent] = None


def get_literature_mining_agent() -> LiteratureMiningAgent:
    """获取 LiteratureMiningAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LiteratureMiningAgent()
    return _agent_instance