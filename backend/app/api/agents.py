"""
智能体 API
"""
import logging
from fastapi import APIRouter, Depends
from typing import Optional, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.response import ApiResponse, success, error
from app.core.database import get_db
from app.agents.problem_understanding_agent import (
    ProblemUnderstandingRequest,
    ProblemUnderstandingResponse,
    get_problem_understanding_agent
)
from app.agents.literature_mining_agent import (
    LiteratureMiningRequest,
    LiteratureMiningResponse,
    get_literature_mining_agent
)
from app.agents.knowledge_gap_agent import (
    KnowledgeGapRequest,
    KnowledgeGapResponse,
    get_knowledge_gap_agent
)
from app.agents.hypothesis_generation_agent import (
    get_hypothesis_generation_agent
)
from app.agents.hypothesis_review_agent import (
    HypothesisCandidate,
    HypothesisReviewRequest,
    HypothesisReviewResult,
    get_hypothesis_review_agent
)
from app.schemas.research import (
    HypothesisGenerationRequest,
    HypothesisGenerationResponse,
    HypothesisResponse,
    EvidenceResponse,
)
from app.services.hypothesis_service import HypothesisService

router = APIRouter(tags=["agents"])


@router.post(
    "/problem-understanding",
    response_model=ApiResponse[ProblemUnderstandingResponse],
    include_in_schema=False,
)
async def problem_understanding(
    request: ProblemUnderstandingRequest
):
    """
    问题理解智能体
    
    输入用户的研究问题和领域描述，输出结构化的问题分析结果。
    强调"明确研究问题、边界定义、避免泛化"。
    """
    try:
        agent = get_problem_understanding_agent()
        
        result = agent.analyze(
            research_question=request.research_question,
            domain_description=request.domain_description
        )
        
        return success(
            result,
            message="问题分析成功"
        )
    except Exception as e:
        return error(str(e))


@router.post(
    "/literature-mining",
    response_model=ApiResponse[LiteratureMiningResponse],
    include_in_schema=False,
)
async def literature_mining(
    request: LiteratureMiningRequest,
    db: Session = Depends(get_db),
):
    """
    文献挖掘智能体
    
    输入项目ID和研究问题，先调用 Zvec 向量检索相关文献片段，再调用 Qwen 提取关键科学事实。
    每条事实必须绑定来源chunk_id、论文标题、页码，禁止无来源事实。
    """
    try:
        agent = get_literature_mining_agent()
        
        result = agent.mine(
            project_id=request.project_id,
            research_question=request.research_question,
            top_k=request.top_k,
            db=db,
        )
        
        return success(
            result,
            message=f"文献挖掘成功，提取 {len(result.facts)} 个科学事实"
        )
    except Exception as e:
        return error(str(e))


@router.post(
    "/knowledge-gap",
    response_model=ApiResponse[KnowledgeGapResponse],
    include_in_schema=False,
)
async def knowledge_gap(
    request: KnowledgeGapRequest
):
    """
    知识缺口智能体
    
    输入文献挖掘智能体输出的 facts 和 uncertain_points，分析当前领域中的矛盾、空白、未验证关系和潜在研究机会。
    每个 gap 都说明依据和可能价值。
    """
    try:
        agent = get_knowledge_gap_agent()
        
        result = agent.analyze(
            facts=request.facts,
            uncertain_points=request.uncertain_points
        )
        
        return success(
            result,
            message=f"知识缺口分析成功，发现 {len(result.knowledge_gaps)} 个知识缺口"
        )
    except Exception as e:
        return error(str(e))


