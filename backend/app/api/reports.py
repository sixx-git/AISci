"""
报告 API
"""
import os
import json
from datetime import datetime, time
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.response import ApiResponse, success, error
from app.core.config import get_settings
from app.core.database import get_db
from app.agents.report_generation_agent import (
    get_report_generation_agent
)
from app.schemas.research import (
    ReportGenerationRequest,
    ReportGenerationResponse,
    ReportCreate,
    ReportDBResponse,
    ReportBrowseItem,
)
from app.schemas.common import PaginatedResponse, PageInfo
from app.schemas.human_loop import ReportReviseRequest
from app.services.report_service import ReportService, merge_report_extra_metadata, enrich_report_for_response, report_to_db_response
from app.services.stage_chat_service import get_stage_chat_service

router = APIRouter(tags=["reports"])


def _safe_report_download_filename(title: Optional[str], ext: str, fallback: str = "科学假设与研究计划") -> str:
    import re

    base = (title or fallback).strip()
    base = re.sub(r'[\\/:*?"<>|]', "_", base)
    base = re.sub(r"\s+", " ", base)[:100].strip() or fallback
    return f"{base}.{ext.lstrip('.')}"
settings = get_settings()


def get_download_url(report_id: str, file_type: str) -> str:
    """
    获取下载地址
    
    Args:
        report_id: 报告 ID
        file_type: 文件类型 (pdf / tex)
        
    Returns:
        下载地址
    """
    base_url = getattr(settings, "API_BASE_URL", "http://localhost:8000")
    return f"{base_url}/api/v1/reports/download/{report_id}/{file_type}"


