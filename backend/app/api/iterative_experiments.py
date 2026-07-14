"""迭代实验 API（对齐前端 IterativeExperimentPage / shaxiang 流程）"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import success_response, error_response
from app.services.iterative_experiment_service import get_iterative_experiment_service

router = APIRouter()


class CreateExperimentBody(BaseModel):
    hypothesis: str
    research_goal: Optional[str] = ""
    constraints: List[str] = Field(default_factory=list)
    executor_type: str = "sandbox"
    max_iterations: int = 10


class ReportIdsBody(BaseModel):
    experiment_ids: List[str] = Field(default_factory=list)


class DesignScriptBody(BaseModel):
    data_config: Optional[Dict[str, Any]] = None


class RunModeBody(BaseModel):
    run_mode: str = "smoke_only"


class FeedbackBody(BaseModel):
    feedback: str = ""


@router.get("/projects/{project_id}/iterative-experiments")
async def list_experiments(project_id: str, db: Session = Depends(get_db)):
    svc = get_iterative_experiment_service()
    return success_response(
        {
            "items": svc.list(project_id),
            "report_experiment_ids": svc.get_report_ids(project_id),
        }
    )


@router.post("/projects/{project_id}/iterative-experiments")
async def create_experiment(project_id: str, body: CreateExperimentBody, db: Session = Depends(get_db)):
    try:
        exp = get_iterative_experiment_service().create(project_id, body.model_dump())
        return success_response(exp, message="实验已创建")
    except Exception as e:
        return error_response(str(e), code=400)


@router.get("/iterative-experiments/{experiment_id}")
async def get_experiment(experiment_id: str, project_id: str):
    svc = get_iterative_experiment_service()
    exp = svc.get(project_id, experiment_id)
    if not exp:
        return error_response("实验不存在", code=404)
    return success_response(exp)


@router.delete("/projects/{project_id}/iterative-experiments/{experiment_id}")
async def delete_experiment(project_id: str, experiment_id: str):
    get_iterative_experiment_service().delete(project_id, experiment_id)
    return success_response({"deleted": True})


@router.put("/projects/{project_id}/iterative-experiments/report-selection")
async def set_report_selection(project_id: str, body: ReportIdsBody):
    ids = get_iterative_experiment_service().set_report_ids(project_id, body.experiment_ids)
    return success_response({"report_experiment_ids": ids})


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/toggle-report")
async def toggle_report(project_id: str, experiment_id: str):
    ids = get_iterative_experiment_service().toggle_report(project_id, experiment_id)
    return success_response({"report_experiment_ids": ids})


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/recommend-datasets")
async def recommend_datasets(project_id: str, experiment_id: str, body: FeedbackBody = FeedbackBody()):
    try:
        exp = get_iterative_experiment_service().recommend_datasets(
            project_id, experiment_id, body.feedback or None
        )
        return success_response(exp)
    except Exception as e:
        return error_response(str(e), code=400)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/design-script")
async def design_script(project_id: str, experiment_id: str, body: DesignScriptBody):
    try:
        exp = get_iterative_experiment_service().design_script(
            project_id, experiment_id, body.data_config
        )
        return success_response(exp)
    except Exception as e:
        return error_response(str(e), code=400)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/run-mode")
async def set_run_mode(project_id: str, experiment_id: str, body: RunModeBody):
    try:
        exp = get_iterative_experiment_service().set_run_mode(project_id, experiment_id, body.run_mode)
        return success_response(exp)
    except Exception as e:
        return error_response(str(e), code=400)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/run-iteration")
async def run_iteration(project_id: str, experiment_id: str):
    try:
        record = get_iterative_experiment_service().run_iteration(project_id, experiment_id)
        exp = get_iterative_experiment_service().get(project_id, experiment_id)
        return success_response({"record": record, "experiment": exp})
    except Exception as e:
        return error_response(str(e), code=400)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/run-to-completion")
async def run_to_completion(project_id: str, experiment_id: str):
    try:
        exp = get_iterative_experiment_service().run_to_completion(project_id, experiment_id)
        return success_response(exp)
    except Exception as e:
        return error_response(str(e), code=400)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/feedback")
async def submit_feedback(project_id: str, experiment_id: str, body: FeedbackBody):
    try:
        exp = get_iterative_experiment_service().submit_feedback(
            project_id, experiment_id, body.feedback
        )
        return success_response(exp)
    except Exception as e:
        return error_response(str(e), code=400)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/redesign")
async def redesign(project_id: str, experiment_id: str, body: FeedbackBody):
    try:
        exp = get_iterative_experiment_service().redesign_from_feedback(
            project_id, experiment_id, body.feedback
        )
        return success_response(exp)
    except Exception as e:
        return error_response(str(e), code=400)
