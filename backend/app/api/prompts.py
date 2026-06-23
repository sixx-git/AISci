"""Prompt Override API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.schemas.common import ResponseModel
from app.schemas.human_loop import (
    PromptOverrideRequest,
    PromptInfoResponse,
    PromptPresetCatalogResponse,
    PromptPresetContentResponse,
    PromptPresetApplyRequest,
    PromptPresetApplyResponse,
)
from app.services.prompt_override_service import get_prompt_override_service
from app.services.prompt_preset_service import get_prompt_preset_service

router = APIRouter()


def _resolve_project_mode(db: Session, project_id: str) -> str:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"项目不存在: {project_id}")
    return project.project_mode or "general"


@router.get("/presets/catalog", response_model=ResponseModel[PromptPresetCatalogResponse])
async def get_prompt_preset_catalog(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    try:
        mode = _resolve_project_mode(db, project_id)
        svc = get_prompt_preset_service(db)
        catalog = svc.get_catalog(project_mode=mode)
        return ResponseModel(code=200, message="获取成功", data=PromptPresetCatalogResponse(**catalog))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/presets/{pack_id}/{stage}/{variant_id}",
    response_model=ResponseModel[PromptPresetContentResponse],
)
async def get_prompt_preset_content(
    pack_id: str,
    stage: str,
    variant_id: str,
):
    try:
        svc = get_prompt_preset_service()
        data = svc.get_preset_content(pack_id, stage, variant_id)
        return ResponseModel(code=200, message="获取成功", data=PromptPresetContentResponse(**data))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/presets/apply", response_model=ResponseModel[PromptPresetApplyResponse])
async def apply_prompt_preset(
    body: PromptPresetApplyRequest,
    db: Session = Depends(get_db),
):
    try:
        svc = get_prompt_preset_service(db)
        result = svc.apply_preset(
            body.project_id,
            body.pack_id,
            body.variant_id or "",
            stage=body.stage,
            apply_all_stages=body.apply_all_stages,
        )
        return ResponseModel(code=200, message="范式预设已应用", data=PromptPresetApplyResponse(**result))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{stage}", response_model=ResponseModel[PromptInfoResponse])
async def get_stage_prompt(
    stage: str,
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    try:
        svc = get_prompt_override_service(db)
        info = svc.get_prompt_info(project_id, stage)
        return ResponseModel(code=200, message="获取成功", data=PromptInfoResponse(**info))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{stage}/override", response_model=ResponseModel[PromptInfoResponse])
async def save_stage_prompt_override(
    stage: str,
    body: PromptOverrideRequest,
    db: Session = Depends(get_db),
):
    try:
        svc = get_prompt_override_service(db)
        info = svc.save_override(body.project_id, stage, body.prompt_template)
        return ResponseModel(code=200, message="Prompt 覆盖已保存", data=PromptInfoResponse(**info))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{stage}/override", response_model=ResponseModel[PromptInfoResponse])
async def delete_stage_prompt_override(
    stage: str,
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    try:
        svc = get_prompt_override_service(db)
        info = svc.delete_override(project_id, stage)
        return ResponseModel(code=200, message="已恢复默认 Prompt", data=PromptInfoResponse(**info))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
