"""Feedback Hub API"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.feedback_hub_service import get_feedback_hub_service

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackSubmitRequest(BaseModel):
    project_id: str
    source: str = Field("user", description="hitl|kg|data_finder|provenance|literature|user|multimodal")
    message: str
    target: str = Field("hypothesis", description="literature|data_finder|hypothesis|experiment|kg|full")
    payload: Optional[Dict[str, Any]] = None
    trigger_rerun: bool = False


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
