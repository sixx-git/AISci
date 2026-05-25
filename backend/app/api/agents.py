"""
智能体 API
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.core.response import ApiResponse, success, error
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
