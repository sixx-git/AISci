import logging
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.multimodal_service import MultimodalService, detect_modality
from app.services.dataset_service import DatasetService, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)
router = APIRouter()

MULTIMODAL_EXTENSIONS = SUPPORTED_EXTENSIONS | {".mp3", ".m4a", ".flac", ".ogg", ".aac", ".md", ".webp", ".gif"}


@router.post("/upload")
async def upload_multimodal_asset(
    project_id: str = Form(...),
    research_question: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in MULTIMODAL_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式 {ext}，支持: {', '.join(sorted(MULTIMODAL_EXTENSIONS))}",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    ds_service = DatasetService(db)
    file_path = ds_service.save_uploaded_file(project_id, file.filename or "unknown", content)
    modality = detect_modality(file.filename or "")

    dataset = None
    try:
        dataset = ds_service.create_dataset(
            project_id=project_id,
            filename=file.filename or "unknown",
            file_path=file_path,
            file_size=len(content),
            auto_analyze=True,
        )
    except Exception as exc:
        logger.warning(f"创建 Dataset 记录失败（仍继续多模态解析）: {exc}")

    mm_service = MultimodalService(db)
    asset = mm_service.create_and_parse(
        project_id=project_id,
        file_path=file_path,
        file_name=file.filename or "unknown",
        research_question=research_question,
        dataset_id=dataset.id if dataset else None,
        data_type=dataset.data_type if dataset else None,
    )
    return {
        "code": 200,
        "data": {
            "asset": mm_service.to_response(asset),
            "dataset": ds_service.to_response(dataset) if dataset else None,
        },
        "message": "上传并完成多模态解析",
    }


@router.get("")
async def list_multimodal_assets(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
):
    service = MultimodalService(db)
    assets = service.list_assets(project_id)
    return {
        "code": 200,
        "data": [service.to_response(a) for a in assets],
        "message": "success",
    }


@router.get("/context")
async def get_multimodal_context(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
):
    service = MultimodalService(db)
    return {"code": 200, "data": service.get_multimodal_context(project_id), "message": "success"}


@router.post("/{asset_id}/reparse")
async def reparse_asset(
    asset_id: str,
    research_question: str = Form(""),
    db: Session = Depends(get_db),
):
    service = MultimodalService(db)
    asset = service.reparse_asset(asset_id, research_question)
    if not asset:
        raise HTTPException(status_code=404, detail="资产未找到")
    return {"code": 200, "data": service.to_response(asset), "message": "重新解析完成"}


@router.get("/{asset_id}/file")
async def get_asset_file(asset_id: str, db: Session = Depends(get_db)):
    service = MultimodalService(db)
    asset = service.get_asset(asset_id)
    if not asset or not os.path.exists(asset.file_path):
        raise HTTPException(status_code=404, detail="文件未找到")
    return FileResponse(asset.file_path, filename=asset.file_name)


@router.put("/{asset_id}/toggle-hypothesis")
async def toggle_hypothesis(
    asset_id: str,
    db: Session = Depends(get_db),
):
    service = MultimodalService(db)
    asset = service.toggle_hypothesis(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产未找到")
    return {"code": 200, "data": service.to_response(asset), "message": "已更新"}
