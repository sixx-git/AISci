"""多源数据查找 API"""
import logging
import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.data_finder_service import get_data_finder_service
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
router = APIRouter()


class DataFinderAcquireRequest(BaseModel):
    project_id: str
    research_question: str = ""
    selected_hypothesis: str = ""
    project_mode: Optional[str] = None
    auto_import: bool = False
    acquisition_mode: Optional[str] = Field(
        None, description="dataset_discovery | full；默认读取 project.config.data_acquisition.mode",
    )


class DataFinderSearchRequest(BaseModel):
    project_id: str
    research_question: str = ""
    selected_hypothesis: str = ""
    project_mode: Optional[str] = None


class DataFinderGapEnrichRequest(BaseModel):
    project_id: str
    auto_import: bool = True
    coverage_gap_threshold: Optional[float] = None
    data_spec_gap_threshold: Optional[float] = None
    max_gap_rounds: Optional[int] = Field(None, ge=1, le=4)


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


class FigureReviewRequest(BaseModel):
    project_id: str
    figure_id: str
    action: str = Field(..., description="confirm | confirm_edited | reject")
    edited_rows: Optional[List[dict]] = None
    reviewer_note: str = ""


def _resolve_project_mode(db: Session, project_id: str, override: Optional[str]) -> str:
    if override:
        return override
    project = ProjectService(db).get_project(project_id)
    if project:
        return getattr(project, "project_mode", None) or "general"
    return "general"


@router.post("/acquire")
async def data_finder_acquire(body: DataFinderAcquireRequest, db: Session = Depends(get_db)):
    """数据采集：默认仅检索领域公开数据集；mode=full 时含论文抽取与合并。"""
    try:
        service = get_data_finder_service(db)
        mode = _resolve_project_mode(db, body.project_id, body.project_mode)
        gap_options: dict = {}
        if body.acquisition_mode:
            gap_options["acquisition_mode"] = body.acquisition_mode
        result = await service.run_data_acquisition(
            project_id=body.project_id,
            research_question=body.research_question,
            selected_hypothesis=body.selected_hypothesis,
            project_mode=mode,
            auto_import=body.auto_import,
            gap_options=gap_options or None,
        )
        return {"code": 200, "data": result, "message": "数据采集完成"}
    except Exception as e:
        logger.error(f"data_finder acquire failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def data_finder_search(body: DataFinderSearchRequest, db: Session = Depends(get_db)):
    """按研究问题检索相关领域公开数据集（不抽取 PDF 表格/图表）。"""
    try:
        service = get_data_finder_service(db)
        mode = _resolve_project_mode(db, body.project_id, body.project_mode)
        result = await service.run_dataset_discovery(
            project_id=body.project_id,
            research_question=body.research_question,
            selected_hypothesis=body.selected_hypothesis,
            project_mode=mode,
        )
        return {"code": 200, "data": result, "message": "数据集检索完成"}
    except Exception as e:
        logger.error(f"data_finder search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gap-enrich")
async def data_finder_gap_enrich(body: DataFinderGapEnrichRequest, db: Session = Depends(get_db)):
    """基于 Coverage / DataSpec 缺口触发多轮外部数据补搜。"""
    try:
        service = get_data_finder_service(db)
        run_options = {
            k: v
            for k, v in {
                "coverage_gap_threshold": body.coverage_gap_threshold,
                "data_spec_gap_threshold": body.data_spec_gap_threshold,
                "max_gap_rounds": body.max_gap_rounds,
            }.items()
            if v is not None
        }
        history = await service.run_gap_loop(
            body.project_id,
            auto_import=body.auto_import,
            run_options=run_options or None,
        )
        result = service.load_results(body.project_id)
        return {
            "code": 200,
            "data": {"history": history, "results": result},
            "message": "Gap 补搜完成" if history else "无需补搜",
        }
    except Exception as e:
        logger.error(f"data_finder gap-enrich failed: {e}")
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


@router.get("/external-candidates/manual")
async def list_manual_external_candidates(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    """列出需用户手动下载/上传的外部数据候选。"""
    from app.services.external_candidate_service import list_manual_candidates

    service = get_data_finder_service(db)
    results = service.load_results(project_id) or {}
    manual = list_manual_candidates(results.get("external_candidates"))
    return {"code": 200, "data": {"candidates": manual, "count": len(manual)}, "message": "success"}


@router.post("/external-candidates/upload")
async def upload_external_candidate(
    project_id: str = Form(...),
    candidate_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """用户上传外部数据文件，解析后自动 align + merge。"""
    from app.services.external_candidate_service import get_external_candidate_service

    suffix = os.path.splitext(file.filename or "")[1] or ".csv"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        svc = get_external_candidate_service(db)
        result = await svc.upload_and_merge(
            project_id,
            candidate_id,
            source_path=tmp_path,
            original_filename=file.filename or "upload.csv",
        )
        return {"code": 200, "data": result, "message": "上传成功，已纳入合并 CSV"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("external candidate upload failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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


@router.get("/paper-extraction-stats")
async def paper_extraction_stats(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    from app.services.figure_review_service import get_figure_review_service

    stats = get_figure_review_service(db).get_paper_extraction_stats(project_id)
    return {"code": 200, "data": stats, "message": "success"}


@router.post("/figures/review")
async def review_figure(body: FigureReviewRequest, db: Session = Depends(get_db)):
    from app.services.figure_review_service import get_figure_review_service

    try:
        service = get_figure_review_service(db)
        result = service.review_figure(
            body.project_id,
            body.figure_id,
            action=body.action,
            edited_rows=body.edited_rows,
            reviewer_note=body.reviewer_note,
        )
        return {"code": 200, "data": result, "message": "图表复核已保存"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation/{citation_id}")
async def resolve_data_citation(
    citation_id: str,
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    """按 data_citation_id 追溯 provenance 记录"""
    try:
        service = get_data_finder_service(db)
        record = service.resolve_data_citation(project_id, citation_id)
        if not record:
            raise HTTPException(status_code=404, detail="未找到 data_citation 记录")
        return {"code": 200, "data": record, "message": "追溯成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bundle/download")
async def download_analysis_bundle(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
):
    try:
        service = get_data_finder_service(db)
        zip_path = service.get_bundle_zip_path(project_id)
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"data_finder_bundle_{project_id[:8]}.zip",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
