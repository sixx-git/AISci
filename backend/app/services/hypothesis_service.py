"""
Hypothesis 服务
处理假设和证据链的数据库操作
"""
import logging
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.research import Hypothesis, Evidence
from app.models.pipeline import PipelineStage
from app.schemas.research import HypothesisCreate, HypothesisResponse, HypothesisReviewScores
from app.services._utils.pipeline_queries import (
    get_latest_pipeline_run,
    get_stage_output,
)
from app.services.literature_search_utils import (
    build_minimal_evidence_chain,
    match_literature_facts,
)
logger = logging.getLogger(__name__)


def extract_review_scores(review: dict) -> dict:
    """从 hypothesis_review 单条 review 提取维度分数。"""
    scores = review.get("scores") or {}

    def dim(key: str):
        raw = scores.get(key)
        if isinstance(raw, dict):
            return raw.get("score")
        if isinstance(raw, (int, float)):
            return raw
        return None

    return {
        "novelty": dim("novelty"),
        "testability": dim("testability"),
        "data_availability": dim("data_availability"),
        "scientific_value": dim("scientific_value"),
        "cost_risk": dim("cost_risk"),
        "overall_score": review.get("overall_score"),
    }


def parse_review_scores_json(raw: Optional[str]) -> Optional[HypothesisReviewScores]:
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            return HypothesisReviewScores.model_validate(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def match_review_for_hypothesis(reviews: List[dict], hypothesis_text: str, index: int):
    text = (hypothesis_text or "").strip()
    if index < len(reviews):
        candidate = reviews[index]
        cand_text = (candidate.get("hypothesis") or "").strip()
        if not text or not cand_text or cand_text == text or cand_text in text or text in cand_text:
            return candidate
    for review in reviews:
        rev_text = (review.get("hypothesis") or "").strip()
        if text and rev_text and (rev_text == text or rev_text in text or text in rev_text):
            return review
    return reviews[index] if 0 <= index < len(reviews) else None


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

    def replace_project_hypotheses(self, project_id: str) -> int:
        """删除项目下已有假设及其证据（Pipeline 重新保存前调用）。"""
        hypos = self.get_hypotheses_by_project(project_id, limit=500)
        if not hypos:
            return 0
        hypo_ids = [h.id for h in hypos]
        try:
            self.db.query(Evidence).filter(Evidence.hypothesis_id.in_(hypo_ids)).delete(
                synchronize_session=False
            )
            for hypo in hypos:
                self.db.delete(hypo)
            self.db.commit()
            logger.info("已替换项目 %s 的 %d 条旧假设", project_id, len(hypo_ids))
            return len(hypo_ids)
        except Exception as e:
            self.db.rollback()
            logger.error("替换项目假设失败: %s", e, exc_info=True)
            raise

    def to_response(self, hypothesis: Hypothesis) -> HypothesisResponse:
        resp = HypothesisResponse.model_validate(hypothesis)
        review_scores = parse_review_scores_json(getattr(hypothesis, "review_scores_json", None))
        if review_scores:
            return resp.model_copy(update={"review_scores": review_scores})
        return resp

    def backfill_evidence_from_literature(
        self,
        hypothesis: Hypothesis,
        literature_mining: dict,
    ) -> List[Evidence]:
        """从 Pipeline 文献 facts 为缺少证据的假设补建证据与最小证据链。"""
        from app.services.evidence_reasoning_service import get_evidence_reasoning_service
        from app.services.literature_search_utils import (
            build_minimal_evidence_chain,
            match_literature_facts,
        )

        existing = self.get_evidence_by_hypothesis(hypothesis.id)
        if existing:
            return existing

        raw_ids = hypothesis.supporting_fact_ids
        try:
            target_ids = json.loads(raw_ids) if raw_ids else []
        except (json.JSONDecodeError, TypeError):
            target_ids = []
        if not isinstance(target_ids, list):
            target_ids = []

        all_facts = literature_mining.get("facts", []) if isinstance(literature_mining, dict) else []
        matched_facts = match_literature_facts(all_facts, target_ids)
        if not matched_facts:
            return []

        created = self.create_evidence_batch(
            project_id=hypothesis.project_id,
            hypothesis_id=hypothesis.id,
            facts=matched_facts,
        )
        er_service = get_evidence_reasoning_service()
        if not er_service.load_evidence_chain(hypothesis.project_id, hypothesis.id):
            minimal_chain = build_minimal_evidence_chain(hypothesis.hypothesis, matched_facts)
            er_service.save_evidence_chain(hypothesis.project_id, hypothesis.id, minimal_chain)
        return created
    
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
            self.db.query(Evidence).filter(Evidence.hypothesis_id == hypothesis_id).delete(
                synchronize_session=False
            )
            self.db.delete(db_hypothesis)
            self.db.commit()
            
            logger.info(f"删除假设成功，ID：{hypothesis_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除假设失败：{e}", exc_info=True)
            raise

    def apply_review_scores_to_hypotheses(
        self,
        project_id: str,
        hypothesis_generation: Dict[str, Any],
        review_result: Dict[str, Any],
        db_hypos: Optional[List[Hypothesis]] = None,
    ) -> None:
        """将 hypothesis_review 结果回写至已保存的假设。"""
        db_hypos = db_hypos or self.get_hypotheses_by_project(project_id, limit=50)
        if not db_hypos:
            return

        reviews = review_result.get("reviews") or []
        ensemble = (review_result.get("skill_outputs") or {}).get("ensemble_review") or {}
        primary_idx = review_result.get("primary_index")
        if primary_idx is None:
            primary_idx = ensemble.get("target_hypothesis_index", 0)
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0

        decision = ensemble.get("decision") or review_result.get("ensemble_decision")
        overall = ensemble.get("overall") or review_result.get("ensemble_overall")
        hg_hypos = hypothesis_generation.get("hypotheses") or []

        for i, review in enumerate(reviews):
            review_text = (review.get("hypothesis") or "").strip()
            db_hypo = db_hypos[i] if i < len(db_hypos) else None
            if review_text:
                for h in db_hypos:
                    if h.hypothesis.strip() == review_text or review_text in h.hypothesis:
                        db_hypo = h
                        break
            if not db_hypo and i < len(hg_hypos):
                hypo_text = (hg_hypos[i].get("hypothesis") or "").strip()
                for h in db_hypos:
                    if h.hypothesis.strip() == hypo_text:
                        db_hypo = h
                        break
            if not db_hypo:
                continue

            score = review.get("overall_score")
            if score is None and i == primary_idx:
                score = overall
            confidence = float(score or 5.0) / 10.0
            status = db_hypo.status or "draft"
            if i == primary_idx:
                if decision == "Accept":
                    status = "accepted"
                elif decision == "Reject":
                    status = "rejected"
            self.update_hypothesis(
                db_hypo.id,
                {
                    "confidence": confidence,
                    "status": status,
                    "review_scores_json": json.dumps(extract_review_scores(review), ensure_ascii=False),
                },
            )

        if 0 <= primary_idx < len(db_hypos):
            self.set_primary_hypothesis(project_id, db_hypos[primary_idx].id)

    def persist_hypotheses_from_pipeline_results(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
        *,
        apply_reviews: bool = True,
    ) -> List[Hypothesis]:
        """将 Pipeline 阶段结果写入 Hypothesis / Evidence / 证据链 JSON。"""
        from app.services.evidence_reasoning_service import get_evidence_reasoning_service

        hg = results.get("hypothesis_generation") or {}
        lm = results.get("literature_mining") or {}
        if not hg.get("hypotheses"):
            return []

        alignment_data = hg.get("alignment", {})
        alignments = alignment_data.get("alignments", []) if alignment_data else []
        hypotheses_with_alignment = []
        for i, h in enumerate(hg["hypotheses"]):
            item = dict(h)
            if i < len(alignments):
                a = alignments[i]
                item["alignment_score"] = a.get("alignment_score")
                item["off_topic"] = a.get("off_topic")
                item["off_topic_reason"] = a.get("off_topic_reason")
                item["matched_keywords"] = a.get("matched_keywords")
                item["missing_keywords"] = a.get("missing_keywords")
            hypotheses_with_alignment.append(item)

        self.replace_project_hypotheses(project_id)
        created_hypos = self.create_hypotheses_batch(
            project_id=project_id,
            research_question=research_question,
            hypotheses_list=hypotheses_with_alignment,
        )

        er_service = get_evidence_reasoning_service()
        all_facts = lm.get("facts", [])
        for idx, db_hypo in enumerate(created_hypos):
            hypo_data = hypotheses_with_alignment[idx] if idx < len(hypotheses_with_alignment) else {}
            chain = hypo_data.get("evidence_chain")
            if chain:
                er_service.save_evidence_chain(project_id, db_hypo.id, chain)
                final_text = chain.get("final_version") or hypo_data.get("hypothesis")
                if final_text and final_text != db_hypo.hypothesis:
                    self.update_hypothesis(
                        db_hypo.id,
                        {"hypothesis": final_text, "rationale": db_hypo.rationale},
                    )
                evidence_items = (chain.get("supporting_evidence") or []) + (chain.get("counter_evidence") or [])
                facts_for_db = []
                for ev in evidence_items:
                    facts_for_db.append(
                        {
                            "fact_text": ev.get("claim") or ev.get("quote_or_summary", ""),
                            "quote_text": ev.get("quote_or_summary", ""),
                            "source_paper_title": ev.get("source_title", ""),
                            "document_id": ev.get("paper_id") or ev.get("document_id"),
                            "relevance_score": ev.get("relevance_score", 0.5),
                            "extra_metadata": json.dumps(
                                {
                                    "stance": ev.get("stance"),
                                    "stance_reason": ev.get("stance_reason"),
                                    "reliability_score": ev.get("reliability_score"),
                                    "evidence_id": ev.get("evidence_id"),
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )
                if facts_for_db:
                    self.create_evidence_batch(project_id, db_hypo.id, facts_for_db)
                continue

            target_ids = hypo_data.get("supporting_fact_ids") or []
            if not isinstance(target_ids, list):
                target_ids = []
            if not target_ids and db_hypo.supporting_fact_ids:
                try:
                    target_ids = json.loads(db_hypo.supporting_fact_ids)
                except (json.JSONDecodeError, TypeError):
                    target_ids = []

            matched_facts = match_literature_facts(all_facts, target_ids) if target_ids else []
            if matched_facts:
                self.create_evidence_batch(project_id, db_hypo.id, matched_facts)
                er_service.save_evidence_chain(
                    project_id,
                    db_hypo.id,
                    build_minimal_evidence_chain(db_hypo.hypothesis, matched_facts),
                )

        if apply_reviews:
            review_result = results.get("hypothesis_review") or {}
            if review_result.get("reviews"):
                self.apply_review_scores_to_hypotheses(
                    project_id,
                    hg,
                    review_result,
                    db_hypos=created_hypos,
                )

        return self.get_hypotheses_by_project(project_id, limit=50)

    def materialize_from_latest_pipeline(self, project_id: str) -> List[Hypothesis]:
        """DB 无假设时，从最近一次 Pipeline 阶段输出物化假设与证据。"""
        from app.models.pipeline import PipelineStatus

        statuses = [
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
            PipelineStatus.RUNNING,
            PipelineStatus.HUMAN_REVIEW_REQUIRED,
        ]
        latest_run = get_latest_pipeline_run(self.db, project_id, statuses=statuses)
        if not latest_run:
            return []

        hg = get_stage_output(self.db, latest_run.id, PipelineStage.HYPOTHESIS_GENERATION)
        if not hg or not hg.get("hypotheses"):
            return []

        lm = get_stage_output(self.db, latest_run.id, PipelineStage.LITERATURE_MINING) or {}
        hr = get_stage_output(self.db, latest_run.id, PipelineStage.HYPOTHESIS_REVIEW) or {}
        results = {
            "hypothesis_generation": hg,
            "literature_mining": lm,
            "hypothesis_review": hr,
        }
        research_question = latest_run.research_question or ""
        try:
            return self.persist_hypotheses_from_pipeline_results(
                project_id,
                research_question,
                results,
                apply_reviews=bool(hr.get("reviews")),
            )
        except Exception as exc:
            logger.warning("从 Pipeline 物化假设失败 project_id=%s: %s", project_id, exc)
            return []
