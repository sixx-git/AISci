"""从 Pipeline 阶段 output 解析 fallback 数据（projects API 用）"""
from __future__ import annotations

import json
import logging
from typing import Any, List

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineStage, PipelineStageExecution, PipelineStatus
from app.schemas.research import ExperimentDesignDBResponse, HypothesisResponse
from app.services._utils.pipeline_queries import (
    get_latest_pipeline_run,
    get_latest_run_with_stage_output,
    get_stage_output,
)

logger = logging.getLogger(__name__)

_COMPLETED_OR_FAILED = [PipelineStatus.COMPLETED, PipelineStatus.FAILED]
_PIPELINE_READ_STATUSES = [
    PipelineStatus.COMPLETED,
    PipelineStatus.FAILED,
    PipelineStatus.RUNNING,
    PipelineStatus.HUMAN_REVIEW_REQUIRED,
]


def safe_output_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        try:
            return json.dumps(val, ensure_ascii=False)
        except Exception:
            return str(val)
    return str(val)


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


def parse_hypotheses_from_pipeline(
    db: Session,
    project_id: str,
) -> List[HypothesisResponse]:
    latest_run = get_latest_pipeline_run(db, project_id, statuses=_COMPLETED_OR_FAILED)
    if not latest_run:
        return []

    results: List[HypothesisResponse] = []
    for stage_name in (PipelineStage.HYPOTHESIS_GENERATION, PipelineStage.HYPOTHESIS_REVIEW):
        output = get_stage_output(db, latest_run.id, stage_name)
        if not output:
            continue
        try:
            items = output.get("hypotheses", [])
            if not isinstance(items, list):
                continue
            stage_exec = _stage_execution(db, latest_run.id, stage_name)
            completed_at = stage_exec.completed_at if stage_exec else latest_run.created_at
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                results.append(HypothesisResponse(
                    id=f"pipeline-{latest_run.id}-{stage_name.value}-{idx}",
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
                    confidence=0.7,
                    created_at=completed_at or latest_run.created_at,
                ))
        except Exception as parse_err:
            logger.warning("解析 Pipeline 阶段 %s 输出失败: %s", stage_name, parse_err)
    return results


def _resolve_experiment_hypothesis(db: Session, pipeline_run_id: str, output: dict) -> str:
    hypothesis = (output.get("hypothesis") or "").strip()
    if hypothesis:
        return hypothesis
    vh = output.get("verifiable_hypothesis")
    if isinstance(vh, dict) and (vh.get("claim") or "").strip():
        return str(vh.get("claim")).strip()
    hr_out = get_stage_output(db, pipeline_run_id, PipelineStage.HYPOTHESIS_REVIEW)
    if isinstance(hr_out, dict):
        reviews = hr_out.get("reviews") or []
        primary_idx = hr_out.get("primary_index", 0)
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0
        if reviews and 0 <= primary_idx < len(reviews) and isinstance(reviews[primary_idx], dict):
            return (reviews[primary_idx].get("hypothesis") or "").strip()
        if reviews and isinstance(reviews[0], dict):
            return (reviews[0].get("hypothesis") or "").strip()
    return ""


def parse_experiment_design_from_pipeline(
    db: Session,
    project_id: str,
) -> List[ExperimentDesignDBResponse]:
    latest_run = get_latest_run_with_stage_output(
        db,
        project_id,
        PipelineStage.EXPERIMENT_DESIGN,
        statuses=_PIPELINE_READ_STATUSES,
    )
    if not latest_run:
        return []

    output = get_stage_output(db, latest_run.id, PipelineStage.EXPERIMENT_DESIGN)
    if not output:
        return []

    try:
        stage_exec = _stage_execution(db, latest_run.id, PipelineStage.EXPERIMENT_DESIGN)
        hypothesis = _resolve_experiment_hypothesis(db, latest_run.id, output)
        return [ExperimentDesignDBResponse(
            id=f"pipeline-{latest_run.id}-experiment_design",
            project_id=project_id,
            hypothesis_id=output.get("hypothesis_id", "") or f"pipeline-run-{latest_run.id}",
            hypothesis=hypothesis,
            methods=safe_output_str(output.get("methods", "")),
            datasets=safe_output_str(output.get("datasets", "")),
            source_data=safe_output_str(output.get("source_data", "")),
            target_data=safe_output_str(output.get("target_data", "")),
            baselines=safe_output_str(output.get("baselines", "")),
            metrics=safe_output_str(output.get("metrics", "")),
            experimental_steps=safe_output_str(output.get("experimental_steps", "")),
            expected_results=safe_output_str(output.get("expected_results", "")),
            limitations=safe_output_str(output.get("limitations", "")),
            status="draft",
            priority=1,
            created_at=(stage_exec.completed_at if stage_exec else None) or latest_run.created_at,
        )]
    except Exception as parse_err:
        logger.warning("解析 Pipeline experiment_design 输出失败: %s", parse_err)
        return []
