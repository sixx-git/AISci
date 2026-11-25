"""6G 专题目录、自定义解析和预检记录报告。"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.project_modes import is_emergency_6g_mode
from app.models.project import Project
from app.schemas.common import success_response
from app.services.sixg.parse import parse_custom_task
from app.services.sixg.profile import confirm_custom_parameters, public_profile, save_custom_parse
from app.services.sixg.records import save_precheck_report
from app.services.sixg.topics import list_topics

router = APIRouter()


class CustomParseRequest(BaseModel):
    text: str = Field(..., min_length=1)


class ParameterUpdate(BaseModel):
    name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    confirmed: bool = False


class ParameterConfirmRequest(BaseModel):
    parameters: List[ParameterUpdate]


def _project(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not is_emergency_6g_mode(getattr(project, "project_mode", None)):
        raise HTTPException(status_code=400, detail="当前项目不是 6G 专业应用")
    return project


@router.get("/sixg/topics")
def get_sixg_topics():
    return success_response(data=list_topics(), message="success")


@router.get("/projects/{project_id}/sixg")
def get_sixg_profile(project_id: str, db: Session = Depends(get_db)):
    project = _project(db, project_id)
    return success_response(data=public_profile(project), message="success")


@router.post("/projects/{project_id}/sixg/parse")
def parse_sixg_task(project_id: str, body: CustomParseRequest, db: Session = Depends(get_db)):
    project = _project(db, project_id)
    try:
        parsed = parse_custom_task(body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_custom_parse(project, parsed)
    if not (project.research_question or "").strip():
        project.research_question = body.text.strip()
    db.add(project)
    db.commit()
    db.refresh(project)
    return success_response(data=public_profile(project), message="success")


@router.put("/projects/{project_id}/sixg/parameters")
def update_sixg_parameters(
    project_id: str,
    body: ParameterConfirmRequest,
    db: Session = Depends(get_db),
):
    project = _project(db, project_id)
    confirm_custom_parameters(project, [item.model_dump() for item in body.parameters])
    db.add(project)
    db.commit()
    db.refresh(project)
    return success_response(data=public_profile(project), message="success")


@router.post("/projects/{project_id}/sixg/report")
def create_sixg_record_report(project_id: str, db: Session = Depends(get_db)):
    project = _project(db, project_id)
    report = save_precheck_report(db, project)
    return success_response(
        data={"report_id": report.id, "title": report.title},
        message="已写入研究报告",
    )
