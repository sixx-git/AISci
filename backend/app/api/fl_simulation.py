"""联邦仿真 API（仅 federated_learning 项目可访问）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.project_modes import is_federated_learning_mode
from app.models.project import Project
from app.schemas.common import success_response
from app.services.fl_simulation.runner import FlSimulationError, get_fl_simulation_runner
from app.services.iterative_experiment_service import get_iterative_experiment_service
from app.core.async_utils import run_blocking

router = APIRouter()


class FlSimConfigPatch(BaseModel):
    backend: Optional[str] = Field(None, description="local_pack | flower | fedml")
    num_clients: Optional[int] = None
    rounds: Optional[int] = None
    strategy: Optional[str] = None
    partition: Optional[str] = None
    timeout_sec: Optional[int] = None
    dirichlet_alpha: Optional[float] = None
    dataset_ref: Optional[str] = None


class FlSimRunBody(BaseModel):
    backend: Optional[str] = None
    num_clients: Optional[int] = None
    rounds: Optional[int] = None
    strategy: Optional[str] = None
    partition: Optional[str] = None
    timeout_sec: Optional[int] = None
    dirichlet_alpha: Optional[float] = None
    dataset_ref: Optional[str] = None


def _err(exc: Exception, default_code: int = 400):
    from app.schemas.common import error_response

    if isinstance(exc, FlSimulationError):
        code = 403 if exc.code == "FL_MODE_REQUIRED" else 400
        return error_response(message=f"{exc.code}: {exc}", code=code)
    if isinstance(exc, PermissionError):
        return error_response(message=str(exc), code=403)
    if isinstance(exc, ValueError):
        return error_response(message=str(exc), code=400)
    return error_response(message=str(exc), code=default_code)


def _get_fl_project(db: Session, project_id: str) -> Project:
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise ValueError("项目不存在")
    if not is_federated_learning_mode(getattr(proj, "project_mode", None)):
        raise FlSimulationError("仅联邦学习（资源包）项目可使用仿真环境")
    return proj


@router.get("/projects/{project_id}/fl-simulation/capabilities")
async def fl_sim_capabilities(project_id: str, db: Session = Depends(get_db)):
    try:
        def _work():
            proj = _get_fl_project(db, project_id)
            return get_fl_simulation_runner().capabilities(
                project_mode=getattr(proj, "project_mode", None)
            )

        data = await run_blocking(_work)
        return success_response(data)
    except Exception as e:
        return _err(e)


@router.get("/projects/{project_id}/fl-simulation/config")
async def get_fl_sim_config(project_id: str, db: Session = Depends(get_db)):
    try:
        def _work():
            proj = _get_fl_project(db, project_id)
            cfg = (proj.config or {}) if isinstance(proj.config, dict) else {}
            sim = cfg.get("fl_simulation")
            if not isinstance(sim, dict):
                sim = get_fl_simulation_runner().build_config_blob()
            return sim

        data = await run_blocking(_work)
        return success_response(data)
    except Exception as e:
        return _err(e)


@router.patch("/projects/{project_id}/fl-simulation/config")
async def patch_fl_sim_config(
    project_id: str,
    body: FlSimConfigPatch,
    db: Session = Depends(get_db),
):
    try:
        def _work():
            proj = _get_fl_project(db, project_id)
            cfg = dict(proj.config or {}) if isinstance(proj.config, dict) else {}
            existing = cfg.get("fl_simulation") if isinstance(cfg.get("fl_simulation"), dict) else {}
            overrides: Dict[str, Any] = {}
            payload = body.model_dump(exclude_none=True)
            backend = payload.pop("backend", None) or existing.get("backend")
            overrides.update(existing.get("spec") or {})
            overrides.update(payload)
            sim = get_fl_simulation_runner().build_config_blob(
                backend=backend,
                spec_overrides=overrides,
            )
            cfg["fl_simulation"] = sim
            proj.config = cfg
            db.add(proj)
            db.commit()
            db.refresh(proj)
            return sim

        data = await run_blocking(_work)
        return success_response(data, message="仿真配置已更新")
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/experiments/{experiment_id}/fl-simulation/run")
async def run_fl_simulation(
    project_id: str,
    experiment_id: str,
    body: FlSimRunBody = FlSimRunBody(),
    db: Session = Depends(get_db),
):
    try:
        def _work():
            proj = _get_fl_project(db, project_id)
            return get_iterative_experiment_service().run_fl_simulation(
                project_id,
                experiment_id,
                project_mode=getattr(proj, "project_mode", None),
                project_config=proj.config if isinstance(proj.config, dict) else {},
                spec_overrides=body.model_dump(exclude_none=True),
            )

        data = await run_blocking(_work)
        return success_response(data, message="仿真已完成")
    except Exception as e:
        return _err(e)


@router.get("/projects/{project_id}/experiments/{experiment_id}/fl-simulation/latest")
async def latest_fl_simulation(
    project_id: str,
    experiment_id: str,
    db: Session = Depends(get_db),
):
    try:
        def _work():
            _get_fl_project(db, project_id)
            return get_iterative_experiment_service().get_fl_simulation_latest(
                project_id, experiment_id
            )

        data = await run_blocking(_work)
        return success_response(data)
    except Exception as e:
        return _err(e)
