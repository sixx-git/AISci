"""
报告 API
"""
import os
import json
from fastapi import APIRouter, Depends, HTTPException
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
    ReportDBResponse
)
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])
settings = get_settings()


def get_download_url(report_id: str, file_type: str) -> str:
    """
    获取下载地址
    
    Args:
        report_id: 报告 ID
        file_type: 文件类型 (pdf 或 md)
        
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
        md_download_url = get_download_url(report_file_id, "md") if report_file_id else None
        pdf_download_url = get_download_url(report_file_id, "pdf") if report_file_id and pdf_success else None
        
        # 更新结果包含下载地址
        report_result["md_download_url"] = md_download_url
        report_result["pdf_download_url"] = pdf_download_url
        
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
            markdown_content=report_result.get("markdown_content", ""),
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
            version=1
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
async def download_report_file(report_id: str, file_type: str):
    """
    下载报告文件
    
    Args:
        report_id: 报告文件 ID
        file_type: 文件类型 (pdf 或 md)
    """
    try:
        # 构建文件路径
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "reports")
        report_dir = os.path.join(reports_dir, report_id)
        
        if file_type == "pdf":
            file_path = os.path.join(report_dir, "report.pdf")
            filename = "科学假设与研究计划.pdf"
            media_type = "application/pdf"
        elif file_type == "md":
            file_path = os.path.join(report_dir, "report.md")
            filename = "科学假设与研究计划.md"
            media_type = "text/markdown"
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 如果 PDF 不存在，尝试返回 MD
            if file_type == "pdf":
                md_path = os.path.join(report_dir, "report.md")
                if os.path.exists(md_path):
                    return FileResponse(
                        md_path,
                        filename="科学假设与研究计划.md",
                        media_type="text/markdown"
                    )
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
            reports,
            message=f"获取研究报告列表成功，共 {len(reports)} 条"
        )
    except Exception as e:
        return error(str(e))


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
            report,
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
            report,
            message="获取研究报告详情成功" if report else "报告不存在"
        )
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
