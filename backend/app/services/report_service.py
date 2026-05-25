"""
ResearchReport 服务
处理研究报告的数据库操作
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.research import ResearchReport
from app.schemas.research import ReportCreate, ReportDBResponse
from app.core.database import get_db

logger = logging.getLogger(__name__)


class ReportService:
    """研究报告服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_report(self, report_data: ReportCreate) -> ResearchReport:
        """创建新的研究报告"""
        try:
            db_report = ResearchReport(
                project_id=report_data.project_id,
                hypothesis_id=report_data.hypothesis_id,
                experiment_design_id=report_data.experiment_design_id,
                small_validation_id=report_data.small_validation_id,
                report_id=report_data.report_id,
                pdf_generated=1 if report_data.pdf_generated else 0,
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
                version=report_data.version or 1
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
    
    def get_report_by_id(self, report_id: str) -> Optional[ResearchReport]:
        """根据 ID 获取研究报告"""
        return self.db.query(ResearchReport).filter(
            ResearchReport.id == report_id
        ).first()
    
    def get_reports_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ResearchReport]:
        """获取项目的研究报告列表"""
        query = self.db.query(ResearchReport).filter(
            ResearchReport.project_id == project_id
        )
        
        if status:
            query = query.filter(ResearchReport.status == status)
        
        return query.order_by(
            ResearchReport.created_at.desc()
        ).limit(limit).offset(offset).all()
    
    def get_latest_report_by_project(
        self,
        project_id: str
    ) -> Optional[ResearchReport]:
        """获取项目最新的研究报告"""
        return self.db.query(ResearchReport).filter(
            ResearchReport.project_id == project_id
        ).order_by(
            ResearchReport.created_at.desc()
        ).first()
    
    def update_report(
        self,
        report_id: str,
        update_data: dict
    ) -> Optional[ResearchReport]:
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
