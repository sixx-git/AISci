"""
Pipeline API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.schemas.pipeline import (
    PipelineRunRequest,
    PipelineRunResult,
    PipelineStatus,
    PipelineRunSummary,
    PipelineRunDetail,
    PipelineStageExecutionSummary
)
from app.models.pipeline import PipelineRun, PipelineStageExecution
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


@router.get("/runs/{project_id}", response_model=ResponseModel[List[PipelineRunSummary]])
async def get_project_runs(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目的所有 Pipeline 运行历史
    
    - **project_id**: 项目 ID
    """
    try:
        runs = db.query(PipelineRun).filter(
            PipelineRun.project_id == project_id
        ).order_by(PipelineRun.created_at.desc()).all()
        
        # 转换为 schema
        run_summaries = [
            PipelineRunSummary(
                id=run.id,
                run_id=run.run_id,
                project_id=run.project_id,
                research_question=run.research_question,
                status=run.status.value if hasattr(run.status, "value") else str(run.status),
                started_at=run.started_at,
                completed_at=run.completed_at,
                total_duration_ms=run.total_duration_ms,
                final_report_id=run.final_report_id,
                failed_stage=run.failed_stage.value if hasattr(run.failed_stage, "value") else str(run.failed_stage) if run.failed_stage else None,
                created_at=run.created_at
            )
            for run in runs
        ]
        
        return ResponseModel(
            code=200,
            message="获取成功",
            data=run_summaries
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Pipeline 运行历史失败: {str(e)}")


@router.get("/run/{run_id}", response_model=ResponseModel[PipelineRunDetail])
async def get_run_detail(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    获取单个 Pipeline 运行的详细信息
    
    - **run_id**: Pipeline 运行 ID
    """
    try:
        # 先查找通过 run_id
        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            # 再尝试通过 id 查找
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行记录未找到")
        
        # 获取所有阶段
        stages = db.query(PipelineStageExecution).filter(
            PipelineStageExecution.pipeline_run_id == run.id
        ).order_by(PipelineStageExecution.stage_order).all()
        
        # 转换阶段
        stage_summaries = [
            PipelineStageExecutionSummary(
                id=stage.id,
                pipeline_run_id=stage.pipeline_run_id,
                stage=stage.stage.value if hasattr(stage.stage, "value") else str(stage.stage),
                stage_order=stage.stage_order,
                status=stage.status.value if hasattr(stage.status, "value") else str(stage.status),
                started_at=stage.started_at,
                completed_at=stage.completed_at,
                duration_ms=stage.duration_ms,
                input_data=stage.input_data,
                output_data=stage.output_data,
                error_message=stage.error_message,
                token_count=stage.token_count
            )
            for stage in stages
        ]
        
        # 转换运行详情
        run_detail = PipelineRunDetail(
            id=run.id,
            run_id=run.run_id,
            project_id=run.project_id,
            research_question=run.research_question,
            status=run.status.value if hasattr(run.status, "value") else str(run.status),
            started_at=run.started_at,
            completed_at=run.completed_at,
            total_duration_ms=run.total_duration_ms,
            final_report_id=run.final_report_id,
            failed_stage=run.failed_stage.value if hasattr(run.failed_stage, "value") else str(run.failed_stage) if run.failed_stage else None,
            created_at=run.created_at,
            input_data=run.input_data,
            output_data=run.output_data,
            stages=stage_summaries
        )
        
        return ResponseModel(
            code=200,
            message="获取成功",
            data=run_detail
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Pipeline 运行详情失败: {str(e)}")
