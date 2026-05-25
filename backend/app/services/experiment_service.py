"""
ExperimentDesign 服务
处理实验设计的数据库操作
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.research import ExperimentDesign
from app.schemas.research import ExperimentDesignCreate, ExperimentDesignDBResponse
from app.core.database import get_db

logger = logging.getLogger(__name__)


class ExperimentDesignService:
    """实验设计服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_experiment_design(
        self, 
        experiment_data: ExperimentDesignCreate
    ) -> ExperimentDesign:
        """创建新实验设计"""
        try:
            db_experiment = ExperimentDesign(
                project_id=experiment_data.project_id,
                hypothesis_id=experiment_data.hypothesis_id,
                hypothesis=experiment_data.hypothesis,
                methods=experiment_data.methods,
                datasets=experiment_data.datasets,
                source_data=experiment_data.source_data,
                target_data=experiment_data.target_data,
                baselines=experiment_data.baselines,
                metrics=experiment_data.metrics,
                experimental_steps=experiment_data.experimental_steps,
                expected_results=experiment_data.expected_results,
                limitations=experiment_data.limitations,
                status=experiment_data.status or "draft",
                priority=experiment_data.priority or 3
            )
            
            self.db.add(db_experiment)
            self.db.commit()
            self.db.refresh(db_experiment)
            
            logger.info(f"创建实验设计成功，ID：{db_experiment.id}")
            return db_experiment
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建实验设计失败：{e}", exc_info=True)
            raise
    
    def get_experiment_design_by_id(
        self, 
        experiment_id: str
    ) -> Optional[ExperimentDesign]:
        """根据 ID 获取实验设计"""
        return self.db.query(ExperimentDesign).filter(
            ExperimentDesign.id == experiment_id
        ).first()
    
    def get_experiment_designs_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ExperimentDesign]:
        """获取项目的实验设计列表"""
        query = self.db.query(ExperimentDesign).filter(
            ExperimentDesign.project_id == project_id
        )
        
        if status:
            query = query.filter(ExperimentDesign.status == status)
        
        return query.order_by(
            ExperimentDesign.priority, 
            ExperimentDesign.created_at.desc()
        ).limit(limit).offset(offset).all()
    
    def get_experiment_designs_by_hypothesis(
        self,
        hypothesis_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[ExperimentDesign]:
        """获取假设的实验设计列表"""
        return self.db.query(ExperimentDesign).filter(
            ExperimentDesign.hypothesis_id == hypothesis_id
        ).order_by(ExperimentDesign.created_at.desc()).limit(limit).offset(offset).all()
    
    def update_experiment_design(
        self,
        experiment_id: str,
        update_data: dict
    ) -> Optional[ExperimentDesign]:
        """更新实验设计"""
        db_experiment = self.get_experiment_design_by_id(experiment_id)
        if not db_experiment:
            return None
        
        try:
            for key, value in update_data.items():
                if hasattr(db_experiment, key):
                    setattr(db_experiment, key, value)
            
            self.db.commit()
            self.db.refresh(db_experiment)
            
            logger.info(f"更新实验设计成功，ID：{experiment_id}")
            return db_experiment
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新实验设计失败：{e}", exc_info=True)
            raise
    
    def delete_experiment_design(self, experiment_id: str) -> bool:
        """删除实验设计"""
        db_experiment = self.get_experiment_design_by_id(experiment_id)
        if not db_experiment:
            return False
        
        try:
            self.db.delete(db_experiment)
            self.db.commit()
            
            logger.info(f"删除实验设计成功，ID：{experiment_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除实验设计失败：{e}", exc_info=True)
            raise


def get_experiment_design_service() -> ExperimentDesignService:
    """获取 ExperimentDesignService 实例"""
    db = next(get_db())
    return ExperimentDesignService(db)