@router.post("/generate", response_model=ApiResponse[ReportGenerationResponse])
async def generate_report(
    request: ReportGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    生成《科学假设与研究计划》报告
    
    输入项目基本信息、问题理解结果、文献事实、知识缺口、最终假设、实验设计、小样验证结果，
    生成 Markdown 格式报告，包含所有必需章节，参考文献来自 Document 表和 citation_map。
    """
    try:
        agent = get_report_generation_agent()
        
        # 生成报告
        report_result = agent.generate_report(
            project_info=request.project_info,
            problem_understanding=request.problem_understanding,
            literature_facts=request.literature_facts,
            citation_map=request.citation_map,
            knowledge_gaps=request.knowledge_gaps,
            final_hypothesis=request.final_hypothesis,
            experiment_design=request.experiment_design,
            small_validation=request.small_validation
        )
        
        # 获取报告 ID
        report_file_id = report_result.get("report_id")
        pdf_success = report_result.get("pdf_success", False)
        
        # 构建下载地址
        pdf_download_url = get_download_url(report_file_id, "pdf") if report_file_id and pdf_success else None
        tex_download_url = get_download_url(report_file_id, "tex") if report_file_id else None
        
        # 更新结果包含下载地址
        report_result["pdf_download_url"] = pdf_download_url
        report_result["tex_download_url"] = tex_download_url
        
        # 保存到数据库
        report_service = ReportService(db)
        
        # 准备创建数据
        chapters = report_result.get("chapters", {})
        report_create = ReportCreate(
            project_id=request.project_id,
            hypothesis_id=request.final_hypothesis.get("id") if isinstance(request.final_hypothesis, dict) else None,
            experiment_design_id=request.experiment_design.get("id") if isinstance(request.experiment_design, dict) else None,
            small_validation_id=request.small_validation.get("id") if isinstance(request.small_validation, dict) else None,
            title=report_result.get("title", "科学假设与研究计划"),
            paper_title=report_result.get("paper_title", "研究报告"),
            paper_abstract=report_result.get("paper_abstract", ""),
            markdown_content="",
            problem_statement=chapters.get("problem_statement", ""),
            rationale=chapters.get("rationale", ""),
            technical_details=chapters.get("technical_details", ""),
            datasets=chapters.get("datasets", ""),
            source=chapters.get("source", ""),
            target=chapters.get("target", ""),
            methods=chapters.get("methods", ""),
            experiments=chapters.get("experiments", ""),
            results=chapters.get("results", ""),
            references=json.dumps(chapters.get("references", []), ensure_ascii=False),
            report_id=report_file_id,
            pdf_generated=pdf_success,
            status="generated",
            version=1,
            extra_metadata=merge_report_extra_metadata(
                report_result.get("compliance_check"),
                report_result,
            )
        )
        
        db_report = report_service.create_report(report_create)
        
        # 构建响应
        response = ReportGenerationResponse(
            report=report_result,
            summary=f"报告生成成功，报告 ID: {db_report.id}"
        )
        
        return success(
            response,
            message="研究报告生成完成"
        )
    except Exception as e:
        return error(str(e))


@router.get("/download/{report_id}/{file_type}")
async def download_report_file(report_id: str, file_type: str, db: Session = Depends(get_db)):
    """
    下载报告文件
    
    Args:
        report_id: 报告文件 ID（支持 DB UUID 或文件目录名）
        file_type: 文件类型 (pdf / tex)
    """
    try:
        from app.models.project import Report as ReportModel

        db_report = None
        resolved_report_id = report_id
        if "-" in report_id and len(report_id) > 20:
            db_report = db.query(ReportModel).filter(ReportModel.id == report_id).first()
            if db_report and db_report.pdf_path:
                resolved_report_id = db_report.pdf_path

        report_title = None
        if db_report:
            report_title = db_report.paper_title or db_report.title

        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "reports")
        report_dir = os.path.join(reports_dir, resolved_report_id)
        
        if file_type == "pdf":
            file_path = os.path.join(report_dir, "report.pdf")
            filename = _safe_report_download_filename(report_title, "pdf")
            media_type = "application/pdf"
        elif file_type == "tex":
            file_path = os.path.join(report_dir, "report.tex")
            filename = _safe_report_download_filename(report_title, "tex")
            media_type = "application/x-tex"
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return FileResponse(
            file_path,
            filename=filename,
            media_type=media_type
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest/{project_id}", response_model=ApiResponse[Optional[ReportDBResponse]])
async def get_latest_report(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目最新的研究报告
    """
    try:
        report_service = ReportService(db)
        report = report_service.get_latest_report_by_project(project_id)
        
        return success(
            enrich_report_for_response(report, db) if report else None,
            message="获取最新研究报告成功" if report else "暂无研究报告"
        )
    except Exception as e:
        return error(str(e))


@router.get("/detail/{report_id}", response_model=ApiResponse[Optional[ReportDBResponse]])
async def get_report_detail(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    获取研究报告详情
    """
    try:
        report_service = ReportService(db)
        report = report_service.get_report_by_id(report_id)
        
        return success(
            enrich_report_for_response(report, db) if report else None,
            message="获取研究报告详情成功" if report else "报告不存在"
        )
    except Exception as e:
        return error(str(e))


def _parse_filter_date(value: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        if "T" in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt
        parsed = datetime.strptime(raw[:10], "%Y-%m-%d")
        if end_of_day:
            return datetime.combine(parsed.date(), time(23, 59, 59))
        return datetime.combine(parsed.date(), time.min)
    except ValueError:
        return None


@router.get("/browse", response_model=ApiResponse[PaginatedResponse[ReportBrowseItem]])
async def browse_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    project_mode: Optional[str] = Query(
        None,
        description="项目模式: general",
    ),
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    keyword: Optional[str] = Query(None, description="标题/项目名/研究问题关键词"),
    db: Session = Depends(get_db),
):
    """报告中心：跨项目分页列表，支持时间与问题类型筛选。"""
    try:
        report_service = ReportService(db)
        items, total = report_service.browse_reports(
            page=page,
            page_size=page_size,
            project_mode=project_mode,
            date_from=_parse_filter_date(date_from),
            date_to=_parse_filter_date(date_to, end_of_day=True),
            keyword=keyword,
        )
        total_pages = (total + page_size - 1) // page_size if total else 0
        return success(
            PaginatedResponse(
                list=items,
                pagination=PageInfo(
                    page=page,
                    page_size=page_size,
                    total=total,
                    total_pages=total_pages,
                ),
            ),
            message=f"获取报告列表成功，共 {total} 条",
        )
    except Exception as e:
        return error(str(e))


@router.get("/plots/{report_id}/{plot_id}/image")
async def get_report_plot_image(
    report_id: str,
    plot_id: str,
    db: Session = Depends(get_db),
):
    """按需返回报告实验图 PNG（避免列表接口携带大量 base64）。"""
    try:
        report_service = ReportService(db)
        image_path = report_service.get_plot_image_path(report_id, plot_id)
        if not image_path or not image_path.is_file():
            raise HTTPException(status_code=404, detail="图表不存在")
        return FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=f"{plot_id}.png",
        )
    except HTTPException:
        raise
    except Exception as e:
        return error(str(e))


@router.get("/{project_id}", response_model=ApiResponse[List[ReportDBResponse]])
async def get_project_reports(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    获取项目的研究报告列表
    """
    try:
        report_service = ReportService(db)
        reports = report_service.get_reports_by_project(
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return success(
            [report_to_db_response(r) for r in reports],
            message=f"获取研究报告列表成功，共 {len(reports)} 条"
        )
    except Exception as e:
        return error(str(e))


@router.post("/revise", response_model=ApiResponse[dict])
async def revise_report(body: ReportReviseRequest, db: Session = Depends(get_db)):
    """根据用户反馈修改报告（多轮人在回路）。"""
    try:
        svc = get_stage_chat_service(db)
        result = svc.revise_report(
            project_id=body.project_id,
            report_id=body.report_id,
            user_message=body.message,
            section_keys=body.section_keys,
            apply_change=body.apply_change,
        )
        return success(result, message="报告已根据反馈更新")
    except ValueError as e:
        return error(str(e), code=400)
    except Exception as e:
        return error(str(e))


@router.get("/{report_id}/latex-source", response_model=ApiResponse[dict])
async def get_report_latex_source(report_id: str, db: Session = Depends(get_db)):
    """读取报告磁盘上的 LaTeX 源码（内置编辑器用）。"""
    try:
        report_service = ReportService(db)
        return success(report_service.get_latex_source(report_id), message="已加载 LaTeX 源码")
    except ValueError as e:
        return error(str(e), code=400)
    except Exception as e:
        return error(str(e))


@router.put("/{report_id}/latex-source", response_model=ApiResponse[dict])
async def save_report_latex_source(
    report_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """保存手改 LaTeX 源码到磁盘。"""
    try:
        tex = body.get("tex") if isinstance(body, dict) else None
        bib = body.get("bib") if isinstance(body, dict) else None
        if not isinstance(tex, str):
            return error("缺少 tex 字段", code=400)
        report_service = ReportService(db)
        result = report_service.save_latex_source(
            report_id,
            tex=tex,
            bib=bib if isinstance(bib, str) else None,
        )
        return success(result, message="LaTeX 源码已保存")
    except ValueError as e:
        return error(str(e), code=400)
    except Exception as e:
        return error(str(e))


@router.post("/{report_id}/compile-latex", response_model=ApiResponse[dict])
async def compile_report_latex_source(report_id: str, db: Session = Depends(get_db)):
    """编译磁盘上的 report.tex（不从章节重建，保留手改）。"""
    try:
        report_service = ReportService(db)
        result = report_service.compile_latex_source(report_id)
        return success(
            result,
            message="PDF 编译成功" if result.get("pdf_success") else "PDF 编译失败",
        )
    except ValueError as e:
        return error(str(e), code=400)
    except Exception as e:
        return error(str(e))


@router.post("/{report_id}/regenerate-pdf", response_model=ApiResponse[dict])
async def regenerate_report_pdf_endpoint(report_id: str, db: Session = Depends(get_db)):
    """为已有报告重新编译/生成 PDF。"""
    try:
        report_service = ReportService(db)
        result = report_service.regenerate_pdf(report_id)
        return success(
            result,
            message="PDF 重新生成成功" if result.get("pdf_success") else "PDF 生成失败",
        )
    except ValueError as e:
        return error(str(e), code=400)
    except Exception as e:
        return error(str(e))


@router.delete("/{report_id}", response_model=ApiResponse[bool])
async def delete_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    删除研究报告
    """
    try:
        report_service = ReportService(db)
        success_flag = report_service.delete_report(report_id)
        
        return success(
            success_flag,
            message="删除研究报告成功" if success_flag else "报告不存在"
        )
    except Exception as e:
        return error(str(e))
