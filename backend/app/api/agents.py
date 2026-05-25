"""
智能体 API
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from sqlalchemy.orm import Session

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
from app.schemas.research import (
    HypothesisGenerationRequest,
    HypothesisGenerationResponse,
    HypothesisResponse
)
from app.services.hypothesis_service import HypothesisService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/problem-understanding", response_model=ApiResponse[ProblemUnderstandingResponse])
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


@router.post("/literature-mining", response_model=ApiResponse[LiteratureMiningResponse])
async def literature_mining(
    request: LiteratureMiningRequest
):
    """
    文献挖掘智能体
    
    输入项目ID和研究问题，先调用FAISS检索相关文献片段，再调用Qwen提取关键科学事实。
    每条事实必须绑定来源chunk_id、论文标题、页码，禁止无来源事实。
    """
    try:
        agent = get_literature_mining_agent()
        
        result = agent.mine(
            project_id=request.project_id,
            research_question=request.research_question,
            top_k=request.top_k
        )
        
        return success(
            result,
            message=f"文献挖掘成功，提取 {len(result.facts)} 个科学事实"
        )
    except Exception as e:
        return error(str(e))


@router.post("/knowledge-gap", response_model=ApiResponse[KnowledgeGapResponse])
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


@router.post("/hypothesis-generation", response_model=ApiResponse[HypothesisGenerationResponse])
async def hypothesis_generation(
    request: HypothesisGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    假设生成智能体
    
    输入研究问题、facts、knowledge_gaps、constraints，生成 3-5 条科学假设。
    每条假设包含：hypothesis、rationale、novelty、testability、required_data、possible_method、risk。
    使用归纳推理和演绎推理，避免空泛套话。
    生成的假设将保存到 Hypothesis 表中。
    """
    try:
        # 生成假设
        agent = get_hypothesis_generation_agent()
        result = agent.generate(
            research_question=request.research_question,
            facts=request.facts,
            knowledge_gaps=request.knowledge_gaps,
            constraints=request.constraints,
            project_id=request.project_id
        )
        
        # 保存假设到数据库
        hypothesis_service = HypothesisService(db)
        hypotheses_list = [hypo.model_dump() for hypo in result.hypotheses]
        
        hypothesis_service.create_hypotheses_batch(
            project_id=request.project_id,
            research_question=request.research_question,
            hypotheses_list=hypotheses_list
        )
        
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
        
        return success(
            hypotheses,
            message=f"获取假设列表成功，共 {len(hypotheses)} 条"
        )
    except Exception as e:
        return error(str(e))
