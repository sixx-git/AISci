"""
Pipeline API 路由
"""
import threading
from enum import Enum
from typing import Any, Optional, Type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db, SessionLocal
from app.core.database import init_db as _ensure_db_initialized
from app.schemas.common import ResponseModel
from app.schemas.pipeline import (
    PipelineRunRequest,
    PipelineRunResult,
    PipelineStatus,
    PipelineRunSummary,
    PipelineRunDetail,
    PipelineStageExecutionSummary,
    PipelineStageLog,
    PipelineStageStatus,
    PipelineStage,
)
from app.models.pipeline import PipelineRun, PipelineStageExecution
from app.services.pipeline_service import get_pipeline_service, PipelineService

router = APIRouter()


def _safe_enum_value(enum_cls: Type[Enum], value: Any, default: Any = None) -> Any:
    """安全获取枚举值，兼容旧数据格式。

    - 如果 value 是 enum_cls 类型，直接返回
    - 如果 value 有 .value 属性，提取字符串
    - 如果字符串含点号，取最后一段
    - 统一 lowercase 后通过 value 匹配

    返回枚举成员或 default。
    """
    if value is None:
        return default
    if isinstance(value, enum_cls):
        return value
    if hasattr(value, 'value') and not isinstance(value, str):
        return _safe_enum_value(enum_cls, value.value, default)
    s = str(value)
    if '.' in s:
        s = s.split('.')[-1]
    s_lower = s.lower()
    for member in enum_cls:
        if member.value.lower() == s_lower:
            return member
    try:
        return enum_cls(s)
    except (ValueError, KeyError):
        pass
    return default


@router.post("/run", response_model=ResponseModel[PipelineRunResult])
async def run_pipeline(
    request: PipelineRunRequest,
    db: Session = Depends(get_db)
):
    """
    异步运行完整的 Pipeline（立即返回，后台执行）

    - **project_id**: 项目 ID
    - **research_question**: 研究问题
    - **options**: 可选配置参数

    按顺序执行 8 个阶段：
    1. ProblemUnderstandingAgent
    2. LiteratureMiningAgent
    3. KnowledgeGapAgent
    4. HypothesisGenerationAgent
    5. HypothesisReviewAgent
    6. ExperimentDesignAgent
    7. SmallValidationAgent
    8. ReportGenerationAgent

    立即返回 run_id，前端通过 GET /status/{run_id} 轮询进度。
    """
    try:
        pipeline_service = get_pipeline_service(db)
        run_id = pipeline_service.start_pipeline_async(request)

        def _bg_execute():
            _ensure_db_initialized()
            bg_db = SessionLocal()
            try:
                bg_service = PipelineService(bg_db)
                bg_service.execute_pipeline_run(run_id, request)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error(
                    f"后台 Pipeline 执行失败 run_id={run_id}: {exc}", exc_info=True
                )
            finally:
                bg_db.close()

        threading.Thread(target=_bg_execute, daemon=True).start()

        stages = [
            PipelineStageLog(
                stage=d["stage_enum"],
                status=PipelineStageStatus.PENDING
            )
            for d in [
                {"stage_enum": PipelineStage.PROBLEM_UNDERSTANDING},
                {"stage_enum": PipelineStage.LITERATURE_MINING},
                {"stage_enum": PipelineStage.KNOWLEDGE_GAP},
                {"stage_enum": PipelineStage.HYPOTHESIS_GENERATION},
                {"stage_enum": PipelineStage.HYPOTHESIS_REVIEW},
                {"stage_enum": PipelineStage.EXPERIMENT_DESIGN},
                {"stage_enum": PipelineStage.SMALL_VALIDATION},
                {"stage_enum": PipelineStage.REPORT_GENERATION},
            ]
        ]

        return ResponseModel(
            code=200,
            message="Pipeline 已启动，后台执行中",
            data=PipelineRunResult(
                pipeline_id=run_id,
                run_id=run_id,
                project_id=request.project_id,
                research_question=request.research_question,
                status=PipelineStatus.RUNNING,
                stages=stages,
                created_at=pipeline_service.db_pipeline_run.created_at,
            )
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline 服务异常: {str(e)}")


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
                token_count=stage.token_count,
                model_used=stage.model_used,
                prompt_used=stage.prompt_used,
                model_parameters=stage.model_parameters
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


@router.get("/status/{run_id}", response_model=ResponseModel[PipelineRunResult])
async def get_run_status(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    轮询 Pipeline 运行状态（供前端实时更新）

    - **run_id**: Pipeline 运行 ID
    """
    try:
        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行记录未找到")

        stages = db.query(PipelineStageExecution).filter(
            PipelineStageExecution.pipeline_run_id == run.id
        ).order_by(PipelineStageExecution.stage_order).all()

        stage_logs = [
            PipelineStageLog(
                stage=_safe_enum_value(PipelineStage, s.stage, PipelineStage.PROBLEM_UNDERSTANDING),
                status=_safe_enum_value(PipelineStageStatus, s.status, PipelineStageStatus.PENDING),
                start_time=s.started_at,
                end_time=s.completed_at,
                duration=s.duration_ms / 1000.0 if s.duration_ms else None,
                input_data=s.input_data,
                output_data=s.output_data,
                error_message=s.error_message,
                model_used=s.model_used,
                token_count=s.token_count,
                prompt_used=s.prompt_used,
                model_parameters=s.model_parameters,
            )
            for s in stages
        ]

        total_duration = run.total_duration_ms / 1000.0 if run.total_duration_ms else None

        return ResponseModel(
            code=200,
            message="获取成功",
            data=PipelineRunResult(
                pipeline_id=run.run_id,
                run_id=run.run_id,
                project_id=run.project_id,
                research_question=run.research_question,
                status=_safe_enum_value(PipelineStatus, run.status, PipelineStatus.RUNNING),
                stages=stage_logs,
                total_duration=total_duration,
                failed_stage=run.failed_stage.value if hasattr(run.failed_stage, "value") else str(run.failed_stage) if run.failed_stage else None,
                final_report_id=run.final_report_id,
                created_at=run.created_at or run.started_at,
                completed_at=run.completed_at,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))