@router.post(
    "/hypothesis-generation",
    response_model=ApiResponse[HypothesisGenerationResponse],
    include_in_schema=False,
)
async def hypothesis_generation(
    request: HypothesisGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    假设生成智能体
    
    输入研究问题、facts、knowledge_gaps、constraints，生成 3-5 条科学假设。
    每条假设包含：hypothesis、rationale、novelty、testability、required_data、possible_method、risk。
    使用归纳推理和演绎推理，避免空泛套话。
    生成的假设将保存到 Hypothesis 表中，并将关联 facts 写入 Evidence 证据链表。
    """
    try:
        agent = get_hypothesis_generation_agent()
        facts = list(request.facts or [])
        # 有 project_id 时合并项目文献库（手动上传 PDF 的摘要/chunk → facts）
        if request.project_id:
            try:
                from app.services.literature_bundle_service import merge_project_library_into_literature_mining

                enriched = merge_project_library_into_literature_mining(
                    {"facts": facts, "citation_map": []},
                    db=db,
                    project_id=request.project_id,
                )
                facts = list(enriched.get("facts") or facts)
            except Exception as merge_err:
                logger.warning("假设生成合并项目文献库失败: %s", merge_err)

        result = agent.generate(
            research_question=request.research_question,
            facts=facts,
            knowledge_gaps=request.knowledge_gaps,
            constraints=request.constraints,
            project_id=request.project_id
        )

        hypotheses_list = [hypo.model_dump() for hypo in result.hypotheses]

        # ── 问题对齐检查 ──
        alignment_results = []
        if request.research_question and hypotheses_list:
            try:
                import asyncio
                from app.skills.reasoning.question_alignment_skill import QuestionAlignmentSkill

                async def _run_alignment():
                    skill = QuestionAlignmentSkill()
                    return await skill.run(
                        input_data={
                            "research_question": request.research_question,
                            "hypotheses": hypotheses_list,
                        },
                        context={"stage": "hypothesis_generation"},
                    )

                skill_result = asyncio.run(_run_alignment())
                alignment_data = skill_result.data
                alignment_results = alignment_data.get("alignments", [])
            except Exception as align_err:
                logger.warning(f"问题对齐检查失败: {align_err}")

        # 为每条假设附上对齐结果
        for i, h in enumerate(hypotheses_list):
            if i < len(alignment_results):
                a = alignment_results[i]
                h["alignment_score"] = a.get("alignment_score")
                h["off_topic"] = a.get("off_topic")
                h["off_topic_reason"] = a.get("off_topic_reason")
                h["matched_keywords"] = a.get("matched_keywords")
                h["missing_keywords"] = a.get("missing_keywords")

        # 保存假设到数据库
        hypothesis_service = HypothesisService(db)
        created_hypotheses = hypothesis_service.create_hypotheses_batch(
            project_id=request.project_id,
            research_question=request.research_question,
            hypotheses_list=hypotheses_list
        )
        
        # 为每条假设创建证据链记录
        for db_hypothesis in created_hypotheses:
            try:
                hypothesis_service.create_evidence_batch(
                    project_id=request.project_id,
                    hypothesis_id=db_hypothesis.id,
                    facts=request.facts
                )
            except Exception as ev_err:
                logger.warning(f"为假设 {db_hypothesis.id} 创建证据链失败: {ev_err}")
        
        return success(
            result,
            message=f"假设生成成功，生成 {len(result.hypotheses)} 条假设"
        )
    except Exception as e:
        return error(str(e))


@router.get("/hypotheses/{project_id}", response_model=ApiResponse[List[HypothesisResponse]])
async def get_project_hypotheses(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    获取项目的假设列表
    """
    try:
        hypothesis_service = HypothesisService(db)
        hypotheses = hypothesis_service.get_hypotheses_by_project(
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset
        )
        if not hypotheses:
            hypotheses = hypothesis_service.materialize_from_latest_pipeline(project_id)
        from app.services.pipeline_output_service import enrich_hypothesis_responses_with_reviews
        responses = [hypothesis_service.to_response(h) for h in hypotheses]
        responses = enrich_hypothesis_responses_with_reviews(db, project_id, responses)

        return success(
            responses,
            message=f"获取假设列表成功，共 {len(responses)} 条"
        )
    except Exception as e:
        return error(str(e))


@router.get("/hypotheses/{hypothesis_id}/evidence", response_model=ApiResponse[List[EvidenceResponse]])
async def get_hypothesis_evidence(
    hypothesis_id: str,
    db: Session = Depends(get_db)
):
    """
    获取假设的证据链
    
    返回某条假设背后的所有文献事实来源，包含：
    - fact_text: 事实陈述
    - quote_text: 原文引用片段
    - source_title: 来源论文/文档标题
    - page_number: 页码
    - relevance_score: 相关度分数
    - document_id / chunk_id: 溯源信息
    """
    try:
        from app.services._utils.pipeline_queries import get_literature_mining_output

        hypothesis_service = HypothesisService(db)
        hypo = hypothesis_service.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            return error("假设不存在", code=404)

        evidences = hypothesis_service.get_evidence_by_hypothesis(hypothesis_id)
        if not evidences:
            literature_mining = get_literature_mining_output(db, hypo.project_id) or {}
            evidences = hypothesis_service.backfill_evidence_from_literature(hypo, literature_mining)
        
        return success(
            evidences,
            message=f"获取证据链成功，共 {len(evidences)} 条"
        )
    except Exception as e:
        return error(str(e))


@router.get("/hypotheses/{hypothesis_id}/evidence-chain")
async def get_hypothesis_evidence_chain(
    hypothesis_id: str,
    db: Session = Depends(get_db),
):
    """获取假设的结构化证据链（支持/反对/修正历史）"""
    try:
        from app.services.evidence_reasoning_service import get_evidence_reasoning_service

        hypo_service = HypothesisService(db)
        hypo = hypo_service.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            return error("假设不存在", code=404)

        er_service = get_evidence_reasoning_service()
        chain = er_service.load_evidence_chain(hypo.project_id, hypothesis_id)
        if not chain:
            from app.services._utils.pipeline_queries import get_literature_mining_output

            literature_mining = get_literature_mining_output(db, hypo.project_id) or {}
            hypo_service.backfill_evidence_from_literature(hypo, literature_mining)
            chain = er_service.load_evidence_chain(hypo.project_id, hypothesis_id)
        if not chain:
            return success(None, message="暂无结构化证据链，请先运行 Pipeline 或迭代修正")

        chain = er_service.refresh_stale_relevance_scores(
            chain,
            hypothesis_text=hypo.hypothesis or "",
            persist_path=er_service._chain_path(hypo.project_id, hypothesis_id),
        )
        return success(chain, message="获取证据链成功")
    except Exception as e:
        return error(str(e))


@router.post("/hypotheses/{hypothesis_id}/evidence-chain/iterate")
async def iterate_hypothesis_evidence_chain(
    hypothesis_id: str,
    db: Session = Depends(get_db),
):
    """对单条假设重新运行证据链迭代验证"""
    try:
        from app.core.json_fields import parse_json_list
        from app.services._utils.pipeline_queries import get_literature_mining_output
        from app.services.evidence_reasoning_service import get_evidence_reasoning_service

        hypo_service = HypothesisService(db)
        hypo = hypo_service.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            return error("假设不存在", code=404)

        literature_mining = get_literature_mining_output(db, hypo.project_id) or {}
        if not literature_mining.get("facts") and not literature_mining.get("citation_map"):
            return error(
                "项目尚无文献挖掘结果，请先运行 Pipeline 的文献挖掘阶段后再迭代修正",
                code=400,
            )

        supporting_ids = list(hypo.supporting_fact_ids or [])
        if isinstance(supporting_ids, str):
            supporting_ids = parse_json_list(supporting_ids) or []

        hypo_dict = {
            "hypothesis": hypo.hypothesis,
            "rationale": hypo.rationale or "",
            "supporting_fact_ids": supporting_ids,
        }

        er_service = get_evidence_reasoning_service()
        # FastAPI 路由已在事件循环内，不可再用 asyncio.run
        output = await er_service.run_for_hypothesis(
            hypo_dict,
            hypo.research_question or "",
            literature_mining,
        )

        chain = output.get("evidence_chain", {})
        if not chain:
            warn = output.get("warnings")
            detail = ("；".join(str(w) for w in warn) if isinstance(warn, list) and warn else "")
            return error(
                detail or "证据链迭代未产出结果，请检查文献挖掘 facts 是否充足",
                code=500,
            )
        er_service.save_evidence_chain(hypo.project_id, hypothesis_id, chain)

        enriched = output.get("hypothesis") or {}
        update_payload: dict = {}
        if enriched.get("hypothesis"):
            update_payload["hypothesis"] = enriched["hypothesis"]
        if enriched.get("supporting_fact_ids") is not None:
            update_payload["supporting_fact_ids"] = enriched["supporting_fact_ids"]
        if enriched.get("evidence_level"):
            update_payload["evidence_level"] = enriched["evidence_level"]
        if update_payload:
            hypo_service.update_hypothesis(hypothesis_id, update_payload)

        facts_for_db = []
        for ev in (chain.get("supporting_evidence") or []) + (chain.get("counter_evidence") or []):
            facts_for_db.append(
                {
                    "fact_text": ev.get("claim") or ev.get("quote_or_summary", ""),
                    "quote_text": ev.get("quote_or_summary", ""),
                    "source_title": ev.get("source_title", ""),
                    "document_id": ev.get("paper_id"),
                    "relevance_score": ev.get("relevance_score", 0.5),
                    "extra_metadata": __import__("json").dumps(
                        {
                            "stance": ev.get("stance"),
                            "stance_reason": ev.get("stance_reason"),
                            "reliability_score": ev.get("reliability_score"),
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        if facts_for_db:
            hypo_service.create_evidence_batch(hypo.project_id, hypothesis_id, facts_for_db)

        return success(
            {"evidence_chain": chain, "hypothesis": enriched},
            message="证据链迭代完成",
        )
    except Exception as e:
        return error(str(e))


@router.get("/hypotheses/{hypothesis_id}/provenance-timeline")
async def get_hypothesis_provenance_timeline(
    hypothesis_id: str,
    db: Session = Depends(get_db),
):
    """假设溯源时间线：facts → 多模态 → 数据集 → verifiable spec"""
    try:
        import json

        from app.core.hypothesis_provenance import build_hypothesis_provenance_timeline
        from app.core.data_citation import collect_citation_ids_from_hypothesis
        from app.core.iterative_science import build_general_verifiable_hypothesis_spec
        from app.core.json_fields import parse_json_list
        from app.models.pipeline import PipelineStatus
        from app.services._utils.pipeline_queries import get_literature_mining_output

        hypo_service = HypothesisService(db)
        hypo = hypo_service.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            return error("假设不存在", code=404)

        literature_mining = get_literature_mining_output(
            db,
            hypo.project_id,
            statuses=[PipelineStatus.COMPLETED],
        )

        row_provenance: list = []
        try:
            from app.services.data_finder_service import get_data_finder_service

            df = get_data_finder_service(db).load_results(hypo.project_id) or {}
            row_provenance = df.get("row_provenance") or []
        except Exception:
            pass

        supporting_fact_ids = parse_json_list(hypo.supporting_fact_ids)
        data_evidence_ids = parse_json_list(hypo.data_evidence_ids)
        dataset_field_refs = parse_json_list(hypo.dataset_field_refs)

        hypo_dict = {
            "hypothesis": hypo.hypothesis,
            "supporting_fact_ids": supporting_fact_ids,
            "data_evidence_ids": data_evidence_ids,
            "dataset_field_refs": dataset_field_refs,
            "data_citation_ids": [],
            "verifiable_spec": build_general_verifiable_hypothesis_spec(
                hypo.hypothesis or "",
                {
                    "supporting_fact_ids": supporting_fact_ids,
                    "dataset_field_refs": dataset_field_refs,
                    "evidence_level": hypo.evidence_level,
                    "validation_target": hypo.validation_target,
                    "expected_measurable_effect": hypo.expected_measurable_effect,
                },
            ),
        }
        hypo_dict["data_citation_ids"] = collect_citation_ids_from_hypothesis(hypo_dict)

        timeline = build_hypothesis_provenance_timeline(
            hypo_dict,
            facts=literature_mining.get("facts") or [],
            multimodal_facts=literature_mining.get("multimodal_evidence") or [],
            row_provenance=row_provenance,
        )
        return success(
            {"hypothesis_id": hypothesis_id, "timeline": timeline},
            message="获取溯源时间线成功",
        )
    except Exception as e:
        return error(str(e))


@router.post(
    "/hypothesis-review",
    response_model=ApiResponse[HypothesisReviewResult],
    include_in_schema=False,
)
async def hypothesis_review(
    request: HypothesisReviewRequest
):
    """
    假设评审智能体
    
    输入候选假设列表，对每条假设从 5 个维度评分：
    - scientific_value (科学价值 0-10分)
    - novelty (创新性 0-10分)
    - testability (可测试性 0-10分)
    - data_availability (数据可用性 0-10分)
    - cost_risk (成本风险 0-10分)
    
    给出修改建议，输出按综合得分排序后的假设列表
    """
    try:
        agent = get_hypothesis_review_agent()
        
        result = agent.review(
            hypotheses=request.hypotheses
        )
        
        return success(
            result,
            message=f"假设评审完成，评审了 {len(result.reviews)} 条假设"
        )
    except Exception as e:
        return error(str(e))

