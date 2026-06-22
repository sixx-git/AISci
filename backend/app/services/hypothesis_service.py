"""
Hypothesis 服务
处理假设和证据链的数据库操作
"""
import logging
import json
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.research import Hypothesis, Evidence
from app.schemas.research import HypothesisCreate, HypothesisResponse
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
                supporting_fact_ids=json.dumps(hypothesis_data.supporting_fact_ids, ensure_ascii=False) if hypothesis_data.supporting_fact_ids else None,
                evidence_level=hypothesis_data.evidence_level or "medium",
                status=hypothesis_data.status or "draft",
                priority=hypothesis_data.priority or 3,
                confidence=hypothesis_data.confidence or 0.5,
                alignment_score=hypothesis_data.alignment_score,
                off_topic=hypothesis_data.off_topic,
                off_topic_reason=hypothesis_data.off_topic_reason,
                matched_keywords=json.dumps(hypothesis_data.matched_keywords, ensure_ascii=False) if hypothesis_data.matched_keywords else None,
                missing_keywords=json.dumps(hypothesis_data.missing_keywords, ensure_ascii=False) if hypothesis_data.missing_keywords else None,
                question_alignment=hypothesis_data.question_alignment,
                dataset_field_refs=json.dumps(hypothesis_data.dataset_field_refs, ensure_ascii=False) if hypothesis_data.dataset_field_refs else None,
                data_evidence_ids=json.dumps(hypothesis_data.data_evidence_ids, ensure_ascii=False) if hypothesis_data.data_evidence_ids else None,
                validation_target=hypothesis_data.validation_target,
                expected_measurable_effect=hypothesis_data.expected_measurable_effect,
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
                    supporting_fact_ids=hypo_data.get("supporting_fact_ids") if isinstance(hypo_data.get("supporting_fact_ids"), list) else None,
                    evidence_level=hypo_data.get("evidence_level", "medium"),
                    status=status,
                    priority=idx + 1 if idx + 1 <= 5 else 3,  # 前 5 个优先级更高
                    alignment_score=hypo_data.get("alignment_score"),
                    off_topic=hypo_data.get("off_topic"),
                    off_topic_reason=hypo_data.get("off_topic_reason"),
                    matched_keywords=hypo_data.get("matched_keywords"),
                    missing_keywords=hypo_data.get("missing_keywords"),
                    question_alignment=hypo_data.get("question_alignment"),
                    dataset_field_refs=hypo_data.get("dataset_field_refs") if isinstance(hypo_data.get("dataset_field_refs"), list) else None,
                    data_evidence_ids=hypo_data.get("data_evidence_ids") if isinstance(hypo_data.get("data_evidence_ids"), list) else None,
                    validation_target=hypo_data.get("validation_target"),
                    expected_measurable_effect=hypo_data.get("expected_measurable_effect"),
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

    def set_primary_hypothesis(self, project_id: str, hypothesis_id: str) -> Optional[Hypothesis]:
        """将指定假设设为主假设，其他假设取消主假设标记"""
        target = self.get_hypothesis_by_id(hypothesis_id)
        if not target:
            return None

        try:
            self.db.query(Hypothesis).filter(
                Hypothesis.project_id == project_id,
                Hypothesis.priority == 1,
            ).update({"priority": 3})

            target.priority = 1
            self.db.commit()
            self.db.refresh(target)

            logger.info(f"设置主假设成功，ID：{hypothesis_id}, 项目：{project_id}")
            return target

        except Exception as e:
            self.db.rollback()
            logger.error(f"设置主假设失败：{e}", exc_info=True)
            raise
    
    def create_evidence_batch(
        self,
        project_id: str,
        hypothesis_id: str,
        facts: List[dict]
    ) -> List[Evidence]:
        """为一条假设批量创建证据记录"""
        created = []
        try:
            for fact in facts:
                evidence = Evidence(
                    project_id=project_id,
                    hypothesis_id=hypothesis_id,
                    document_id=fact.get("document_id") or fact.get("source_document_id"),
                    chunk_id=fact.get("source_chunk_id"),
                    fact_text=fact.get("fact_text") or fact.get("content", ""),
                    quote_text=fact.get("quote_text"),
                    page_number=fact.get("page_number") or fact.get("source_page"),
                    relevance_score=fact.get("relevance_score", 0.5),
                    source_title=fact.get("source_paper_title") or fact.get("source_title"),
                    extra_metadata=fact.get("extra_metadata"),
                )
                self.db.add(evidence)
                created.append(evidence)
            self.db.commit()
            logger.info(f"批量创建 {len(created)} 条证据记录，假设 ID: {hypothesis_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"批量创建证据失败: {e}", exc_info=True)
            raise
        return created

    def get_evidence_by_hypothesis(self, hypothesis_id: str) -> List[Evidence]:
        """获取某条假设的证据链"""
        return self.db.query(Evidence).filter(
            Evidence.hypothesis_id == hypothesis_id
        ).order_by(Evidence.relevance_score.desc()).all()

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
