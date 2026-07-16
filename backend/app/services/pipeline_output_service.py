"""从 Pipeline 阶段 output 解析 fallback 数据（projects API 用）"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineStage, PipelineStageExecution, PipelineStatus
from app.schemas.research import HypothesisResponse, HypothesisReviewScores
from app.services.hypothesis_service import extract_review_scores, match_review_for_hypothesis
from app.services._utils.pipeline_queries import (
    get_latest_pipeline_run,
    get_stage_output,
)

logger = logging.getLogger(__name__)

_COMPLETED_OR_FAILED = [PipelineStatus.COMPLETED, PipelineStatus.FAILED]


def _stage_execution(
    db: Session,
    pipeline_run_id: str,
    stage: PipelineStage,
) -> PipelineStageExecution | None:
    return (
        db.query(PipelineStageExecution)
        .filter(
            PipelineStageExecution.pipeline_run_id == pipeline_run_id,
            PipelineStageExecution.stage == stage,
        )
        .first()
    )


def get_latest_hypothesis_reviews(
    db: Session,
    project_id: str,
) -> List[dict]:
    """从最近一次 Pipeline 的 hypothesis_review 阶段读取 reviews。"""
    latest_run = get_latest_pipeline_run(db, project_id, statuses=_COMPLETED_OR_FAILED)
    if not latest_run:
        return []
    output = get_stage_output(db, latest_run.id, PipelineStage.HYPOTHESIS_REVIEW)
    if not isinstance(output, dict):
        return []
    reviews = output.get("reviews") or []
    return [r for r in reviews if isinstance(r, dict)]


def enrich_hypothesis_responses_with_reviews(
    db: Session,
    project_id: str,
    responses: List[HypothesisResponse],
) -> List[HypothesisResponse]:
    """为缺少 review_scores 的假设从 Pipeline 阶段输出补全评审分数。"""
    reviews = get_latest_hypothesis_reviews(db, project_id)
    if not reviews:
        return responses

    enriched: List[HypothesisResponse] = []
    for idx, resp in enumerate(responses):
        if resp.review_scores:
            enriched.append(resp)
            continue
        review = match_review_for_hypothesis(reviews, resp.hypothesis, idx)
        if not review:
            enriched.append(resp)
            continue
        scores = HypothesisReviewScores.model_validate(extract_review_scores(review))
        overall = scores.overall_score
        confidence = resp.confidence
        if overall is not None:
            confidence = float(overall) / 10.0
        enriched.append(resp.model_copy(update={"review_scores": scores, "confidence": confidence}))
    return enriched


def parse_hypotheses_from_pipeline(
    db: Session,
    project_id: str,
) -> List[HypothesisResponse]:
    latest_run = get_latest_pipeline_run(db, project_id, statuses=_COMPLETED_OR_FAILED)
    if not latest_run:
        return []

    hg_output = get_stage_output(db, latest_run.id, PipelineStage.HYPOTHESIS_GENERATION)
    if not hg_output:
        return []
    hr_output = get_stage_output(db, latest_run.id, PipelineStage.HYPOTHESIS_REVIEW) or {}
    reviews = hr_output.get("reviews") or []
    items = hg_output.get("hypotheses") or []
    if not isinstance(items, list):
        return []

    stage_exec = _stage_execution(db, latest_run.id, PipelineStage.HYPOTHESIS_GENERATION)
    completed_at = stage_exec.completed_at if stage_exec else latest_run.created_at
    results: List[HypothesisResponse] = []
    try:
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            review = match_review_for_hypothesis(reviews, item.get("hypothesis", ""), idx)
            review_scores = None
            confidence = 0.5
            if review:
                review_scores = HypothesisReviewScores.model_validate(extract_review_scores(review))
                if review_scores.overall_score is not None:
                    confidence = float(review_scores.overall_score) / 10.0
            results.append(
                HypothesisResponse(
                    id=f"pipeline-{latest_run.id}-hypothesis_generation-{idx}",
                    project_id=project_id,
                    research_question=latest_run.research_question or "",
                    hypothesis=item.get("hypothesis", ""),
                    rationale=item.get("rationale", ""),
                    novelty=item.get("novelty", ""),
                    testability=item.get("testability", ""),
                    required_data=item.get("required_data", ""),
                    possible_method=item.get("possible_method", ""),
                    risk=item.get("risk", ""),
                    supporting_fact_ids=item.get("supporting_fact_ids", []) or [],
                    evidence_level=item.get("evidence_level", "medium"),
                    status="draft",
                    priority=idx + 1 if idx + 1 <= 5 else 3,
                    confidence=confidence,
                    review_scores=review_scores,
                    created_at=completed_at or latest_run.created_at,
                )
            )
    except Exception as parse_err:
        logger.warning("解析 Pipeline 假设输出失败: %s", parse_err)
    return results
