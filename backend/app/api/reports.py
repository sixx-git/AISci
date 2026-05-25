"""
报告 API
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.response import ApiResponse, success, error
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

router = APIRouter(prefix="/reports", tags=["reports"])


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


# 导入 json，因为在上面的代码中使用了
import json
