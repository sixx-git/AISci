import os
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Path, Query, Depends, HTTPException, Form, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.project import Project
from app.services.dataset_service import DatasetService, SUPPORTED_EXTENSIONS
from app.services.modeling_service import ModelingService

logger = logging.getLogger(__name__)
router = APIRouter()


class ModelingRunRequest(BaseModel):
    target_column: Optional[str] = Field(None, description="目标变量列名")
    task_type: Optional[str] = Field(
        None,
        description="任务类型: classification / regression / time_series / unknown",
    )
    research_task: Optional[str] = Field(None, description="用户研究任务描述")


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
        from app.services.multimodal_service import get_multimodal_service, detect_modality

        if detect_modality(file.filename or "", dataset.data_type) in ("text", "image", "audio"):
            project = db.query(Project).filter(Project.id == project_id).first()
            rq = (project.research_question if project else "") or ""
            get_multimodal_service(db).sync_from_dataset(dataset, rq)

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


@router.post("/{dataset_id}/modeling/run")
async def run_dataset_modeling(
    dataset_id: str = Path(..., description="数据集 ID"),
    request: Optional[ModelingRunRequest] = Body(default=None),
    db: Session = Depends(get_db),
):
    """运行多源科学数据建模预测与结果自校正流程"""
    req = request or ModelingRunRequest()
    service = ModelingService(db)
    result = await service.run_modeling_pipeline(
        dataset_id=dataset_id,
        target_column=req.target_column,
        task_type=req.task_type,
        research_task=req.research_task,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "建模失败"))
    return {"code": 200, "data": result, "message": "自动建模完成"}


@router.get("/{dataset_id}/modeling/result")
async def get_dataset_modeling_result(
    dataset_id: str = Path(..., description="数据集 ID"),
    db: Session = Depends(get_db),
):
    """获取最近一次建模结果"""
    service = ModelingService(db)
    ds = service.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    result = service.load_result(dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="暂无建模结果，请先运行自动建模")
    return {"code": 200, "data": result, "message": "success"}


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


@router.get("/catalog")
async def get_data_catalog(
    project_id: str = Query(..., description="项目 ID"),
    refresh: bool = Query(False, description="是否重新生成目录"),
    db: Session = Depends(get_db),
):
    from app.services.data_catalog_service import get_data_catalog_service

    service = get_data_catalog_service(db)
    if refresh:
        catalog = service.build_catalog(project_id)
    else:
        catalog = service.load_catalog(project_id) or service.build_catalog(project_id)
    return {"code": 200, "data": catalog, "message": "success"}