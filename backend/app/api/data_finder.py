"""多源数据查找 API"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.data_finder_service import get_data_finder_service
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
router = APIRouter()


class DataFinderSearchRequest(BaseModel):
    project_id: str
    research_question: str = ""
    selected_hypothesis: str = ""
    project_mode: Optional[str] = None


class DataFinderExtractRequest(BaseModel):
    project_id: str
    paper_ids: Optional[List[str]] = None


class DataFinderAlignRequest(BaseModel):
    project_id: str
    table_ids: Optional[List[str]] = None


class DataFinderMergeRequest(BaseModel):
    project_id: str


class DataFinderImportRequest(BaseModel):
    project_id: str
    csv_path: Optional[str] = None
    merge_id: Optional[str] = None


def _resolve_project_mode(db: Session, project_id: str, override: Optional[str]) -> str:
    if override:
        return override
    project = ProjectService(db).get_project(project_id)
    if project:
        return getattr(project, "project_mode", None) or "general"
    return "general"


@router.post("/search")
async def data_finder_search(body: DataFinderSearchRequest, db: Session = Depends(get_db)):
    try:
        service = get_data_finder_service(db)
        mode = _resolve_project_mode(db, body.project_id, body.project_mode)
        result = await service.run_search(
            project_id=body.project_id,
            research_question=body.research_question,
            selected_hypothesis=body.selected_hypothesis,
            project_mode=mode,
        )
        return {"code": 200, "data": result, "message": "数据查找完成"}
    except Exception as e:
        logger.error(f"data_finder search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-tables")
async def data_finder_extract_tables(body: DataFinderExtractRequest, db: Session = Depends(get_db)):
    try:
        service = get_data_finder_service(db)
        result = await service.run_extract_tables(body.project_id, body.paper_ids)
        return {"code": 200, "data": result, "message": "表格抽取完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/align-schema")
async def data_finder_align_schema(body: DataFinderAlignRequest, db: Session = Depends(get_db)):
    try:
        service = get_data_finder_service(db)
        result = await service.run_align_schema(body.project_id, body.table_ids)
        return {"code": 200, "data": result, "message": "字段对齐完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge")
async def data_finder_merge(body: DataFinderMergeRequest, db: Session = Depends(get_db)):
    try:
        service = get_data_finder_service(db)
        result = await service.run_merge(body.project_id)
        return {"code": 200, "data": result, "message": "数据合并完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results")
async def data_finder_results(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    service = get_data_finder_service(db)
    result = service.load_results(project_id)
    return {"code": 200, "data": result, "message": "success" if result else "暂无 data_finder 结果"}


@router.post("/import-to-dataset")
async def data_finder_import_to_dataset(body: DataFinderImportRequest, db: Session = Depends(get_db)):
    try:
        service = get_data_finder_service(db)
        dataset = service.import_to_dataset(body.project_id, body.csv_path, body.merge_id)
        return {"code": 200, "data": dataset, "message": "已加入项目数据集"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
