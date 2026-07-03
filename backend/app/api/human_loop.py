"""人在回路 API — 阶段编辑、重跑、导师评审、多轮修改"""
import asyncio
import logging
import threading
import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.schemas.common import ResponseModel
from app.schemas.human_loop import (
    StageHumanEditRequest,
    StageHumanEditResponse,
    RerunFromStageRequest,
    RerunFromStageResponse,
    StageChatRequest,
    StageChatResponse,
    MentorReviewRequest,
    MentorReviewResponse,
    ReportReviseRequest,
    HitlGateResumeRequest,
    HitlGateStatusResponse,
    HitlGateResumeResponse,
)
from app.services.stage_human_loop_service import (
    StageHumanLoopService,
    get_stage_meta,
    get_stage_human_loop_service,
)
from app.services.stage_chat_service import get_stage_chat_service
from app.services.pipeline_service import get_pipeline_service
from app.skills.mentor_review_skill import MentorReviewSkill
from app.models.pipeline import PipelineRun

logger = logging.getLogger(__name__)
router = APIRouter()


def _stage_edit_response(stage_exec) -> StageHumanEditResponse:
    meta = get_stage_meta(stage_exec)
    return StageHumanEditResponse(
        run_id="",
        stage=stage_exec.stage.value if hasattr(stage_exec.stage, "value") else str(stage_exec.stage),
        human_modified_output=meta.get("human_modified_output"),
        human_reviewed=bool(meta.get("human_reviewed")),
        human_feedback=meta.get("human_feedback"),
        edited_at=meta.get("edited_at"),
        revision_history=meta.get("revision_history") or [],
    )


@router.get("/stage/{run_id}/{stage}", response_model=ResponseModel[dict])
async def get_stage_human_detail(
    run_id: str,
    stage: str,
    db: Session = Depends(get_db),
):
    try:
        svc = get_stage_human_loop_service(db)
        return ResponseModel(code=200, message="获取成功", data=svc.get_stage_detail(run_id, stage))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/stage-output/save", response_model=ResponseModel[StageHumanEditResponse])
async def save_stage_human_output(
    body: StageHumanEditRequest,
    db: Session = Depends(get_db),
):
    try:
        svc = get_stage_human_loop_service(db)
        stage_exec = svc.save_human_edit(
            run_id=body.run_id,
            stage=body.stage,
            output_data=body.output_data,
            human_feedback=body.human_feedback,
            mark_reviewed=body.mark_reviewed,
        )
        resp = _stage_edit_response(stage_exec)
        resp.run_id = body.run_id
        return ResponseModel(code=200, message="人工修改已保存", data=resp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerun-from-stage", response_model=ResponseModel[RerunFromStageResponse])
async def rerun_from_stage(
    body: RerunFromStageRequest,
    db: Session = Depends(get_db),
):
    try:
        pipeline_service = get_pipeline_service(db)
        new_run_id = pipeline_service.start_rerun_from_stage(
            project_id=body.project_id,
            parent_run_id=body.run_id,
            from_stage=body.stage,
            use_human_modified_output=body.use_human_modified_output,
            rerun_mode=body.rerun_mode,
        )

        def _bg():
            bg_db = SessionLocal()
            try:
                svc = get_pipeline_service(bg_db)
                svc.execute_pipeline_run(new_run_id)
            except Exception as exc:
                logger.exception(f"Rerun 后台失败: {exc}")
            finally:
                bg_db.close()

        threading.Thread(target=_bg, daemon=True).start()

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


@router.post("/stage-chat", response_model=ResponseModel[StageChatResponse])
async def stage_chat(body: StageChatRequest, db: Session = Depends(get_db)):
    try:
        svc = get_stage_chat_service(db)
        result = svc.chat(
            run_id=body.run_id,
            stage=body.stage,
            user_message=body.message,
            apply_change=body.apply_change,
        )
        return ResponseModel(code=200, message="阶段对话完成", data=StageChatResponse(**result))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mentor-review", response_model=ResponseModel[MentorReviewResponse])
async def mentor_review(body: MentorReviewRequest, db: Session = Depends(get_db)):
    try:
        content = body.content
        research_question = body.research_question
        if body.report_id and not content:
            from app.core.report_fields import report_orm_to_dict
            from app.models.project import Report

            report = (
                db.query(Report)
                .filter(Report.id == body.report_id, Report.project_id == body.project_id)
                .first()
            )
            if not report:
                raise HTTPException(status_code=404, detail="报告未找到")
            content = report_orm_to_dict(report)
        if body.run_id and body.stage and not content:
            detail = get_stage_human_loop_service(db).get_stage_detail(body.run_id, body.stage)
            content = detail.get("human_modified_output") or detail.get("output_data") or {}
            run = db.query(PipelineRun).filter(PipelineRun.run_id == body.run_id).first()
            if run and not research_question:
                research_question = run.research_question or ""

        skill = MentorReviewSkill()
        result = await skill.run(
            {
                "target_type": body.target_type,
                "content": content or {},
                "research_question": research_question,
                "user_notes": body.user_notes,
            },
            {},
        )
        if not result.success:
            raise HTTPException(status_code=500, detail="导师评审失败")
        return ResponseModel(
            code=200,
            message="导师评审完成",
            data=MentorReviewResponse(**result.data),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gate/{run_id}", response_model=ResponseModel[HitlGateStatusResponse])
async def get_hitl_gate_status(run_id: str, db: Session = Depends(get_db)):
    try:
        svc = get_stage_human_loop_service(db)
        data = svc.get_hitl_gate_status(run_id)
        return ResponseModel(code=200, message="获取成功", data=HitlGateStatusResponse(**data))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/gate/resume", response_model=ResponseModel[HitlGateResumeResponse])
async def resume_hitl_gate(body: HitlGateResumeRequest, db: Session = Depends(get_db)):
    try:
        hl_svc = get_stage_human_loop_service(db)
        result = hl_svc.resume_hitl_gate(
            run_id=body.run_id,
            action=body.action,
            human_feedback=body.human_feedback,
            inject_feedback=body.inject_feedback,
        )

        if result["action"] == "continue":
            from app.api.pipeline import _execute_pipeline_background

            threading.Thread(
                target=_execute_pipeline_background,
                args=(body.run_id,),
                daemon=True,
            ).start()

        elif result["action"] == "rerun":
            pipeline_service = get_pipeline_service(db)
            stage = result.get("rerun_from_stage") or "hypothesis_review"
            new_run_id = pipeline_service.start_rerun_from_stage(
                project_id=body.project_id,
                parent_run_id=body.run_id,
                from_stage=stage,
                use_human_modified_output=True,
                rerun_mode="from_stage_onward",
            )
            result["run_id"] = new_run_id

            def _bg_rerun():
                from app.api.pipeline import _execute_pipeline_background
                _execute_pipeline_background(new_run_id)

            threading.Thread(target=_bg_rerun, daemon=True).start()

        return ResponseModel(
            code=200,
            message=f"HITL Gate: {result['action']}",
            data=HitlGateResumeResponse(**result),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
