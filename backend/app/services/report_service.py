"""
Report 服务
处理研究报告的数据库操作
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.project import Report, Project
from app.schemas.research import ReportCreate, ReportDBResponse, ReportBrowseItem
from app.core.database import get_db
from app.core.project_modes import normalize_project_mode
from app.services.latex_export_service import (
    export_report_via_latex,
    get_reports_storage_dir,
    regenerate_report_pdf,
)

logger = logging.getLogger(__name__)


def report_pdf_exists(file_id: Optional[str]) -> bool:
    """检查报告目录下是否已有有效 PDF。"""
    if not file_id:
        return False
    pdf_path = get_reports_storage_dir() / file_id / "report.pdf"
    return pdf_path.is_file() and pdf_path.stat().st_size > 0


def report_to_db_response(
    report: Report,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> ReportDBResponse:
    """将 ORM Report 转为 API 响应（补齐 report_id / pdf_generated）。"""
    file_id = report.pdf_path
    extra = extra_metadata if extra_metadata is not None else (
        report.extra_metadata if isinstance(report.extra_metadata, dict) else {}
    )
    pdf_generated = report_pdf_exists(file_id) or bool(extra.get("pdf_success"))

    return ReportDBResponse(
        id=report.id,
        project_id=report.project_id,
        hypothesis_id=report.hypothesis_id,
        experiment_design_id=report.experiment_design_id,
        small_validation_id=report.small_validation_id,
        title=report.title,
        paper_title=report.paper_title,
        paper_abstract=report.paper_abstract,
        markdown_content=report.markdown_content,
        problem_statement=report.problem_statement,
        rationale=report.rationale,
        technical_details=report.technical_details,
        datasets=report.datasets,
        source=report.source,
        target=report.target,
        methods=report.methods,
        experiments=report.experiments,
        results=report.results,
        references=report.references,
        report_id=file_id,
        pdf_generated=pdf_generated,
        status=report.status,
        version=report.version or 1,
        extra_metadata=extra or None,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def enrich_report_for_response(report: Report, db: Session) -> ReportDBResponse:
    """读取报告时重算合规指标，对齐 Pipeline 文献阶段与 References 章节。"""
    from app.models.pipeline import PipelineStage
    from app.services._utils.pipeline_queries import get_latest_pipeline_run, get_literature_mining_output, get_stage_output
    from app.services.literature_bundle_service import enrich_literature_mining
    from app.services.report_compliance_service import enrich_report_extra_metadata

    literature_mining = enrich_literature_mining(get_literature_mining_output(db, report.project_id))
    hypotheses: List[Dict[str, Any]] = []
    latest_run = get_latest_pipeline_run(db, report.project_id)
    if latest_run:
        hg = get_stage_output(db, latest_run.id, PipelineStage.HYPOTHESIS_GENERATION)
        if isinstance(hg, dict):
            hypotheses = hg.get("hypotheses") or []

    extra = enrich_report_extra_metadata(
        report,
        literature_mining=literature_mining if isinstance(literature_mining, dict) else None,
        hypotheses=hypotheses if isinstance(hypotheses, list) else [],
    )
    return report_to_db_response(report, extra_metadata=extra)


class ReportService:
    """研究报告服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_report(self, report_data: ReportCreate) -> Report:
        """创建新的研究报告"""
        try:
            db_report = Report(
                project_id=report_data.project_id,
                hypothesis_id=report_data.hypothesis_id,
                experiment_design_id=report_data.experiment_design_id,
                small_validation_id=report_data.small_validation_id,
                pdf_path=report_data.report_id,  # 旧 report_id 映射为 pdf_path
                title=report_data.title,
                paper_title=report_data.paper_title,
                paper_abstract=report_data.paper_abstract,
                markdown_content=report_data.markdown_content,
                problem_statement=report_data.problem_statement,
                rationale=report_data.rationale,
                technical_details=report_data.technical_details,
                datasets=report_data.datasets,
                source=report_data.source,
                target=report_data.target,
                methods=report_data.methods,
                experiments=report_data.experiments,
                results=report_data.results,
                references=report_data.references,
                status=report_data.status or "draft",
                version=report_data.version or 1,
                extra_metadata=report_data.extra_metadata
            )
            
            self.db.add(db_report)
            self.db.commit()
            self.db.refresh(db_report)
            
            logger.info(f"创建研究报告成功，ID: {db_report.id}")
            return db_report
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建研究报告失败: {e}", exc_info=True)
            raise
    
    def get_report_by_id(self, report_id: str) -> Optional[Report]:
        """根据 ID 获取研究报告"""
        return self.db.query(Report).filter(
            Report.id == report_id
        ).first()
    
    def get_reports_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Report]:
        """获取项目的研究报告列表"""
        query = self.db.query(Report).filter(
            Report.project_id == project_id
        )
        
        if status:
            query = query.filter(Report.status == status)
        
        return query.order_by(
            Report.created_at.desc()
        ).limit(limit).offset(offset).all()
    
    def get_latest_report_by_project(
        self,
        project_id: str,
        *,
        ensure_pdf: bool = True,
    ) -> Optional[Report]:
        """获取项目最新的研究报告；可选在 PDF 缺失时自动补生成。"""
        report = self.db.query(Report).filter(
            Report.project_id == project_id
        ).order_by(
            Report.created_at.desc()
        ).first()
        if report and ensure_pdf and report.pdf_path and not report_pdf_exists(report.pdf_path):
            try:
                self.regenerate_pdf(report.id)
                self.db.refresh(report)
            except Exception as exc:
                logger.warning("自动补生成 PDF 失败 report=%s: %s", report.id, exc)
        return report

    def browse_reports(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        project_mode: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[ReportBrowseItem], int]:
        """跨项目分页浏览报告，支持时间与项目模式筛选。"""
        page = max(1, page)
        page_size = max(1, min(page_size, 50))

        query = (
            self.db.query(Report, Project)
            .join(Project, Report.project_id == Project.id)
        )

        if project_mode and project_mode not in ("", "all"):
            normalized = normalize_project_mode(project_mode)
            query = query.filter(Project.project_mode == normalized)

        if date_from is not None:
            query = query.filter(Report.created_at >= date_from)
        if date_to is not None:
            query = query.filter(Report.created_at <= date_to)

        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    Report.title.ilike(kw),
                    Report.paper_title.ilike(kw),
                    Project.name.ilike(kw),
                    Project.research_question.ilike(kw),
                )
            )

        total = query.count()
        rows = (
            query.order_by(Report.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items: List[ReportBrowseItem] = []
        for report, project in rows:
            items.append(
                ReportBrowseItem(
                    id=report.id,
                    project_id=project.id,
                    project_name=project.name,
                    project_mode=normalize_project_mode(project.project_mode or "general"),
                    research_question=project.research_question,
                    title=report.title,
                    paper_title=report.paper_title,
                    status=report.status,
                    version=report.version or 1,
                    created_at=report.created_at,
                    updated_at=report.updated_at,
                )
            )
        return items, total
    
    def update_report(
        self,
        report_id: str,
        update_data: dict
    ) -> Optional[Report]:
        """更新研究报告"""
        db_report = self.get_report_by_id(report_id)
        if not db_report:
            return None
        
        try:
            # 如果更新内容包含版本信息，递增版本
            if "version" in update_data:
                update_data["version"] = int(update_data["version"])
            else:
                update_data["version"] = db_report.version + 1
            
            for key, value in update_data.items():
                if hasattr(db_report, key):
                    setattr(db_report, key, value)
            
            self.db.commit()
            self.db.refresh(db_report)
            
            logger.info(f"更新研究报告成功，ID: {report_id}")
            return db_report
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新研究报告失败: {e}", exc_info=True)
            raise
    
    def regenerate_pdf(
        self,
        report_id: str,
        *,
        citation_map: Optional[List[Dict[str, Any]]] = None,
    ) -> dict:
        """为已有报告按 LaTeX 模板重新导出 PDF。"""
        db_report = self.get_report_by_id(report_id)
        if not db_report:
            raise ValueError("报告不存在")
        file_id = db_report.pdf_path
        if not file_id:
            raise ValueError("报告未关联文件目录，无法生成 PDF")

        refs = db_report.references
        try:
            refs_list = json.loads(refs) if isinstance(refs, str) and refs.strip().startswith("[") else refs
        except json.JSONDecodeError:
            refs_list = [refs] if refs else []

        result = {
            "title": db_report.title,
            "paper_title": db_report.paper_title,
            "paper_abstract": db_report.paper_abstract,
            "markdown_content": db_report.markdown_content,
            "plots": (db_report.extra_metadata or {}).get("plots", []),
            "chapters": {
                "problem_statement": db_report.problem_statement,
                "rationale": db_report.rationale,
                "technical_details": db_report.technical_details,
                "datasets": db_report.datasets,
                "source": db_report.source,
                "target": db_report.target,
                "methods": db_report.methods,
                "experiments": db_report.experiments,
                "results": db_report.results,
                "references": refs_list if isinstance(refs_list, list) else [],
            },
        }
        verified = list(citation_map or [])
        if not verified and isinstance(refs_list, list):
            verified = [{"title": r} for r in refs_list if isinstance(r, str)]

        export_result = export_report_via_latex(
            result=result,
            output_dir=str(get_reports_storage_dir() / file_id),
            project_info={"title": db_report.paper_title},
            citation_map=citation_map or verified,
            verified_references=verified,
            fallback_markdown_pdf=True,
        )
        result_payload = {
            "success": export_result.get("pdf_success", False),
            "pdf_success": export_result.get("pdf_success", False),
            "pdf_path": export_result.get("pdf_path"),
            "warning": export_result.get("warning"),
            "export_method": export_result.get("export_method"),
        }

        extra = dict(db_report.extra_metadata or {})
        extra["pdf_success"] = result_payload.get("pdf_success", False)
        if result_payload.get("export_method"):
            extra["export_method"] = result_payload["export_method"]
        if result_payload.get("warning"):
            extra["pdf_warning"] = result_payload["warning"]
        db_report.extra_metadata = extra
        self.db.commit()
        self.db.refresh(db_report)

        return {
            **result_payload,
            "report": report_to_db_response(db_report),
        }

    def delete_report(self, report_id: str) -> bool:
        """删除研究报告"""
        db_report = self.get_report_by_id(report_id)
        if not db_report:
            return False
        
        try:
            self.db.delete(db_report)
            self.db.commit()
            
            logger.info(f"删除研究报告成功，ID: {report_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除研究报告失败: {e}", exc_info=True)
            raise


def get_report_service() -> ReportService:
    """获取 ReportService 实例"""
    db = next(get_db())
    return ReportService(db)
