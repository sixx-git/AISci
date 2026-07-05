"""科学自迭代 API"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ApiResponse, success, error
from app.schemas.science_iteration import (
    HypothesisProvenanceResponse,
    ScienceIterationSessionResponse,
)
from app.services.science_iteration_service import (
    build_hypothesis_provenance,
    build_session_from_results,
    resolve_science_iteration_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["science-iteration"])


@router.get(
    "/projects/{project_id}/hypotheses/{hypothesis_id}/provenance",
    response_model=ApiResponse[HypothesisProvenanceResponse],
)
async def get_hypothesis_provenance(
    project_id: str,
    hypothesis_id: str,
    run_id: str | None = Query(None, description="可选 Pipeline run_id"),
    db: Session = Depends(get_db),
):
    """假设溯源：来源、文献/数据依据、验证规格。"""
    try:
        pipeline_results = None
        from app.models.pipeline import PipelineRun

        if run_id:
            run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
            if run and isinstance(run.output_data, dict):
                pipeline_results = run.output_data
        else:
            run = (
                db.query(PipelineRun)
                .filter(PipelineRun.project_id == project_id)
                .order_by(PipelineRun.created_at.desc())
                .first()
            )
            if run and isinstance(run.output_data, dict):
                pipeline_results = run.output_data

        prov = build_hypothesis_provenance(
            db, hypothesis_id, pipeline_results=pipeline_results,
        )
        from app.services.hypothesis_service import HypothesisService

        hypo = HypothesisService(db).get_hypothesis_by_id(hypothesis_id)
        if hypo and hypo.project_id != project_id:
            raise HTTPException(status_code=404, detail="假设不属于该项目")
        return success(prov, message="获取假设溯源成功")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_hypothesis_provenance failed")
        return error(str(e))


@router.get(
    "/runs/{run_id}/session",
    response_model=ApiResponse[ScienceIterationSessionResponse],
)
async def get_iteration_session(run_id: str, db: Session = Depends(get_db)):
    """获取 Pipeline 自迭代会话。"""
    try:
        from app.models.pipeline import PipelineRun
        from app.services.project_service import ProjectService

        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        if meta.get("science_iteration"):
            return success(
                ScienceIterationSessionResponse(**meta["science_iteration"]),
                message="获取自迭代会话成功",
            )

        results = run.output_data if isinstance(run.output_data, dict) else {}
        project = ProjectService(db).get_project(run.project_id)
        pcfg = project.config if project and isinstance(project.config, dict) else {}
        cfg = resolve_science_iteration_config(pcfg)
        session = build_session_from_results(
            run.project_id, run_id, results, extra_metadata=meta, config=cfg,
        )
        return success(session, message="获取自迭代会话成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_iteration_session failed")
        return error(str(e))


@router.get("/projects/{project_id}/config")
async def get_iteration_config(project_id: str, db: Session = Depends(get_db)):
    from app.services.project_service import ProjectService

    project = ProjectService(db).get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    pcfg = project.config if isinstance(project.config, dict) else {}
    return success(resolve_science_iteration_config(pcfg).model_dump(), message="ok")
