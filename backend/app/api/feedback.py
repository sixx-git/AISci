"""Feedback Hub API"""
import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.services.feedback_hub_service import RERUN_TARGETS, get_feedback_hub_service
from app.services.pipeline_service import get_pipeline_service

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackSubmitRequest(BaseModel):
    project_id: str
    source: str = Field("user", description="hitl|kg|data_finder|provenance|literature|user|multimodal")
    message: str
    target: str = Field("hypothesis", description="literature|data_finder|hypothesis|experiment|kg|full")
    payload: Optional[Dict[str, Any]] = None
    trigger_rerun: bool = False
    run_id: Optional[str] = Field(None, description="触发重跑时必填：父 Pipeline run_id")


@router.post("/submit")
async def submit_feedback(body: FeedbackSubmitRequest, db: Session = Depends(get_db)):
    try:
        service = get_feedback_hub_service(db)
        result = service.submit_feedback(
            body.project_id,
            source=body.source,
            message=body.message,
            target=body.target,
            payload=body.payload,
            trigger_rerun=body.trigger_rerun,
        )

        if body.trigger_rerun:
            if not body.run_id:
                raise HTTPException(status_code=400, detail="trigger_rerun 需要 run_id")
            stages = result.get("suggested_rerun_stages") or RERUN_TARGETS.get(body.target, [])
            if not stages:
                raise HTTPException(status_code=400, detail="无法确定重跑起始阶段")
            from_stage = stages[0]
            pipeline_service = get_pipeline_service(db)
            new_run_id = pipeline_service.start_rerun_from_stage(
                project_id=body.project_id,
                parent_run_id=body.run_id,
                from_stage=from_stage,
                use_human_modified_output=True,
                rerun_mode="from_stage_onward",
            )

            def _bg():
                bg_db = SessionLocal()
                try:
                    svc = get_pipeline_service(bg_db)
                    svc.execute_pipeline_run(new_run_id)
                except Exception as exc:
                    logger.exception("Feedback 触发重跑失败: %s", exc)
                finally:
                    bg_db.close()

            threading.Thread(target=_bg, daemon=True).start()
            result["rerun"] = {
                "run_id": new_run_id,
                "parent_run_id": body.run_id,
                "from_stage": from_stage,
                "status": "running",
            }

        return {"code": 200, "data": result, "message": "反馈已记录并注入 global_constraints"}
    except Exception as e:
        logger.error("feedback submit failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/constraints")
async def get_constraints(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
):
    service = get_feedback_hub_service(db)
    constraints = service.get_active_constraints(project_id)
    entries = service.list_entries(project_id)
    return {
        "code": 200,
        "data": {"global_constraints": constraints, "recent_entries": entries[-10:]},
        "message": "success",
    }


@router.get("/entries")
async def list_feedback_entries(
    project_id: str = Query(...),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = get_feedback_hub_service(db)
    entries = service.list_entries(project_id, limit=limit)
    return {"code": 200, "data": entries, "message": "success"}
