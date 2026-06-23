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
    "data_acquisition",
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

    def collect_feedback_constraints(self, run_id: str) -> List[str]:
        """汇总各阶段 human_feedback 为下一轮约束。"""
        run = self._get_run(run_id)
        stages = (
            self.db.query(PipelineStageExecution)
            .filter(PipelineStageExecution.pipeline_run_id == run.id)
            .order_by(PipelineStageExecution.stage_order)
            .all()
        )
        out: List[str] = []
        for stage_exec in stages:
            meta = get_stage_meta(stage_exec)
            fb = (meta.get("human_feedback") or "").strip()
            if not fb:
                continue
            stage_key = stage_exec.stage.value if hasattr(stage_exec.stage, "value") else str(stage_exec.stage)
            out.append(f"阶段「{stage_key}」人工反馈: {fb}")
        return out[:10]

    def get_hitl_gate_status(self, run_id: str) -> Dict[str, Any]:
        run = self._get_run(run_id)
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        gate = meta.get("hitl_gate") or {}
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        paused = bool(gate.get("paused")) or status_val == PipelineStatus.HUMAN_REVIEW_REQUIRED.value
        return {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "status": status_val,
            "paused": paused,
            "stage": gate.get("stage"),
            "stage_label": gate.get("stage_label"),
            "resume_phase": gate.get("resume_phase"),
            "paused_at": gate.get("paused_at"),
            "cleared_stages": gate.get("cleared_stages") or [],
        }

    def resume_hitl_gate(
        self,
        run_id: str,
        action: str,
        human_feedback: str = "",
        inject_feedback: bool = True,
    ) -> Dict[str, Any]:
        run = self._get_run(run_id)
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        gate = dict(meta.get("hitl_gate") or {})
        stage = gate.get("stage")

        if run.status != PipelineStatus.HUMAN_REVIEW_REQUIRED and not gate.get("paused"):
            raise ValueError("Pipeline 未处于 HITL Gate 暂停状态")

        if action == "abort":
            run.status = PipelineStatus.CANCELLED
            gate["paused"] = False
            gate["last_action"] = "abort"
            gate["aborted_at"] = _now_iso()
            meta["hitl_gate"] = gate
            run.extra_metadata = meta
            run.current_stage = None
            self.db.commit()
            return {"action": "abort", "status": "cancelled", "run_id": run.run_id}

        if action == "rerun":
            if not stage:
                raise ValueError("无法重跑：缺少 gate stage")
            gate["paused"] = False
            gate["last_action"] = "rerun"
            meta["hitl_gate"] = gate
            run.extra_metadata = meta
            self.db.commit()
            return {
                "action": "rerun",
                "status": "rerun_requested",
                "run_id": run.run_id,
                "rerun_from_stage": stage,
            }

        if action != "continue":
            raise ValueError(f"未知 action: {action}")

        constraints: List[str] = []
        if inject_feedback and human_feedback.strip():
            constraints.append(f"人工反馈（{stage or 'gate'}）: {human_feedback.strip()}")
        if inject_feedback:
            constraints.extend(self.collect_feedback_constraints(run_id))

        cleared = list(gate.get("cleared_stages") or [])
        if stage and stage not in cleared:
            cleared.append(stage)

        gate["cleared_stages"] = cleared
        gate["feedback_constraints"] = constraints
        gate["resumed"] = True
        gate["paused"] = False
        gate["last_action"] = "continue"
        gate["continued_at"] = _now_iso()
        if human_feedback.strip():
            gate["last_human_feedback"] = human_feedback.strip()

        meta["hitl_gate"] = gate
        run.status = PipelineStatus.RUNNING
        run.extra_metadata = meta
        self.db.commit()

        return {
            "action": "continue",
            "status": "running",
            "run_id": run.run_id,
            "feedback_constraints_count": len(constraints),
        }

    def _get_run(self, run_id: str) -> PipelineRun:
        run = self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            run = self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            raise ValueError(f"Pipeline run 未找到: {run_id}")
        return run


def get_stage_human_loop_service(db: Session) -> StageHumanLoopService:
    return StageHumanLoopService(db)
