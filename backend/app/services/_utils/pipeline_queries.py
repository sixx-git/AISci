"""Pipeline 相关 DB 查询辅助"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineRun, PipelineStage, PipelineStageExecution, PipelineStatus


def get_latest_pipeline_run(
    db: Session,
    project_id: str,
    *,
    statuses: Optional[List[PipelineStatus]] = None,
) -> Optional[PipelineRun]:
    query = db.query(PipelineRun).filter(PipelineRun.project_id == project_id)
    if statuses:
        query = query.filter(PipelineRun.status.in_(statuses))
    return query.order_by(PipelineRun.created_at.desc()).first()


def get_stage_output(
    db: Session,
    pipeline_run_id: str,
    stage: PipelineStage,
) -> Optional[Dict[str, Any]]:
    stage_exec = (
        db.query(PipelineStageExecution)
        .filter(
            PipelineStageExecution.pipeline_run_id == pipeline_run_id,
            PipelineStageExecution.stage == stage,
        )
        .first()
    )
    if not stage_exec or not isinstance(stage_exec.output_data, dict):
        return None
    return stage_exec.output_data


def get_literature_mining_output(
    db: Session,
    project_id: str,
    *,
    statuses: Optional[List[PipelineStatus]] = None,
) -> Dict[str, Any]:
    """获取项目最近一次 run 的 literature_mining 阶段输出。"""
    empty: Dict[str, Any] = {
        "facts": [],
        "citation_map": [],
        "uncertain_points": [],
        "imported_documents": [],
        "multimodal_evidence": [],
    }
    if statuses is None:
        statuses = [
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
            PipelineStatus.RUNNING,
        ]
    latest_run = get_latest_pipeline_run(db, project_id, statuses=statuses)
    if not latest_run:
        return empty
    output = get_stage_output(db, latest_run.id, PipelineStage.LITERATURE_MINING)
    return output if output else empty
