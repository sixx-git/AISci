import os
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Path, Query, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.dataset_service import DatasetService, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_dataset(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 {ext}，支持的格式: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    service = DatasetService(db)
    file_path = service.save_uploaded_file(project_id, file.filename or "unknown", content)

    try:
        dataset = service.create_dataset(
            project_id=project_id,
            filename=file.filename or "unknown",
            file_path=file_path,
            file_size=len(content),
            auto_analyze=True,
        )
        return {"code": 200, "data": service.to_response(dataset), "message": "上传成功，已完成初步分析"}
    except Exception as e:
        logger.error(f"创建数据集记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_datasets(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    service = DatasetService(db)
    datasets = service.get_project_datasets(project_id)
    return {
        "code": 200,
        "data": [service.to_response(ds) for ds in datasets],
        "message": "success",
    }


@router.get("/context")
async def get_data_context(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    """获取项目数据上下文
    返回统一 data_context，包括:
    - dataset_count、available_modalities、datasets
    - field_candidates、target_candidates
    - quality_summary、warnings
    """
    service = DatasetService(db)
    data_context = service.get_project_data_context(project_id)
    return {
        "code": 200,
        "data": data_context,
        "message": "success",
    }


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str = Path(..., description="数据集 ID"),
    db: Session = Depends(get_db),
):
    service = DatasetService(db)
    ds = service.get_dataset_by_id(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return {
        "code": 200,
        "data": service.to_response(ds),
        "message": "success",
    }


@router.post("/{dataset_id}/quality")
async def run_quality_analysis(
    dataset_id: str = Path(..., description="数据集 ID"),
    db: Session = Depends(get_db),
):
    """对单个数据集运行质量分析，返回 quality_report"""
    service = DatasetService(db)
    qa_result = service.run_single_quality_analysis(dataset_id)
    return {
        "code": 200,
        "data": qa_result,
        "message": "success" if qa_result.get("success") else "质量分析失败",
    }


@router.post("/{dataset_id}/preprocess")
async def preprocess_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    service = DatasetService(db)
    dataset = service.run_preprocessing(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return {"code": 200, "data": service.to_response(dataset), "message": "预处理完成"}


@router.put("/{dataset_id}/toggle-hypothesis")
async def toggle_hypothesis_use(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    service = DatasetService(db)
    dataset = service.toggle_hypothesis_use(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return {
        "code": 200,
        "data": service.to_response(dataset),
        "message": f"已{'启用' if dataset.use_for_hypothesis else '禁用'}用于假设生成",
    }


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    service = DatasetService(db)
    success = service.delete_dataset(dataset_id)
    if not success:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return {"code": 200, "data": None, "message": "数据集已删除"}