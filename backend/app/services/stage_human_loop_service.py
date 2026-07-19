"""阶段人工审阅、编辑与修订历史"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.pipeline_modes import HITL_GATE_STAGE_LABELS
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
    "iterative_experiment",
    "report_generation",
]

STAGE_LABELS_ZH = {
    "problem_understanding": "问题理解",
    "literature_mining": "文献挖掘",
    "knowledge_gap": "知识缺口",
    "hypothesis_generation": "假设生成",
    "hypothesis_review": "假设评审",
    "iterative_experiment": "迭代实验",
    "experiment_design": "迭代实验",  # 历史 run 展示别名
    "small_validation": "迭代实验",  # 历史 run 展示别名
    "report_generation": "报告生成",
}


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
        action: str = "human_edit",
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
                "action": action,
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
        meta["human_edited"] = True
        meta["revision_history"] = history[-30:]

        stage_exec.extra_metadata = meta
        # 人工修订不覆盖已完成阶段的 status，避免左侧节点误显示为「待上传数据」
        if mark_reviewed and stage_exec.status not in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
            PipelineStatus.RUNNING,
        ):
            stage_exec.status = PipelineStatus.HUMAN_REVIEW_REQUIRED
        stage_exec.updated_at = datetime.now(CHINA_TZ)
        self.db.commit()
        self.db.refresh(stage_exec)

        if human_feedback.strip():
            self._record_feedback_hub(run.project_id, stage, human_feedback)

        if stage == PipelineStage.REPORT_GENERATION.value:
            try:
                from app.services.report_service import ReportService

                ReportService(self.db).sync_from_stage_human_output(
                    project_id=run.project_id,
                    run_id=run_id,
                    stage_output=output_data,
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "报告阶段人工修订同步 Report 表失败 run=%s: %s", run_id, exc
                )

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
        feedback_ctx = self._load_feedback_context(run.project_id)
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
            "human_edited": meta.get("human_edited", False),
            "revision_history": meta.get("revision_history") or [],
            "chat_history": meta.get("chat_history") or [],
            "prompt_used": stage_exec.prompt_used,
            "model_used": stage_exec.model_used,
            **feedback_ctx,
        }

    @staticmethod
    def _load_feedback_context(project_id: str) -> Dict[str, Any]:
        try:
            from app.services.feedback_hub_service import get_feedback_hub_service

            hub = get_feedback_hub_service()
            return {
                "global_constraints": hub.get_active_constraints(project_id),
                "recent_feedback_entries": hub.list_entries(project_id, limit=10),
            }
        except Exception:
            return {"global_constraints": [], "recent_feedback_entries": []}

    @staticmethod
    def _record_feedback_hub(project_id: str, stage: str, message: str, *, trigger_rerun: bool = False) -> None:
        try:
            from app.services.feedback_hub_service import get_feedback_hub_service

            get_feedback_hub_service().record_hitl_feedback(
                project_id,
                stage=stage,
                message=message,
                trigger_rerun=trigger_rerun,
            )
        except Exception:
            pass

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
        for k in ("data_finder", "evidence_reasoning"):
            if k in aux:
                results[k] = aux[k]
            elif k in parent_output:
                results[k] = parent_output[k]
        return results

    def summarize_downstream_context_for_rerun(
        self,
        parent_run: PipelineRun,
        from_stage: str,
    ) -> List[str]:
        """从重跑起点之后的父 run 阶段输出提取摘要，供早期阶段 Agent 感知当前项目进展。"""
        if from_stage not in STAGE_KEY_ORDER:
            return []
        start_idx = STAGE_KEY_ORDER.index(from_stage)
        stages = (
            self.db.query(PipelineStageExecution)
            .filter(PipelineStageExecution.pipeline_run_id == parent_run.id)
            .order_by(PipelineStageExecution.stage_order)
            .all()
        )
        stage_map = {
            s.stage.value if hasattr(s.stage, "value") else str(s.stage): s for s in stages
        }
        summaries: List[str] = []
        for key in STAGE_KEY_ORDER[start_idx + 1 :]:
            exec_row = stage_map.get(key)
            # 历史 run：旧实验阶段映射到迭代实验摘要槽
            if not exec_row and key == "iterative_experiment":
                exec_row = stage_map.get("experiment_design") or stage_map.get("small_validation")
            if not exec_row:
                continue
            output = get_effective_output(exec_row, use_human_modified=True)
            if not isinstance(output, dict) or not output:
                continue
            label = STAGE_LABELS_ZH.get(key, key)
            meta = get_stage_meta(exec_row)
            human_fb = (meta.get("human_feedback") or "").strip()

            if key == "hypothesis_generation":
                hyps = output.get("hypotheses") or []
                if hyps:
                    primary = (hyps[0].get("hypothesis") or "")[:220]
                    summaries.append(f"{label}: 已生成 {len(hyps)} 条假设，主假设「{primary}」")
            elif key == "hypothesis_review":
                score = output.get("overall_score") or output.get("ensemble_score")
                verdict = output.get("verdict") or output.get("recommendation")
                if score is not None or verdict:
                    summaries.append(f"{label}: 评分={score}，结论={verdict}")
            elif key == "iterative_experiment":
                status = output.get("status") or ""
                n_exp = len(output.get("experiments") or [])
                warn_list = output.get("warnings") or []
                warn = (
                    (output.get("warning") or output.get("summary") or "")
                    or ("; ".join(str(w) for w in warn_list[:3]) if isinstance(warn_list, list) else "")
                )[:160]
                if status or n_exp or warn:
                    summaries.append(
                        f"{label}: status={status or 'ok'}"
                        + (f"，实验数={n_exp}" if n_exp else "")
                        + (f"；{warn}" if warn else "")
                    )
            elif key == "literature_mining":
                facts_n = len(output.get("facts") or [])
                papers_n = len(output.get("retrieved_papers") or output.get("source_papers") or [])
                summaries.append(f"{label}: {facts_n} 条 facts，{papers_n} 篇文献")
            elif key == "data_acquisition":
                stats = (output.get("data_acquisition") or {}).get("stats") or {}
                summaries.append(
                    f"{label}: 外部候选 {stats.get('external_candidates', '?')}，"
                    f"表格 {stats.get('tables', '?')}"
                )
            elif key == "knowledge_gap":
                gaps = output.get("knowledge_gaps") or []
                if gaps:
                    summaries.append(f"{label}: {len(gaps)} 个缺口，首条「{str(gaps[0])[:120]}」")
            elif key == "report_generation":
                title = (output.get("title") or output.get("report_title") or "")[:120]
                if title:
                    summaries.append(f"{label}: {title}")

            if human_fb:
                summaries.append(f"{label}人工反馈: {human_fb[:300]}")

        return [f"[项目进展] {s}" for s in summaries[:12]]

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

    def _infer_gate_stage(self, run: PipelineRun, gate: Dict[str, Any]) -> Optional[str]:
        stage = gate.get("stage")
        if stage:
            return str(stage)
        if run.current_stage is not None:
            cs = run.current_stage.value if hasattr(run.current_stage, "value") else str(run.current_stage)
            return cs.lower()
        return None

    def _repair_hitl_gate(self, run: PipelineRun) -> Dict[str, Any]:
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        gate = dict(meta.get("hitl_gate") or {})
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        if status_val != PipelineStatus.HUMAN_REVIEW_REQUIRED.value and not gate.get("paused"):
            return gate

        stage = self._infer_gate_stage(run, gate)
        if stage and not gate.get("stage"):
            gate["stage"] = stage
            gate["stage_label"] = HITL_GATE_STAGE_LABELS.get(stage, stage)
            gate["resume_phase"] = f"after_{stage}"
            gate["paused"] = True
            meta["hitl_gate"] = gate
            run.extra_metadata = meta
            try:
                self.db.commit()
            except Exception:
                pass
        return gate

    def _repair_stuck_pre_resume_stages(self, run: PipelineRun, gate_stage: str) -> None:
        """HITL 继续前修复误从头重跑导致的 RUNNING 阶段（假设已生成场景）。"""
        if gate_stage != "hypothesis_generation":
            return
        stages = (
            self.db.query(PipelineStageExecution)
            .filter(PipelineStageExecution.pipeline_run_id == run.id)
            .order_by(PipelineStageExecution.stage_order)
            .all()
        )
        hg = next((s for s in stages if s.stage_order == 5), None)
        if not hg or hg.status != PipelineStatus.COMPLETED:
            return
        now = datetime.now(CHINA_TZ)
        changed = False
        for s in stages:
            if s.stage_order >= 6:
                continue
            if s.status != PipelineStatus.RUNNING:
                continue
            if s.output_data:
                s.status = PipelineStatus.COMPLETED
                if not s.completed_at:
                    s.completed_at = now
            else:
                s.status = PipelineStatus.FAILED
                s.error_message = "HITL 恢复：取消误启动的阶段"
                s.completed_at = now
            changed = True
        if changed:
            self.db.commit()

    def _ensure_hitl_checkpoint(self, run: PipelineRun, stage_key: str) -> Dict[str, Any]:
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        if stage_key not in STAGE_KEY_ORDER:
            return meta

        stage_idx = STAGE_KEY_ORDER.index(stage_key)
        if stage_idx + 1 >= len(STAGE_KEY_ORDER):
            return meta

        next_stage = STAGE_KEY_ORDER[stage_idx + 1]
        results = self.seed_results_from_run(run, next_stage)
        from app.services.data_finder_slim import slim_results_for_checkpoint

        meta["pipeline_checkpoint"] = {
            "results": slim_results_for_checkpoint(results),
            "resume_phase": f"after_{stage_key}",
        }
        run.extra_metadata = meta
        self.db.commit()
        return meta

    def get_hitl_gate_status(self, run_id: str) -> Dict[str, Any]:
        run = self._get_run(run_id)
        gate = self._repair_hitl_gate(run)
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
        stage = self._infer_gate_stage(run, gate)

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
            gate["stage"] = stage
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

        if not stage:
            raise ValueError("无法继续：缺少暂停阶段信息")

        gate["stage"] = stage
        gate.setdefault("stage_label", HITL_GATE_STAGE_LABELS.get(stage, stage))
        meta = self._ensure_hitl_checkpoint(run, stage)
        gate = dict(meta.get("hitl_gate") or gate)
        self._repair_stuck_pre_resume_stages(run, stage)

        next_stage_map = {
            "hypothesis_generation": "hypothesis_review",
            "hypothesis_review": "iterative_experiment",
            "iterative_experiment": "report_generation",
            "experiment_design": "report_generation",  # 历史 gate
            "small_validation": "report_generation",  # 历史 gate
        }
        run.current_stage = next_stage_map.get(stage, stage)

        constraints: List[str] = []
        if inject_feedback and human_feedback.strip():
            constraints.append(f"人工反馈（{stage}）: {human_feedback.strip()}")
            self._record_feedback_hub(run.project_id, stage, human_feedback)
        if inject_feedback:
            constraints.extend(self.collect_feedback_constraints(run_id))

        cleared = list(gate.get("cleared_stages") or [])
        if stage not in cleared:
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

    def select_evolved_hypothesis(
        self,
        run_id: str,
        *,
        candidate_id: Optional[str] = None,
        hypothesis_text: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """HITL 选用演化候选：写回 reviews[primary].hypothesis，并同步 checkpoint。"""
        run = self._get_run(run_id)
        stage_enum = PipelineStage.HYPOTHESIS_REVIEW
        stage_exec = (
            self.db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == run.id,
                PipelineStageExecution.stage == stage_enum,
            )
            .first()
        )
        if not stage_exec or not isinstance(stage_exec.output_data, dict):
            raise ValueError("假设评审阶段输出不存在")

        output = copy.deepcopy(stage_exec.output_data)
        skill_outputs = dict(output.get("skill_outputs") or {})
        evo = dict(skill_outputs.get("hypothesis_evolution") or {})
        candidates = list(evo.get("candidates") or [])

        chosen: Optional[Dict[str, Any]] = None
        if candidate_id:
            for c in candidates:
                if isinstance(c, dict) and c.get("candidate_id") == candidate_id:
                    chosen = c
                    break
            if not chosen:
                raise ValueError(f"未找到演化候选: {candidate_id}")
        elif hypothesis_text and str(hypothesis_text).strip():
            chosen = {
                "candidate_id": candidate_id or "evo_manual",
                "strategy": strategy or "manual",
                "hypothesis": str(hypothesis_text).strip(),
            }
        else:
            raise ValueError("请提供 candidate_id 或 hypothesis_text")

        new_text = str(chosen.get("hypothesis") or "").strip()
        if not new_text:
            raise ValueError("候选假设文本为空")

        reviews = list(output.get("reviews") or [])
        if not reviews:
            raise ValueError("评审结果中无 reviews")
        try:
            primary_idx = int(output.get("primary_index") or 0)
        except (TypeError, ValueError):
            primary_idx = 0
        primary_idx = min(max(0, primary_idx), len(reviews) - 1)
        prev = ""
        if isinstance(reviews[primary_idx], dict):
            prev = str(reviews[primary_idx].get("hypothesis") or "")
            reviews[primary_idx] = dict(reviews[primary_idx])
            reviews[primary_idx]["hypothesis"] = new_text
        else:
            reviews[primary_idx] = {"hypothesis": new_text}
        output["reviews"] = reviews

        evo["selected_candidate_id"] = chosen.get("candidate_id")
        evo["selected_strategy"] = chosen.get("strategy") or strategy
        evo["selected_at"] = _now_iso()
        evo["default_unchanged"] = False
        evo["previous_primary_hypothesis"] = prev
        skill_outputs["hypothesis_evolution"] = evo
        output["skill_outputs"] = skill_outputs

        # 写入人工修订版本（get_effective_output 优先）并同步 stage output
        self.save_human_edit(
            run_id=run.run_id,
            stage=PipelineStage.HYPOTHESIS_REVIEW.value,
            output_data=output,
            human_feedback=f"采用演化候选 {chosen.get('candidate_id')}（{chosen.get('strategy')}）",
            mark_reviewed=True,
            editor="user",
            action="select_evolved_hypothesis",
        )
        stage_exec = (
            self.db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == run.id,
                PipelineStageExecution.stage == stage_enum,
            )
            .first()
        )
        if stage_exec:
            stage_exec.output_data = output
            self.db.commit()

        # 同步 pipeline_checkpoint.results
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        checkpoint = dict(meta.get("pipeline_checkpoint") or {})
        results = dict(checkpoint.get("results") or {})
        results["hypothesis_review"] = output
        checkpoint["results"] = results
        meta["pipeline_checkpoint"] = checkpoint
        run.extra_metadata = meta
        self.db.commit()

        return {
            "run_id": run.run_id,
            "stage": PipelineStage.HYPOTHESIS_REVIEW.value,
            "selected_candidate_id": chosen.get("candidate_id"),
            "strategy": chosen.get("strategy") or strategy,
            "primary_index": primary_idx,
            "hypothesis": new_text,
            "previous_hypothesis": prev,
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
