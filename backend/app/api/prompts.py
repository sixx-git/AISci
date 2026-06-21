"""Prompt Override API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ResponseModel
from app.schemas.human_loop import PromptOverrideRequest, PromptInfoResponse
from app.services.prompt_override_service import get_prompt_override_service

router = APIRouter()


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
