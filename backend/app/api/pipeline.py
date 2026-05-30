"""
Pipeline API 路由
"""
import logging
import threading
import traceback
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional, Type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal, init_db
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
from app.models.pipeline import PipelineRun, PipelineStageExecution, PipelineStatus as DB_PipelineStatus, PipelineStage as DB_PipelineStage
from app.services.pipeline_service import get_pipeline_service, PipelineService

logger = logging.getLogger(__name__)

CHINA_TZ = timezone(timedelta(hours=8))
STALE_TIMEOUT_MINUTES = 5

PIPELINE_STAGES_ORDERED = [
    PipelineStage.PROBLEM_UNDERSTANDING,
    PipelineStage.LITERATURE_MINING,
    PipelineStage.KNOWLEDGE_GAP,
    PipelineStage.HYPOTHESIS_GENERATION,
    PipelineStage.HYPOTHESIS_REVIEW,
    PipelineStage.EXPERIMENT_DESIGN,
    PipelineStage.SMALL_VALIDATION,
    PipelineStage.REPORT_GENERATION,
]

router = APIRouter()


def _now() -> datetime:
    return datetime.now(CHINA_TZ)


def _safe_enum_value(enum_cls: Type[Enum], value: Any, default: Any = None) -> Any:
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


def _check_and_fail_stale_run(db: Session, run: PipelineRun) -> bool:
    """检测并标记僵尸 run（running 超过 5 分钟但所有 stage 仍为 pending）。

    Returns:
        True 如果 run 已被标记为 stale/failed.
    """
    if run.status != DB_PipelineStatus.RUNNING:
        return False
    if run.created_at is None:
        return False

    age = _now() - run.created_at.replace(tzinfo=CHINA_TZ) if run.created_at.tzinfo is None else _now() - run.created_at
    if age.total_seconds() < STALE_TIMEOUT_MINUTES * 60:
        return False

    stages = db.query(PipelineStageExecution).filter(
        PipelineStageExecution.pipeline_run_id == run.id
    ).all()
    all_pending = all(s.status == DB_PipelineStatus.PENDING for s in stages)

    if not all_pending:
        return False

    run.status = DB_PipelineStatus.FAILED
    run.error_message = "Pipeline 后台任务未启动或已丢失，请重新运行。"
    run.completed_at = _now()
    if stages:
        stages[0].status = DB_PipelineStatus.FAILED
        stages[0].error_message = "后台任务未启动或已丢失"
        stages[0].completed_at = _now()
    db.commit()
    logger.warning(f"Stale run {run.run_id} 已自动标记为 FAILED (age={age.total_seconds():.0f}s)")
    return True


def _fail_project_stale_runs(db: Session, project_id: str):
    """清理项目下所有 stale running run。"""
    stale_runs = db.query(PipelineRun).filter(
        PipelineRun.project_id == project_id,
        PipelineRun.status == DB_PipelineStatus.RUNNING
    ).all()
    for run in stale_runs:
        _check_and_fail_stale_run(db, run)


def _execute_pipeline_background(run_id: str):
    """后台执行 Pipeline（独立线程，独立 DB Session）。"""
    logger.info(f"开始执行 Pipeline run_id={run_id}")
    init_db()
    db = SessionLocal()
    service: Optional[PipelineService] = None
    try:
        service = PipelineService(db)
        service.execute_pipeline_run(run_id)
    except Exception as exc:
        logger.exception(f"Pipeline 后台任务失败 run_id={run_id}: {exc}")
        try:
            run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
            if run:
                run.status = DB_PipelineStatus.FAILED
                run.error_message = str(exc)
                run.error_stacktrace = traceback.format_exc()
                run.completed_at = _now()

                stages = db.query(PipelineStageExecution).filter(
                    PipelineStageExecution.pipeline_run_id == run.id
                ).order_by(PipelineStageExecution.stage_order).all()
                for s in stages:
                    if s.status == DB_PipelineStatus.RUNNING:
                        s.status = DB_PipelineStatus.FAILED
                        s.error_message = str(exc)
                        s.completed_at = _now()
                db.commit()
        except Exception as db_exc:
            logger.exception(f"写入失败状态异常 run_id={run_id}: {db_exc}")
    finally:
        db.close()


@router.post("/run", response_model=ResponseModel[PipelineRunResult])
async def run_pipeline(
    request: PipelineRunRequest,
    db: Session = Depends(get_db)
):
    """异步运行完整的 Pipeline（立即返回，后台执行）。"""
    try:
        _fail_project_stale_runs(db, request.project_id)

        pipeline_service = get_pipeline_service(db)
        run_id = pipeline_service.start_pipeline_async(request)

        threading.Thread(
            target=_execute_pipeline_background,
            args=(run_id,),
            daemon=True
        ).start()

        stages = [
            PipelineStageLog(
                stage=s,
                status=PipelineStageStatus.PENDING
            )
            for s in PIPELINE_STAGES_ORDERED
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


@router.get("/runs/{project_id}", response_model=ResponseModel[list])
async def get_project_runs(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取项目的所有 Pipeline 运行历史。"""
    try:
        _fail_project_stale_runs(db, project_id)

        runs = db.query(PipelineRun).filter(
            PipelineRun.project_id == project_id
        ).order_by(PipelineRun.created_at.desc()).all()

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
    """获取单个 Pipeline 运行的详细信息。"""
    try:
        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()

        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行记录未找到")

        _check_and_fail_stale_run(db, run)

        stages = db.query(PipelineStageExecution).filter(
            PipelineStageExecution.pipeline_run_id == run.id
        ).order_by(PipelineStageExecution.stage_order).all()

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
    """轮询 Pipeline 运行状态（供前端实时更新）。"""
    try:
        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行记录未找到")

        _check_and_fail_stale_run(db, run)

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
                error_message=run.error_message,
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


@router.get("/debug/{run_id}")
async def get_run_debug(
    run_id: str,
    db: Session = Depends(get_db)
):
    """调试接口：返回 Pipeline run 的详细诊断信息。"""
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline 运行记录未找到")

    stages = db.query(PipelineStageExecution).filter(
        PipelineStageExecution.pipeline_run_id == run.id
    ).all()

    status_counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for s in stages:
        sv = s.status.value if hasattr(s.status, "value") else str(s.status)
        if sv in status_counts:
            status_counts[sv] += 1

    all_pending = status_counts["pending"] == len(stages)
    is_stale = False
    hint = None

    if run.status == DB_PipelineStatus.RUNNING and all_pending:
        created_at = run.created_at
        if created_at:
            age = _now() - created_at.replace(tzinfo=CHINA_TZ) if created_at.tzinfo is None else _now() - created_at
            age_seconds = int(age.total_seconds())
            if age_seconds >= STALE_TIMEOUT_MINUTES * 60:
                is_stale = True
                hint = "run.status=running 但所有 stage 长时间 pending，后台任务可能未启动或已丢失"
        else:
            age_seconds = 0
    else:
        age_seconds = int((_now() - run.created_at.replace(tzinfo=CHINA_TZ) if run.created_at and run.created_at.tzinfo is None else (_now() - run.created_at) if run.created_at else timedelta()).total_seconds()) if run.created_at else 0

    return ResponseModel(
        code=200,
        message="获取成功",
        data={
            "run_id": run.run_id,
            "run_status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "age_seconds": age_seconds,
            "stage_count": len(stages),
            "pending_count": status_counts["pending"],
            "running_count": status_counts["running"],
            "completed_count": status_counts["completed"],
            "failed_count": status_counts["failed"],
            "all_pending": all_pending,
            "is_stale": is_stale,
            "hint": hint,
        }
    )