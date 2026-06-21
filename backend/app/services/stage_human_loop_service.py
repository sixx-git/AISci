"""阶段人工审阅、编辑与修订历史"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.pipeline import (
    PipelineRun,
    PipelineStageExecution,
    PipelineStage,
    PipelineStatus,
)

CHINA_TZ = timezone(timedelta(hours=8))

STAGE_KEY_ORDER = [
    "problem_understanding",
    "literature_mining",
    "knowledge_gap",
    "hypothesis_generation",
    "hypothesis_review",
    "experiment_design",
    "small_validation",
    "report_generation",
]


def _now_iso() -> str:
    return datetime.now(CHINA_TZ).isoformat()


def get_stage_meta(stage_exec: PipelineStageExecution) -> Dict[str, Any]:
    meta = stage_exec.extra_metadata if isinstance(stage_exec.extra_metadata, dict) else {}
    return meta


def get_effective_output(
    stage_exec: PipelineStageExecution,
    use_human_modified: bool = True,
) -> Optional[Dict[str, Any]]:
    meta = get_stage_meta(stage_exec)
    if use_human_modified and meta.get("human_modified_output") is not None:
        return meta["human_modified_output"]
    return stage_exec.output_data


class StageHumanLoopService:
    def __init__(self, db: Session):
        self.db = db

    def save_human_edit(
        self,
        run_id: str,
        stage: str,
        output_data: Dict[str, Any],
        human_feedback: str = "",
        mark_reviewed: bool = True,
        editor: str = "user",
    ) -> PipelineStageExecution:
        run = self._get_run(run_id)
        stage_enum = PipelineStage(stage)
        stage_exec = (
            self.db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == run.id,
                PipelineStageExecution.stage == stage_enum,
            )
            .first()
        )
        if not stage_exec:
            raise ValueError(f"阶段 {stage} 不存在于 run {run_id}")

        meta = get_stage_meta(stage_exec)
        history: List[Dict[str, Any]] = list(meta.get("revision_history") or [])
        history.append(
            {
                "id": str(uuid.uuid4()),
                "at": _now_iso(),
                "editor": editor,
                "action": "human_edit",
                "previous_output": copy.deepcopy(stage_exec.output_data),
                "previous_human_output": copy.deepcopy(meta.get("human_modified_output")),
                "new_output": copy.deepcopy(output_data),
                "feedback": human_feedback,
            }
        )

        meta["human_modified_output"] = output_data
        meta["human_reviewed"] = mark_reviewed
        meta["human_feedback"] = human_feedback
        meta["edited_at"] = _now_iso()
        meta["revision_history"] = history[-30:]

        stage_exec.extra_metadata = meta
        if mark_reviewed:
            stage_exec.status = PipelineStatus.HUMAN_REVIEW_REQUIRED
        stage_exec.updated_at = datetime.now(CHINA_TZ)
        self.db.commit()
        self.db.refresh(stage_exec)
        return stage_exec

    def get_stage_detail(self, run_id: str, stage: str) -> Dict[str, Any]:
        run = self._get_run(run_id)
        stage_enum = PipelineStage(stage)
        stage_exec = (
            self.db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == run.id,
                PipelineStageExecution.stage == stage_enum,
            )
            .first()
        )
        if not stage_exec:
            raise ValueError(f"阶段 {stage} 不存在")
        meta = get_stage_meta(stage_exec)
        return {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "stage": stage,
            "status": stage_exec.status.value if hasattr(stage_exec.status, "value") else str(stage_exec.status),
            "input_data": stage_exec.input_data,
            "output_data": stage_exec.output_data,
            "human_modified_output": meta.get("human_modified_output"),
            "human_reviewed": meta.get("human_reviewed", False),
            "human_feedback": meta.get("human_feedback"),
            "edited_at": meta.get("edited_at"),
            "revision_history": meta.get("revision_history") or [],
            "prompt_used": stage_exec.prompt_used,
            "model_used": stage_exec.model_used,
        }

    def seed_results_from_run(
        self,
        parent_run: PipelineRun,
        start_stage: str,
        use_human_modified_output: bool = True,
    ) -> Dict[str, Any]:
        start_idx = STAGE_KEY_ORDER.index(start_stage)
        results: Dict[str, Any] = {}
        stages = (
            self.db.query(PipelineStageExecution)
            .filter(PipelineStageExecution.pipeline_run_id == parent_run.id)
            .order_by(PipelineStageExecution.stage_order)
            .all()
        )
        stage_map = {s.stage.value if hasattr(s.stage, "value") else str(s.stage): s for s in stages}
        for key in STAGE_KEY_ORDER[:start_idx]:
            exec_row = stage_map.get(key)
            if not exec_row:
                continue
            effective = get_effective_output(exec_row, use_human_modified_output)
            if effective is not None:
                results[key] = effective
        parent_meta = parent_run.extra_metadata if isinstance(parent_run.extra_metadata, dict) else {}
        aux = parent_meta.get("auxiliary_results") or {}
        parent_output = parent_run.output_data if isinstance(parent_run.output_data, dict) else {}
        for k in ("data_finder", "knowledge_graph", "evidence_reasoning"):
            if k in aux:
                results[k] = aux[k]
            elif k in parent_output:
                results[k] = parent_output[k]
        return results

    def _get_run(self, run_id: str) -> PipelineRun:
        run = self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            run = self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            raise ValueError(f"Pipeline run 未找到: {run_id}")
        return run


def get_stage_human_loop_service(db: Session) -> StageHumanLoopService:
    return StageHumanLoopService(db)
