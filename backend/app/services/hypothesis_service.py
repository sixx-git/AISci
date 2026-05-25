"""
Hypothesis 服务
处理假设的数据库操作
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.research import Hypothesis
from app.schemas.research import HypothesisCreate, HypothesisResponse
from app.core.database import get_db

logger = logging.getLogger(__name__)


class HypothesisService:
    """假设服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_hypothesis(self, hypothesis_data: HypothesisCreate) -> Hypothesis:
        """创建新假设"""
        try:
            db_hypothesis = Hypothesis(
                project_id=hypothesis_data.project_id,
                research_question=hypothesis_data.research_question,
                hypothesis=hypothesis_data.hypothesis,
                rationale=hypothesis_data.rationale,
                novelty=hypothesis_data.novelty,
                testability=hypothesis_data.testability,
                required_data=hypothesis_data.required_data,
                possible_method=hypothesis_data.possible_method,
                risk=hypothesis_data.risk,
                status=hypothesis_data.status or "draft",
                priority=hypothesis_data.priority or 3,
                confidence=hypothesis_data.confidence or 0.5
            )
            
            self.db.add(db_hypothesis)
            self.db.commit()
            self.db.refresh(db_hypothesis)
            
            logger.info(f"创建假设成功，ID：{db_hypothesis.id}")
            return db_hypothesis
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建假设失败：{e}", exc_info=True)
            raise
    
    def create_hypotheses_batch(
        self,
        project_id: str,
        research_question: str,
        hypotheses_list: List[dict],
        status: str = "draft"
    ) -> List[Hypothesis]:
        """批量创建假设"""
        created_hypotheses = []
        
        try:
            for idx, hypo_data in enumerate(hypotheses_list):
                hypothesis_create = HypothesisCreate(
                    project_id=project_id,
                    research_question=research_question,
                    hypothesis=hypo_data.get("hypothesis", ""),
                    rationale=hypo_data.get("rationale", ""),
                    novelty=hypo_data.get("novelty", ""),
                    testability=hypo_data.get("testability", ""),
                    required_data=hypo_data.get("required_data", ""),
                    possible_method=hypo_data.get("possible_method", ""),
                    risk=hypo_data.get("risk", ""),
                    status=status,
                    priority=idx + 1 if idx + 1 <= 5 else 3  # 前 5 个优先级更高
                )
                
                db_hypothesis = self.create_hypothesis(hypothesis_create)
                created_hypotheses.append(db_hypothesis)
            
            logger.info(f"批量创建 {len(created_hypotheses)} 个假设成功")
            return created_hypotheses
            
        except Exception as e:
            logger.error(f"批量创建假设失败：{e}", exc_info=True)
            raise
    
    def get_hypothesis_by_id(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """根据 ID 获取假设"""
        return self.db.query(Hypothesis).filter(Hypothesis.id == hypothesis_id).first()
    
    def get_hypotheses_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Hypothesis]:
        """获取项目的假设列表"""
        query = self.db.query(Hypothesis).filter(Hypothesis.project_id == project_id)
        
        if status:
            query = query.filter(Hypothesis.status == status)
        
        return query.order_by(Hypothesis.priority, Hypothesis.created_at.desc()).limit(limit).offset(offset).all()
    
    def update_hypothesis(
        self,
        hypothesis_id: str,
        update_data: dict
    ) -> Optional[Hypothesis]:
        """更新假设"""
        db_hypothesis = self.get_hypothesis_by_id(hypothesis_id)
        if not db_hypothesis:
            return None
        
        try:
            for key, value in update_data.items():
                if hasattr(db_hypothesis, key):
                    setattr(db_hypothesis, key, value)
            
            self.db.commit()
            self.db.refresh(db_hypothesis)
            
            logger.info(f"更新假设成功，ID：{hypothesis_id}")
            return db_hypothesis
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新假设失败：{e}", exc_info=True)
            raise
    
    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """删除假设"""
        db_hypothesis = self.get_hypothesis_by_id(hypothesis_id)
        if not db_hypothesis:
            return False
        
        try:
            self.db.delete(db_hypothesis)
            self.db.commit()
            
            logger.info(f"删除假设成功，ID：{hypothesis_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除假设失败：{e}", exc_info=True)
            raise


def get_hypothesis_service() -> HypothesisService:
    """获取 HypothesisService 实例"""
    db = next(get_db())
    return HypothesisService(db)
