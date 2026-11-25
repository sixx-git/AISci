"""6G 应急通信方案预检 API。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import success_response
from app.services.emergency_comm.service import EmergencyCommError, EmergencyCommService

router = APIRouter()


class ScenarioPatch(BaseModel):
    location: Optional[str] = None
    disaster: Optional[str] = None
    terminals: Optional[int] = Field(None, ge=1)
    priority_terminals: Optional[int] = Field(None, ge=0)
    demand_mbps_per_terminal: Optional[float] = Field(None, gt=0)
    satellite_backhaul_mbps: Optional[float] = Field(None, ge=0)
    ground_backhaul_mbps: Optional[float] = Field(None, ge=0)
    uav_count: Optional[int] = Field(None, ge=0)
    uav_endurance_min: Optional[int] = Field(None, ge=0)
    mission_duration_min: Optional[int] = Field(None, ge=1)


def _service(db: Session) -> EmergencyCommService:
    return EmergencyCommService(db)


def _run(action):
    try:
        return success_response(data=action(), message="success")
    except EmergencyCommError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/projects/{project_id}/emergency-comm")
def get_emergency_comm(
    project_id: str,
    db: Session = Depends(get_db),
):
    return _run(lambda: _service(db).ensure(project_id))


@router.put("/projects/{project_id}/emergency-comm/scenario")
def update_emergency_scenario(
    project_id: str,
    body: ScenarioPatch,
    db: Session = Depends(get_db),
):
    patch = body.model_dump(exclude_none=True)
    return _run(lambda: _service(db).update_scenario(project_id, patch))


@router.post("/projects/{project_id}/emergency-comm/suggestions/{suggestion_id}/confirm")
def confirm_emergency_suggestion(
    project_id: str,
    suggestion_id: str,
    db: Session = Depends(get_db),
):
    return _run(lambda: _service(db).confirm(project_id, suggestion_id))
