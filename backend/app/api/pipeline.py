"""
Pipeline API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.schemas.pipeline import (
    PipelineRunRequest,
    PipelineRunResult,
    PipelineStatus
)
from app.services.pipeline_service import get_pipeline_service

router = APIRouter()


@router.post("/run", response_model=ResponseModel[PipelineRunResult])
async def run_pipeline(
    request: PipelineRunRequest,
    db: Session = Depends(get_db)
):
    """
    运行完整的 Pipeline
    
    - **project_id**: 项目 ID
    - **research_question**: 研究问题
    
    按顺序执行 8 个阶段：
    1. ProblemUnderstandingAgent
    2. LiteratureMiningAgent
    3. KnowledgeGapAgent
    4. HypothesisGenerationAgent
    5. HypothesisReviewAgent
    6. ExperimentDesignAgent
    7. SmallValidationAgent
    8. ReportGenerationAgent
    
    返回完整的执行日志和结果。
    """
    try:
        pipeline_service = get_pipeline_service(db)
        result = pipeline_service.run_pipeline(request)
        
        if result.status == PipelineStatus.FAILED:
            # 找到失败的阶段
            failed_stage = None
            for stage in result.stages:
                if stage.status == "failed":
                    failed_stage = stage
                    break
            
            error_msg = f"Pipeline 执行失败在阶段: {failed_stage.stage if failed_stage else 'unknown'}"
            if failed_stage and failed_stage.error_message:
                error_msg += f" - 错误信息: {failed_stage.error_message}"
            
            raise HTTPException(status_code=500, detail=error_msg)
        
        return ResponseModel(
            code=200,
            message="Pipeline 执行成功",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline 执行失败: {str(e)}")
