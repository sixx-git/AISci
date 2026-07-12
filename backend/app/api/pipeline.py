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
from app.schemas.human_loop import RerunFromStageRequest, RerunFromStageResponse
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
    LoopDryRunRequest,
)
from app.models.pipeline import PipelineRun, PipelineStageExecution, PipelineStatus as DB_PipelineStatus, PipelineStage as DB_PipelineStage
from app.services.pipeline_service import get_pipeline_service, PipelineService

logger = logging.getLogger(__name__)


def _human_fields_from_stage(stage: PipelineStageExecution) -> dict:
    meta = stage.extra_metadata if isinstance(stage.extra_metadata, dict) else {}
    history = meta.get("revision_history") or []
    return {
        "extra_metadata": meta or None,
        "human_modified_output": meta.get("human_modified_output"),
        "human_reviewed": bool(meta.get("human_reviewed")),
        "human_feedback": meta.get("human_feedback"),
        "edited_at": meta.get("edited_at"),
        "revision_history": history,
        "chat_history": meta.get("chat_history") or [],
        "human_edited": bool(meta.get("human_edited")),
    }

CHINA_TZ = timezone(timedelta(hours=8))
STALE_TIMEOUT_MINUTES = 5
STALE_STAGE_TIMEOUT_MINUTES = 30
# 轻量阶段（单次 LLM）更短的卡死判定
STALE_STAGE_TIMEOUT_BY_KEY: dict[str, int] = {
    "PROBLEM_UNDERSTANDING": 5,
    # 多源检索 + 建索引 + LLM 抽取，真实 API 下常超过 12 分钟
    "LITERATURE_MINING": 45,
    "DATA_ACQUISITION": 25,
    "KNOWLEDGE_GAP": 15,
    "HYPOTHESIS_GENERATION": 20,
    "HYPOTHESIS_REVIEW": 20,
    "EXPERIMENT_DESIGN": 25,
    "SMALL_VALIDATION": 30,
    "REPORT_GENERATION": 35,
}

