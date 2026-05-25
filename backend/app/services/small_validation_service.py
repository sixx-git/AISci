"""
SmallValidation 服务
处理小样验证的数据库操作
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.research import SmallValidation
from app.schemas.research import SmallValidationCreate, SmallValidationDBResponse
from app.core.database import get_db

logger = logging.getLogger(__name__)


class SmallValidationService:
    """小样验证服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_validation(
        self,
        validation_data: SmallValidationCreate
    ) -> SmallValidation:
        """创建新的小样验证"""
        try:
            db_validation = SmallValidation(
                project_id=validation_data.project_id,
                experiment_design_id=validation_data.experiment_design_id,
                hypothesis=validation_data.hypothesis,
                has_real_data=validation_data.has_real_data,
                analysis_script=validation_data.analysis_script,
                simulated_data=validation_data.simulated_data,
                simulation_assumptions=validation_data.simulation_assumptions,
                charts=validation_data.charts,
                statistics=validation_data.statistics,
                run_log=validation_data.run_log,
                status=validation_data.status or "draft",
                execution_time=validation_data.execution_time
            )
            
            self.db.add(db_validation)
            self.db.commit()
            self.db.refresh(db_validation)
            
            logger.info(f"创建小样验证成功，ID: {db_validation.id}")
            return db_validation
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建小样验证失败: {e}", exc_info=True)
            raise
    
    def get_validation_by_id(
        self,
        validation_id: str
    ) -> Optional[SmallValidation]:
        """根据 ID 获取小样验证"""
        return self.db.query(SmallValidation).filter(
            SmallValidation.id == validation_id
        ).first()
    
    def get_validations_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SmallValidation]:
        """获取项目的小样验证列表"""
        query = self.db.query(SmallValidation).filter(
            SmallValidation.project_id == project_id
        )
        
        if status:
            query = query.filter(SmallValidation.status == status)
        
        return query.order_by(
            SmallValidation.created_at.desc()
        ).limit(limit).offset(offset).all()
    
    def get_validations_by_experiment(
        self,
        experiment_design_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[SmallValidation]:
        """获取实验设计的小样验证列表"""
        return self.db.query(SmallValidation).filter(
            SmallValidation.experiment_design_id == experiment_design_id
        ).order_by(SmallValidation.created_at.desc()).limit(limit).offset(offset).all()
    
    def update_validation(
        self,
        validation_id: str,
        update_data: dict
    ) -> Optional[SmallValidation]:
        """更新小样验证"""
        db_validation = self.get_validation_by_id(validation_id)
        if not db_validation:
            return None
        
        try:
            for key, value in update_data.items():
                if hasattr(db_validation, key):
                    setattr(db_validation, key, value)
            
            self.db.commit()
            self.db.refresh(db_validation)
            
            logger.info(f"更新小样验证成功，ID: {validation_id}")
            return db_validation
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新小样验证失败: {e}", exc_info=True)
            raise
    
    def delete_validation(
        self,
        validation_id: str
    ) -> bool:
        """删除小样验证"""
        db_validation = self.get_validation_by_id(validation_id)
        if not db_validation:
            return False
        
        try:
            self.db.delete(db_validation)
            self.db.commit()
            
            logger.info(f"删除小样验证成功，ID: {validation_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除小样验证失败: {e}", exc_info=True)
            raise


def get_small_validation_service() -> SmallValidationService:
    """获取 SmallValidationService 实例"""
    db = next(get_db())
    return SmallValidationService(db)
