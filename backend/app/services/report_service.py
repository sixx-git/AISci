"""
Report 服务
处理研究报告的数据库操作
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.project import Report, Project
from app.schemas.research import ReportCreate, ReportDBResponse, ReportBrowseItem
from app.core.database import get_db
from app.core.project_modes import normalize_project_mode

logger = logging.getLogger(__name__)


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
        project_id: str
    ) -> Optional[Report]:
        """获取项目最新的研究报告"""
        return self.db.query(Report).filter(
            Report.project_id == project_id
        ).order_by(
            Report.created_at.desc()
        ).first()

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