PIPELINE_STAGES_ORDERED = [
    PipelineStage.PROBLEM_UNDERSTANDING,
    PipelineStage.LITERATURE_MINING,
    PipelineStage.DATA_ACQUISITION,
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_china(dt: datetime) -> datetime:
    """统一按中国时区比较。SQLite 中 server_default 的 created_at 为 UTC  naive，优先用 started_at。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CHINA_TZ)
    return dt.astimezone(CHINA_TZ)


def _run_reference_time(run: PipelineRun) -> Optional[datetime]:
    """用于计算 run 年龄的参考时间（优先 started_at，避免 created_at UTC 偏差）。"""
    return run.started_at or run.created_at


def _run_age_seconds(run: PipelineRun, now: Optional[datetime] = None) -> float:
    ref = _run_reference_time(run)
    if ref is None:
        return 0.0
    now = now or _now()
    age = (now - _as_china(ref)).total_seconds()
    return abs(age) if age < 0 else age


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


def _stage_stale_timeout_minutes(stage_value: Any) -> int:
    key = stage_value.value if hasattr(stage_value, "value") else str(stage_value)
    return STALE_STAGE_TIMEOUT_BY_KEY.get(key.upper(), STALE_STAGE_TIMEOUT_MINUTES)


_SERVER_BOOT_TIME: Optional[datetime] = None


def set_server_boot_time(dt: datetime) -> None:
    global _SERVER_BOOT_TIME
    _SERVER_BOOT_TIME = dt


def fail_orphaned_pipeline_runs(db: Session, boot_time: Optional[datetime] = None) -> int:
    """服务重启后清理仍为 RUNNING 且启动于本次进程之前的 Pipeline。"""
    from app.models.pipeline import PipelineRun as DBRun, PipelineStageExecution as DBStage
    from app.models.pipeline import PipelineStatus as DBStatus

    boot = boot_time or _SERVER_BOOT_TIME or _now()
    orphans = db.query(DBRun).filter(DBRun.status == DBStatus.RUNNING).all()
    if not orphans:
        return 0

    now = _now()
    msg = "服务重启导致 Pipeline 后台任务中断，请重新运行。"
    count = 0
    for run in orphans:
        started = run.started_at or run.created_at
        if started and _as_china(started) >= boot:
            continue
        run.status = DBStatus.FAILED
        run.error_message = msg
        run.completed_at = now
        stages = db.query(DBStage).filter(DBStage.pipeline_run_id == run.id).all()
        for s in stages:
            if s.status == DBStatus.RUNNING:
                s.status = DBStatus.FAILED
                s.error_message = msg
                s.completed_at = now
            elif s.status == DBStatus.PENDING and not any(
                x.status == DBStatus.COMPLETED for x in stages
            ):
                pass
        if stages and all(s.status == DBStatus.PENDING for s in stages):
            stages[0].status = DBStatus.FAILED
            stages[0].error_message = msg
            stages[0].completed_at = now
        count += 1
        logger.warning("孤儿 Pipeline run 已标记失败 run_id=%s", run.run_id)
    db.commit()
    return count


def _check_and_fail_stale_run(db: Session, run: PipelineRun) -> bool:
    """检测并标记僵尸 run。

    两种情况：
    1. running 超过 5 分钟但所有 stage 仍为 pending → 后台任务未启动
    2. 某 stage running 超过阶段级时限 → 阶段卡死

    Returns:
        True 如果 run 已被标记为 stale/failed.
    """
    if run.status != DB_PipelineStatus.RUNNING:
        return False
    if _run_reference_time(run) is None:
        return False

    now = _now()
    age_seconds = _run_age_seconds(run, now)

    stages = db.query(PipelineStageExecution).filter(
        PipelineStageExecution.pipeline_run_id == run.id
    ).all()

    all_pending = all(s.status == DB_PipelineStatus.PENDING for s in stages)

    if all_pending and age_seconds >= STALE_TIMEOUT_MINUTES * 60:
        run.status = DB_PipelineStatus.FAILED
        run.error_message = "Pipeline 后台任务未启动或已丢失，请重新运行。"
        run.completed_at = _now()
        if stages:
            stages[0].status = DB_PipelineStatus.FAILED
            stages[0].error_message = "后台任务未启动或已丢失"
            stages[0].completed_at = _now()
        db.commit()
        logger.warning(f"Stale run {run.run_id} 已自动标记为 FAILED (all pending, age={age_seconds:.0f}s)")
        return True

    stuck_stage = None
    stuck_limit_min = STALE_STAGE_TIMEOUT_MINUTES
    for s in stages:
        if s.status == DB_PipelineStatus.RUNNING and s.started_at:
            stage_age = (now - _as_china(s.started_at)).total_seconds()
            if stage_age < 0:
                stage_age = abs(stage_age)
            limit_min = _stage_stale_timeout_minutes(s.stage)
            if stage_age >= limit_min * 60:
                stuck_stage = s
                stuck_limit_min = limit_min
                break

    if stuck_stage:
        stage_name = stuck_stage.stage.value if hasattr(stuck_stage.stage, 'value') else str(stuck_stage.stage)
        run.status = DB_PipelineStatus.FAILED
        run.failed_stage = stuck_stage.stage
        run.error_message = f"阶段 {stage_name} 执行超时（超过 {stuck_limit_min} 分钟），进程可能已卡死"
        run.completed_at = _now()
        stuck_stage.status = DB_PipelineStatus.FAILED
        stuck_stage.error_message = f"阶段执行超时（超过 {stuck_limit_min} 分钟）"
        stuck_stage.completed_at = _now()
        db.commit()
        logger.warning(f"Stale run {run.run_id} 已自动标记为 FAILED (stuck stage={stage_name})")
        return True

    return False


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
    import app.core.database as _db
    db = None
    try:
        _db.init_db()
        db = _db.SessionLocal()
        logger.info(f"后台任务 DB Session 已创建 run_id={run_id}")
        service = PipelineService(db)
        service.execute_pipeline_run(run_id)
    except Exception as exc:
        logger.exception(f"Pipeline 后台任务失败 run_id={run_id}: {exc}")
        if db is not None:
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
        if db is not None:
            db.close()


@router.post("/run", response_model=ResponseModel[PipelineRunResult])
async def run_pipeline(
    request: PipelineRunRequest,
    db: Session = Depends(get_db)
):
    """异步运行完整的 Pipeline（立即返回，后台执行）。"""
    logger.info(f"收到 Pipeline 运行请求 project_id={request.project_id} research_question={request.research_question[:80] if request.research_question else '(空)'}")
    try:
        _fail_project_stale_runs(db, request.project_id)

        pipeline_service = get_pipeline_service(db)
        run_id = pipeline_service.start_pipeline_async(request)
        logger.info(f"已创建 PipelineRun run_id={run_id}")

        thread = threading.Thread(
            target=_execute_pipeline_background,
            args=(run_id,),
            daemon=True
        )
        thread.start()
        logger.info(f"后台线程已启动 run_id={run_id} thread={thread.name}")

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
                model_parameters=stage.model_parameters,
                **_human_fields_from_stage(stage),
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
            current_stage=(
                run.current_stage.value
                if hasattr(run.current_stage, "value")
                else str(run.current_stage)
            ) if run.current_stage else None,
            created_at=run.created_at,
            input_data=run.input_data,
            output_data=run.output_data,
            extra_metadata=run.extra_metadata if isinstance(run.extra_metadata, dict) else None,
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
                **_human_fields_from_stage(s),
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
                current_stage=(
                    run.current_stage.value
                    if hasattr(run.current_stage, "value")
                    else str(run.current_stage)
                ) if run.current_stage else None,
                final_report_id=run.final_report_id,
                extra_metadata=run.extra_metadata if isinstance(run.extra_metadata, dict) else None,
                created_at=run.created_at or run.started_at,
                completed_at=run.completed_at,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerun-from-stage", response_model=ResponseModel[RerunFromStageResponse])
async def rerun_from_stage(
    body: RerunFromStageRequest,
    db: Session = Depends(get_db),
):
    """从指定阶段重新运行：默认仅重跑本阶段（保留上下游结果）。"""
    try:
        pipeline_service = get_pipeline_service(db)
        rerun_mode = getattr(body, "rerun_mode", None) or "single_stage"
        new_run_id = pipeline_service.start_rerun_from_stage(
            project_id=body.project_id,
            parent_run_id=body.run_id,
            from_stage=body.stage,
            use_human_modified_output=body.use_human_modified_output,
            rerun_mode=rerun_mode,
            human_feedback=getattr(body, "human_feedback", "") or "",
        )
        thread = threading.Thread(
            target=_execute_pipeline_background,
            args=(new_run_id,),
            daemon=True,
        )
        thread.start()
        msg = (
            f"已仅重跑阶段 {body.stage}"
            if body.rerun_mode == "single_stage"
            else f"已从 {body.stage} 起继续执行后续流程"
        )
        return ResponseModel(
            code=200,
            message=msg,
            data=RerunFromStageResponse(
                run_id=new_run_id,
                parent_run_id=body.run_id,
                rerun_from_stage=body.stage,
                rerun_mode=body.rerun_mode,
                status="running",
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    age_seconds = int(_run_age_seconds(run)) if _run_reference_time(run) else 0

    if run.status == DB_PipelineStatus.RUNNING and all_pending:
        if age_seconds >= STALE_TIMEOUT_MINUTES * 60:
            is_stale = True
            hint = "run.status=running 但所有 stage 长时间 pending，后台任务可能未启动或已丢失"

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


@router.post("/loop-dry-run")
async def loop_dry_run(body: LoopDryRunRequest):
    """模拟 Loop 决策逻辑（停滞 / Gap 阈值 / Teaching 配置），不调用 LLM。"""
    from app.services.loops.dry_run import simulate_loop_decisions

    result = simulate_loop_decisions(
        run_options=body.run_options,
        quality_trend=body.quality_trend,
        round_num=body.round_num,
        hypothesis_review=body.hypothesis_review,
        small_validation=body.small_validation,
        project_mode=body.project_mode,
    )
    return ResponseModel(code=200, message="Dry-run 完成", data=result)


@router.get("/audit-export/{run_id}")
async def export_audit_chain(
    run_id: str,
    db: Session = Depends(get_db),
):
    """导出完整审计链：quality_trend / events / decisions / jsonl 记录"""
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline 运行记录未找到")

    from app.services.audit_chain_service import get_audit_chain_service

    meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
    bundle = get_audit_chain_service().export_audit_bundle(run_id, meta=meta)
    return ResponseModel(code=200, message="导出成功", data=bundle)