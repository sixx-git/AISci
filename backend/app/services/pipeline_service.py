"""
Pipeline 服务 - 负责按顺序执行各个 Agent
v3 - 修复 detail->payload 参数名 (force reload)
"""
import copy
import uuid
import json
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

CHINA_TZ = timezone(timedelta(hours=8))

from app.agents.problem_understanding_agent import (
    get_problem_understanding_agent,
    build_scientific_logic_constraints,
    resolve_research_question_from_pu,
)
from app.agents.literature_mining_agent import get_literature_mining_agent
from app.agents.knowledge_gap_agent import get_knowledge_gap_agent
from app.agents.hypothesis_generation_agent import get_hypothesis_generation_agent
from app.agents.hypothesis_review_agent import get_hypothesis_review_agent
from app.agents.report_generation_agent import get_report_generation_agent

from app.models.pipeline import (
    PipelineRun as DB_PipelineRun,
    PipelineStageExecution as DB_PipelineStageExecution,
    PipelineStatus as DB_PipelineStatus,
    PipelineStage as DB_PipelineStage
)
from app.models.project import Report, Project, ProjectStatus
from app.core.project_modes import ProjectMode, normalize_project_mode
from app.core.pipeline_modes import (
    PipelineMode,
    normalize_pipeline_mode,
    resolve_run_options,
    ENSEMBLE_ACCEPT_SCORE,
    HITL_GATE_STAGE_LABELS,
)
from app.core.pipeline_exceptions import HitlGatePause, SingleStageRerunComplete, LiteratureNotFoundError
from app.core.quality_scoring import enrich_quality_trend_entry
from app.services.loops.closed_loop_helpers import infer_quality_trend_entries
from app.core.execution_metadata import annotate_validation_execution_metadata
from app.services.hypothesis_service import HypothesisService
from app.services.qwen_client import get_call_logs, clear_call_logs, CallLog
from app.services.prompt_context import set_project_id as set_prompt_project_id
from app.services.stage_human_loop_service import STAGE_KEY_ORDER, StageHumanLoopService, get_effective_output, get_stage_meta
from app.services.report_service import merge_report_extra_metadata
from app.services.prompt_override_service import get_prompt_override_service

from app.schemas.pipeline import (
    PipelineStatus,
    PipelineStage,
    PipelineStageStatus,
    PipelineStageLog,
    PipelineRunRequest,
    PipelineRunResult
)

logger = logging.getLogger(__name__)

# 阶段定义：名称 → Schema
STAGE_DEFS: List[Dict[str, Any]] = [
    {"idx": 0, "key": "problem_understanding", "stage_enum": PipelineStage.PROBLEM_UNDERSTANDING,
     "db_stage_enum": DB_PipelineStage.PROBLEM_UNDERSTANDING, "label": "问题理解"},
    {"idx": 1, "key": "literature_mining", "stage_enum": PipelineStage.LITERATURE_MINING,
     "db_stage_enum": DB_PipelineStage.LITERATURE_MINING, "label": "文献挖掘"},
    {"idx": 2, "key": "knowledge_gap", "stage_enum": PipelineStage.KNOWLEDGE_GAP,
     "db_stage_enum": DB_PipelineStage.KNOWLEDGE_GAP, "label": "知识缺口"},
    {"idx": 3, "key": "hypothesis_generation", "stage_enum": PipelineStage.HYPOTHESIS_GENERATION,
     "db_stage_enum": DB_PipelineStage.HYPOTHESIS_GENERATION, "label": "假设生成"},
    {"idx": 4, "key": "hypothesis_review", "stage_enum": PipelineStage.HYPOTHESIS_REVIEW,
     "db_stage_enum": DB_PipelineStage.HYPOTHESIS_REVIEW, "label": "假设评估"},
    {"idx": 5, "key": "iterative_experiment", "stage_enum": PipelineStage.ITERATIVE_EXPERIMENT,
     "db_stage_enum": DB_PipelineStage.ITERATIVE_EXPERIMENT, "label": "迭代实验"},
    {"idx": 6, "key": "report_generation", "stage_enum": PipelineStage.REPORT_GENERATION,
     "db_stage_enum": DB_PipelineStage.REPORT_GENERATION, "label": "报告生成"},
]


class PipelineService:
    """Pipeline 服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.run_id = str(uuid.uuid4())
        self.db_pipeline_run: Optional[DB_PipelineRun] = None
        self.db_stage_executions: Dict[int, DB_PipelineStageExecution] = {}
        self._stage_results: Dict[str, Any] = {}
        self._pipeline_start: Optional[datetime] = None
        self._start_idx: int = 0
        self._seeded_results: Optional[Dict[str, Any]] = None
        self._run_options: Dict[str, Any] = {}
        self._discovery_refinement: List[str] = []
        self._validation_feedback_constraints: List[str] = []
        self._human_feedback_constraints: List[str] = []
        self._checkpoint_resume: Optional[Dict[str, Any]] = None
        self._checkpoint_was_loaded: bool = False
        self._finalize_report_after_gate: bool = False
        self._skip_to_post_validation: bool = False
        self._last_pilot_results: Dict[str, Any] = {}
        self._experiment_correction_count: int = 0
        self._federated_campaign_count: int = 0
        self._fed_campaign_discovery_done: set = set()
        self._iteration_snapshots: List[Dict[str, Any]] = []
        self._executability_blocked: bool = False
        # ── 大家长 Agent (CoordinatorAgent) ──
        self._coordinator = None  # 延迟初始化，避免循环导入
        self._coordinator_hints: List[Dict[str, Any]] = []

    def _apply_executability_gate(
        self,
        results: Dict[str, Any],
        project_id: str,
        round_num: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Batch4: 实验设计后检查计划相对数据的可执行性。"""
        ed = results.get("experiment_design") or {}
        if not ed:
            return {}
        from app.core.plan_executability import assess_plan_executability

        data_context = self._build_data_context(project_id) if project_id else {}
        gate = assess_plan_executability(ed, data_context)
        ed["executability_gate"] = gate
        results["experiment_design"] = ed

        passed = bool(gate.get("passed"))
        self._executability_blocked = not passed
        if not self._run_options.get("enable_executability_gate", True):
            self._executability_blocked = False
            passed = True

        blockers = gate.get("blockers") or gate.get("warnings") or []
        reason = "可执行性通过" if passed else "; ".join(blockers[:3]) or "可执行性不足"
        self._record_closed_loop_decision(
            trigger="experiment_design_complete",
            action="proceed_validation" if passed else "block_validation",
            reason=reason[:300],
            next_stage="small_validation" if passed else "experiment_design_replan",
            round_num=round_num,
            metadata={
                "score": gate.get("score"),
                "missing_columns": gate.get("missing_columns"),
            },
        )
        return gate

    def _persist_audit_record(self, record_type: str, payload: Dict[str, Any]) -> None:
        if not self.db_pipeline_run:
            return
        try:
            from app.services.audit_chain_service import get_audit_chain_service

            get_audit_chain_service().append_record(
                self.db_pipeline_run.run_id,
                record_type,
                payload,
                project_id=self.db_pipeline_run.project_id,
            )
        except Exception:
            pass

    def _record_closed_loop_decision(
        self,
        *,
        trigger: str,
        action: str,
        reason: str,
        actor: str = "auto",
        next_stage: Optional[str] = None,
        round_num: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.db_pipeline_run:
            return
        from app.core.closed_loop_decisions import append_closed_loop_decision

        meta = (
            self.db_pipeline_run.extra_metadata
            if isinstance(self.db_pipeline_run.extra_metadata, dict)
            else {}
        )
        decisions = list(meta.get("closed_loop_decisions") or [])
        append_closed_loop_decision(
            decisions,
            trigger=trigger,
            action=action,
            reason=reason,
            actor=actor,
            next_stage=next_stage,
            round_num=round_num,
            metadata=metadata,
        )
        meta["closed_loop_decisions"] = decisions[-30:]
        self.db_pipeline_run.extra_metadata = meta
        if decisions:
            self._persist_audit_record("closed_loop_decision", decisions[-1])
        try:
            self.db.commit()
        except Exception:
            pass

    def start_pipeline_async(self, request: PipelineRunRequest) -> str:
        """
        异步启动 Pipeline：创建运行记录和初始阶段记录，立即返回 run_id。

        Args:
            request: Pipeline 运行请求

        Returns:
            str: run_id
        """
        logger.info(f"异步启动 Pipeline: {self.run_id}, 项目: {request.project_id}")

        self._create_pipeline_run(request)

        for idx, d in enumerate(STAGE_DEFS):
            db_stage = DB_PipelineStageExecution(
                id=str(uuid.uuid4()),
                pipeline_run_id=self.db_pipeline_run.id,
                stage=d["db_stage_enum"],
                stage_order=idx + 1,
                status=DB_PipelineStatus.PENDING,
                started_at=None,
                completed_at=None,
                duration_ms=None,
            )
            self.db.add(db_stage)
            self.db_stage_executions[idx + 1] = db_stage
        self.db.commit()

        return self.run_id

    def start_rerun_from_stage(
        self,
        project_id: str,
        parent_run_id: str,
        from_stage: str,
        use_human_modified_output: bool = True,
        rerun_mode: str = "single_stage",
        human_feedback: str = "",
        run_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """从指定阶段重新运行：single_stage 原地更新同一 run；from_stage_onward 分叉新 run。"""
        if rerun_mode not in ("single_stage", "from_stage_onward"):
            raise ValueError(f"无效 rerun_mode: {rerun_mode}")
        if rerun_mode == "single_stage":
            return self._prepare_in_place_single_stage_rerun(
                project_id=project_id,
                run_id=parent_run_id,
                from_stage=from_stage,
                use_human_modified_output=use_human_modified_output,
                human_feedback=human_feedback,
                run_options=run_options,
            )
        return self._prepare_fork_rerun_from_stage(
            project_id=project_id,
            parent_run_id=parent_run_id,
            from_stage=from_stage,
            use_human_modified_output=use_human_modified_output,
            human_feedback=human_feedback,
            run_options=run_options,
        )

    @staticmethod
    def _archive_stage_output_for_rerun(stage_exec: DB_PipelineStageExecution, from_stage: str) -> None:
        meta = get_stage_meta(stage_exec)
        history: List[Dict[str, Any]] = list(meta.get("revision_history") or [])
        history.append(
            {
                "id": str(uuid.uuid4()),
                "at": datetime.now(CHINA_TZ).isoformat(),
                "editor": "system",
                "action": "agent_rerun",
                "stage": from_stage,
                "previous_output": copy.deepcopy(stage_exec.output_data),
                "previous_human_output": copy.deepcopy(meta.get("human_modified_output")),
            }
        )
        meta["revision_history"] = history[-30:]
        stage_exec.extra_metadata = meta
        flag_modified(stage_exec, "extra_metadata")

    @staticmethod
    def _merge_run_input_options(
        input_data: Optional[Dict[str, Any]],
        run_options: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """合并 / 覆盖 Pipeline input_data.options（用于重跑时关闭红蓝对抗等）。"""
        merged = dict(input_data or {})
        if run_options is None:
            return merged
        prev = merged.get("options") if isinstance(merged.get("options"), dict) else {}
        merged["options"] = {**prev, **dict(run_options)}
        return merged

    def _prepare_in_place_single_stage_rerun(
        self,
        project_id: str,
        run_id: str,
        from_stage: str,
        use_human_modified_output: bool = True,
        human_feedback: str = "",
        run_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        stage_aliases = {"data_acquisition": "knowledge_gap"}
        from_stage = stage_aliases.get(from_stage, from_stage)
        if from_stage not in STAGE_KEY_ORDER:
            raise ValueError(f"无效 stage: {from_stage}")

        run = self.db.query(DB_PipelineRun).filter(DB_PipelineRun.run_id == run_id).first()
        if not run:
            raise ValueError(f"run 未找到: {run_id}")
        if run.project_id != project_id:
            raise ValueError("project_id 与 run 不匹配")

        if run_options is not None:
            run.input_data = self._merge_run_input_options(
                run.input_data if isinstance(run.input_data, dict) else {},
                run_options,
            )
            flag_modified(run, "input_data")

        start_idx = STAGE_KEY_ORDER.index(from_stage)
        human_loop = StageHumanLoopService(self.db)
        stage_rows = (
            self.db.query(DB_PipelineStageExecution)
            .filter(DB_PipelineStageExecution.pipeline_run_id == run.id)
            .order_by(DB_PipelineStageExecution.stage_order)
            .all()
        )
        stage_map = {
            (s.stage.value if hasattr(s.stage, "value") else str(s.stage)): s for s in stage_rows
        }
        target_exec = stage_map.get(from_stage)
        if not target_exec:
            raise ValueError(f"阶段 {from_stage} 不存在于 run {run_id}")

        if target_exec.output_data is not None or get_stage_meta(target_exec).get("human_modified_output") is not None:
            self._archive_stage_output_for_rerun(target_exec, from_stage)

        target_exec.status = DB_PipelineStatus.PENDING
        target_exec.started_at = None
        target_exec.completed_at = None
        target_exec.duration_ms = None
        target_exec.error_message = None
        target_exec.output_data = None

        feedback_constraints: List[str] = []
        downstream_ctx = human_loop.summarize_downstream_context_for_rerun(run, from_stage)
        for c in downstream_ctx:
            if c and c not in feedback_constraints:
                feedback_constraints.append(c)
        if human_feedback and human_feedback.strip():
            feedback_constraints.append(human_feedback.strip())
            try:
                from app.services.feedback_hub_service import get_feedback_hub_service

                get_feedback_hub_service(self.db).record_hitl_feedback(
                    project_id,
                    stage=from_stage,
                    message=human_feedback.strip(),
                    trigger_rerun=True,
                )
            except Exception as fb_err:
                logger.warning("[Rerun] Feedback Hub 记录失败: %s", fb_err)

        run.version = (run.version or 1) + 1
        run.status = DB_PipelineStatus.PENDING
        meta = dict(run.extra_metadata or {})
        meta.update(
            {
                "rerun_from_stage": from_stage,
                "rerun_mode": "single_stage",
                "in_place_rerun": True,
                "use_human_modified_output": use_human_modified_output,
                "feedback_constraints": feedback_constraints,
                "rerun_downstream_context": downstream_ctx,
                "downstream_stale_from": from_stage,
            }
        )
        # 从可行性评估 handoff 进入「生成报告」时清除暂停态
        gate = dict(meta.get("hitl_gate") or {})
        if gate.get("paused"):
            cleared = list(gate.get("cleared_stages") or [])
            if from_stage == "report_generation" and "hypothesis_review" not in cleared:
                cleared.append("hypothesis_review")
            gate["paused"] = False
            gate["cleared_stages"] = cleared
            gate["last_action"] = "report_generation"
            meta["hitl_gate"] = gate
        meta.pop("parent_run_id", None)
        run.extra_metadata = meta
        flag_modified(run, "extra_metadata")

        for idx in range(start_idx + 1, len(STAGE_DEFS)):
            key = STAGE_DEFS[idx]["key"]
            downstream_exec = stage_map.get(key)
            if not downstream_exec:
                continue
            ds_meta = get_stage_meta(downstream_exec)
            ds_meta["stale_after_upstream_rerun"] = from_stage
            downstream_exec.extra_metadata = ds_meta
            flag_modified(downstream_exec, "extra_metadata")

        self.db.commit()
        self.run_id = run_id
        self.db_pipeline_run = run
        self._start_idx = start_idx
        self._seeded_results = human_loop.seed_results_from_run(run, from_stage, use_human_modified_output)
        self._rerun_single_stage_only = True
        self._in_place_rerun = True
        self._parent_run_id_for_rerun = None
        for s in stage_rows:
            self.db_stage_executions[s.stage_order] = s
        logger.info(
            "[Pipeline] 单阶段原地重跑已准备 run_id=%s stage=%s version=%s",
            run_id,
            from_stage,
            run.version,
        )
        return run_id

    def _prepare_fork_rerun_from_stage(
        self,
        project_id: str,
        parent_run_id: str,
        from_stage: str,
        use_human_modified_output: bool = True,
        human_feedback: str = "",
        run_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        stage_aliases = {"data_acquisition": "knowledge_gap"}
        from_stage = stage_aliases.get(from_stage, from_stage)
        if from_stage not in STAGE_KEY_ORDER:
            raise ValueError(f"无效 stage: {from_stage}")

        parent = self.db.query(DB_PipelineRun).filter(DB_PipelineRun.run_id == parent_run_id).first()
        if not parent:
            raise ValueError(f"父 run 未找到: {parent_run_id}")
        if parent.project_id != project_id:
            raise ValueError("project_id 与 run 不匹配")

        start_idx = STAGE_KEY_ORDER.index(from_stage)
        self.run_id = str(uuid.uuid4())
        human_loop = StageHumanLoopService(self.db)
        seeded = human_loop.seed_results_from_run(parent, from_stage, use_human_modified_output)

        parent_stages = (
            self.db.query(DB_PipelineStageExecution)
            .filter(DB_PipelineStageExecution.pipeline_run_id == parent.id)
            .order_by(DB_PipelineStageExecution.stage_order)
            .all()
        )
        parent_stage_map = {
            (s.stage.value if hasattr(s.stage, "value") else str(s.stage)): s for s in parent_stages
        }

        version = (parent.version or 1) + 1
        feedback_constraints: List[str] = []
        downstream_ctx = human_loop.summarize_downstream_context_for_rerun(parent, from_stage)
        for c in downstream_ctx:
            if c and c not in feedback_constraints:
                feedback_constraints.append(c)
        if human_feedback and human_feedback.strip():
            feedback_constraints.append(human_feedback.strip())
            try:
                from app.services.feedback_hub_service import get_feedback_hub_service

                get_feedback_hub_service(self.db).record_hitl_feedback(
                    project_id,
                    stage=from_stage,
                    message=human_feedback.strip(),
                    trigger_rerun=True,
                )
            except Exception as fb_err:
                logger.warning("[Rerun] Feedback Hub 记录失败: %s", fb_err)

        parent_input = parent.input_data if isinstance(parent.input_data, dict) else {}
        child_input = {
            **parent_input,
            "rerun_from": from_stage,
            "parent_run_id": parent_run_id,
        }
        child_input = self._merge_run_input_options(child_input, run_options)

        self.db_pipeline_run = DB_PipelineRun(
            id=str(uuid.uuid4()),
            run_id=self.run_id,
            project_id=project_id,
            research_question=parent.research_question,
            status=DB_PipelineStatus.PENDING,
            input_data=child_input,
            version=version,
            extra_metadata={
                "parent_run_id": parent_run_id,
                "rerun_from_stage": from_stage,
                "rerun_mode": "from_stage_onward",
                "in_place_rerun": False,
                "use_human_modified_output": use_human_modified_output,
                "feedback_constraints": feedback_constraints,
                "rerun_downstream_context": downstream_ctx,
                "auxiliary_results": {
                    k: v for k, v in seeded.items()
                    if k not in STAGE_KEY_ORDER
                },
            },
        )
        self.db.add(self.db_pipeline_run)
        self.db.flush()

        for idx, d in enumerate(STAGE_DEFS):
            order = idx + 1
            parent_exec = parent_stage_map.get(d["key"])
            if idx < start_idx and parent_exec:
                copied = DB_PipelineStageExecution(
                    id=str(uuid.uuid4()),
                    pipeline_run_id=self.db_pipeline_run.id,
                    stage=d["db_stage_enum"],
                    stage_order=order,
                    status=parent_exec.status,
                    started_at=parent_exec.started_at,
                    completed_at=parent_exec.completed_at,
                    duration_ms=parent_exec.duration_ms,
                    input_data=parent_exec.input_data,
                    output_data=parent_exec.output_data,
                    model_used=parent_exec.model_used,
                    model_parameters=parent_exec.model_parameters,
                    prompt_used=parent_exec.prompt_used,
                    token_count=parent_exec.token_count,
                    extra_metadata=parent_exec.extra_metadata,
                )
            else:
                copied = DB_PipelineStageExecution(
                    id=str(uuid.uuid4()),
                    pipeline_run_id=self.db_pipeline_run.id,
                    stage=d["db_stage_enum"],
                    stage_order=order,
                    status=DB_PipelineStatus.PENDING,
                )
            self.db.add(copied)
            self.db_stage_executions[order] = copied

        prompt_svc = get_prompt_override_service(self.db)
        overrides_used = {}
        for stage_key in STAGE_KEY_ORDER[start_idx:]:
            info = prompt_svc.get_prompt_info(project_id, stage_key)
            if info.get("has_override"):
                overrides_used[stage_key] = True
        self.db_pipeline_run.prompt_versions_used = {
            "overrides": overrides_used,
            "rerun_from_stage": from_stage,
            "parent_run_id": parent_run_id,
        }
        self.db.commit()
        self._start_idx = start_idx
        self._seeded_results = seeded
        self._rerun_single_stage_only = False
        self._in_place_rerun = False
        self._parent_run_id_for_rerun = parent_run_id
        return self.run_id

    def execute_pipeline_run(self, run_id: str):
        """
        在后台线程中执行完整 Pipeline（独立 DB Session）。

        Args:
            run_id: 已创建的 Pipeline 运行 ID
        """
        logger.info(f"[Pipeline] execute_pipeline_run 入口 run_id={run_id}")
        self.run_id = run_id

        self.db_pipeline_run = self.db.query(DB_PipelineRun).filter(
            DB_PipelineRun.run_id == run_id
        ).first()
        if not self.db_pipeline_run:
            logger.error(f"[Pipeline] 未找到 PipelineRun 记录 run_id={run_id}")
            return

        logger.info(f"[Pipeline] 找到 DB 记录 run_id={run_id} id={self.db_pipeline_run.id} status={self.db_pipeline_run.status}")

        research_question = self.db_pipeline_run.research_question or ""
        project_id = self.db_pipeline_run.project_id or ""

        existing_stages = (
            self.db.query(DB_PipelineStageExecution)
            .filter(DB_PipelineStageExecution.pipeline_run_id == self.db_pipeline_run.id)
            .order_by(DB_PipelineStageExecution.stage_order)
            .all()
        )
        for s in existing_stages:
            self.db_stage_executions[s.stage_order] = s

        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        if meta.get("in_place_rerun") and meta.get("rerun_from_stage"):
            self._start_idx = STAGE_KEY_ORDER.index(meta["rerun_from_stage"])
            self._seeded_results = StageHumanLoopService(self.db).seed_results_from_run(
                self.db_pipeline_run,
                meta["rerun_from_stage"],
                meta.get("use_human_modified_output", True),
            )
            self._rerun_single_stage_only = True
            self._in_place_rerun = True
            self._parent_run_id_for_rerun = None
            for c in meta.get("feedback_constraints") or []:
                if c and c not in self._human_feedback_constraints:
                    self._human_feedback_constraints.append(c)
            for c in meta.get("rerun_downstream_context") or []:
                if c and c not in self._human_feedback_constraints:
                    self._human_feedback_constraints.append(c)
        elif meta.get("rerun_from_stage"):
            self._start_idx = STAGE_KEY_ORDER.index(meta["rerun_from_stage"])
            parent_id = meta.get("parent_run_id")
            parent = (
                self.db.query(DB_PipelineRun).filter(DB_PipelineRun.run_id == parent_id).first()
                if parent_id else None
            )
            if parent:
                self._seeded_results = StageHumanLoopService(self.db).seed_results_from_run(
                    parent,
                    meta["rerun_from_stage"],
                    meta.get("use_human_modified_output", True),
                )
            self._rerun_single_stage_only = meta.get("rerun_mode", "single_stage") == "single_stage"
            self._in_place_rerun = False
            self._parent_run_id_for_rerun = parent_id
            for c in meta.get("feedback_constraints") or []:
                if c and c not in self._human_feedback_constraints:
                    self._human_feedback_constraints.append(c)
            for c in meta.get("rerun_downstream_context") or []:
                if c and c not in self._human_feedback_constraints:
                    self._human_feedback_constraints.append(c)

        gate = meta.get("hitl_gate") or {}
        cp = meta.get("pipeline_checkpoint")
        if isinstance(cp, dict) and cp.get("resume_phase") and not meta.get("rerun_from_stage"):
            self._checkpoint_resume = dict(cp)
            self._human_feedback_constraints = list(gate.get("feedback_constraints") or [])
            gate = dict(gate)
            gate["paused"] = False
            gate["resumed"] = False
            gate["checkpoint_consumed"] = True
            meta = dict(meta)
            meta["hitl_gate"] = gate
            self.db_pipeline_run.extra_metadata = meta
            flag_modified(self.db_pipeline_run, "extra_metadata")
            try:
                self.db.commit()
            except Exception:
                pass
            logger.info(
                "[Pipeline] 已加载 HITL checkpoint run_id=%s phase=%s",
                run_id,
                cp.get("resume_phase"),
            )

        set_prompt_project_id(project_id)
        self._run_pipeline_stages(research_question, project_id)

    def run_pipeline(self, request: PipelineRunRequest) -> PipelineRunResult:
        self.start_pipeline_async(request)
        return self._run_pipeline_stages(request.research_question, request.project_id)

    def _get_project_mode(self, project_id: str) -> str:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project:
            return normalize_project_mode(getattr(project, "project_mode", None))
        return ProjectMode.GENERAL.value

    def _get_run_options(self) -> Dict[str, Any]:
        input_data: Dict[str, Any] = {}
        if self.db_pipeline_run and isinstance(self.db_pipeline_run.input_data, dict):
            input_data = self.db_pipeline_run.input_data
        return resolve_run_options(input_data.get("options"))

    def _get_literature_top_k(self) -> int:
        try:
            return max(1, min(int(self._run_options.get("literature_max_papers", 10)), 30))
        except (TypeError, ValueError):
            return 10

    def _persist_extra_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """合并写入 extra_metadata（SQLite JSON 列需 flag_modified）。"""
        merged = dict(self.db_pipeline_run.extra_metadata or {})
        merged.update(meta)
        self.db_pipeline_run.extra_metadata = merged
        flag_modified(self.db_pipeline_run, "extra_metadata")
        return merged

    def _exec_ideation_novelty(
        self,
        problem_understanding: Optional[Dict],
        knowledge_gap: Optional[Dict],
    ) -> Dict[str, Any]:
        """P3: 假设生成前的 OpenAlex/S2 新颖性 ideation 预检。"""
        import asyncio
        from app.skills.reasoning.ideation_novelty_skill import IdeationNoveltySkill

        pu = problem_understanding or {}
        kg = knowledge_gap or {}
        rq = resolve_research_question_from_pu(
            pu,
            fallback=self.db_pipeline_run.research_question if self.db_pipeline_run else "",
        )
        keywords = pu.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        skill = IdeationNoveltySkill()
        skill_result = asyncio.run(
            skill.run(
                input_data={
                    "research_question": rq,
                    "knowledge_gaps": kg.get("knowledge_gaps") or kg.get("gaps") or [],
                    "keywords": keywords,
                    "num_ideas": self._run_options.get("num_ideas", 3),
                },
                context={"stage": "ideation_novelty"},
            )
        )
        return skill_result.data if skill_result.success else {}

    def _exec_counterfactual_preview(
        self,
        hypothesis_review: Optional[Dict[str, Any]],
        literature_mining: Optional[Dict[str, Any]],
        research_question: str = "",
    ) -> Dict[str, Any]:
        """L0 定性反事实预演（非独立阶段，失败不阻断 Pipeline）。"""
        import asyncio
        from app.skills.counterfactual.counterfactual_preview_skill import CounterfactualPreviewSkill

        skill = CounterfactualPreviewSkill()
        skill_result = asyncio.run(
            skill.run(
                input_data={
                    "hypothesis_review": hypothesis_review or {},
                    "literature_facts": (literature_mining or {}).get("facts") or [],
                    "research_question": research_question,
                },
                context={"stage": "counterfactual_preview", "research_question": research_question},
            )
        )
        return skill_result.data if skill_result.success else {}

    def _ensure_counterfactual_preview(
        self,
        results: Dict[str, Any],
        research_question: str,
    ) -> None:
        if not self._run_options.get("enable_counterfactual_preview", True):
            return
        if results.get("counterfactual_preview"):
            return
        hr = results.get("hypothesis_review") or {}
        if not (hr.get("reviews") or []):
            return
        try:
            preview = self._exec_counterfactual_preview(
                hr,
                results.get("literature_mining"),
                research_question,
            )
            if preview and not preview.get("skipped"):
                results["counterfactual_preview"] = preview
                self._stage_results["counterfactual_preview"] = preview
                self._record_closed_loop_event(
                    "counterfactual_preview",
                    {
                        "scenario_count": len(preview.get("scenarios") or []),
                        "proceed": preview.get("proceed_to_iterative_experiment", preview.get("proceed_to_experiment_design")),
                        "summary": (preview.get("summary") or "")[:200],
                    },
                )
        except Exception as exc:
            logger.warning("[CounterfactualPreview] 跳过: %s", exc)


    def _build_validation_feedback_constraints(
        self,
        small_validation: Optional[Dict[str, Any]],
        experiment_design: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """P0-1: 从沙箱/小样验证提取可注入下一轮假设与实验设计的约束。"""
        constraints: List[str] = []
        sv = small_validation or {}
        sb = sv.get("sandbox_execution") or {}
        if sb:
            if sb.get("success"):
                metrics = sb.get("metrics") or {}
                if metrics:
                    try:
                        metrics_text = json.dumps(metrics, ensure_ascii=False)[:400]
                    except (TypeError, ValueError):
                        metrics_text = str(metrics)[:400]
                    constraints.append(
                        f"上一轮沙箱实测成功，metrics={metrics_text}；请据此校准指标阈值与验证步骤。"
                    )
            else:
                err = (sb.get("stderr") or sb.get("stdout") or "")[:200]
                constraints.append(
                    f"上一轮沙箱执行失败(return_code={sb.get('return_code')})；"
                    f"错误摘要: {err}；请修订 analysis_script 与实验设计。"
                )

        actual = (sv.get("results") or {}).get("actual_results") or {}
        modeling = actual.get("modeling_result") or {}
        if isinstance(modeling, dict):
            for sug in (modeling.get("self_correction_suggestions") or [])[:3]:
                constraints.append(f"建模自校正建议: {sug}")

        pa = ((sv.get("skill_outputs") or {}).get("preliminary_analysis") or {}).get("data") or {}
        for anomaly in (pa.get("anomalies") or [])[:2]:
            constraints.append(f"预分析异常: {anomaly}")

        for w in (sv.get("warnings") or [])[:3]:
            constraints.append(f"验证警告: {w}")

        for fb in getattr(self, "_human_feedback_constraints", []) or []:
            if fb and fb not in constraints:
                constraints.append(fb)

        sv_replan = sv.get("replan_actions") or []
        if sv_replan:
            constraints.extend(actions_to_feedback_constraints(sv_replan))

        ed = experiment_design or {}
        sc = ((ed.get("skill_outputs") or {}).get("experiment_sanity_check") or {}).get("data") or {}
        if sc and sc.get("executable") is False:
            for rec in (sc.get("recommendations") or sc.get("missing_items") or [])[:3]:
                constraints.append(f"实验可执行性不足: {rec}")

        return constraints

    def _build_pilot_results_payload(self, small_validation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        sv = small_validation or {}
        sb = sv.get("sandbox_execution") or {}
        actual = (sv.get("results") or {}).get("actual_results") or {}
        return {
            "sandbox_success": sb.get("success"),
            "sandbox_metrics": sb.get("metrics"),
            "sandbox_stderr_preview": (sb.get("stderr") or "")[:300],
            "modeling_summary": (actual.get("modeling_result") or {}).get("summary"),
            "preliminary_summary": (
                ((sv.get("skill_outputs") or {}).get("preliminary_analysis") or {}).get("data") or {}
            ).get("summary"),
            "human_review_required": sv.get("human_review_required"),
        }

    def _get_science_iteration_orchestrator(self):
        from app.services.science_iteration_service import get_science_iteration_orchestrator
        return get_science_iteration_orchestrator(self.db, self)

    def _run_science_iteration_hooks(
        self,
        hook: str,
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        project_mode: str,
        stages: Optional[List[PipelineStageLog]] = None,
    ) -> Optional[Dict[str, Any]]:
        """统一观测层：仅记录里程碑与会话，不触发独立 refine 环。"""
        if not self._run_options.get("enable_science_iteration_observe", True):
            return None
        try:
            orch = self._get_science_iteration_orchestrator()
            if hook == "after_hypothesis_generation":
                orch.record_milestone(results, "initial", label="R1_initial")
            elif hook == "after_hypothesis_review":
                orch.record_milestone(results, "hypothesis_review", label="post_review")
            elif hook == "after_small_validation":
                sv = results.get("small_validation") or {}
                sb = sv.get("sandbox_execution") or {}
                if sb.get("success") is False:
                    orch.record_milestone(
                        results, "validation_fail",
                        actions=["sandbox_success=False"],
                    )
            elif hook == "finalize":
                meta = dict(self.db_pipeline_run.extra_metadata or {}) if self.db_pipeline_run else {}
                meta["iteration_mode"] = self._run_options.get("iteration_mode")
                if self.db_pipeline_run:
                    self._persist_extra_metadata(meta)
                return orch.finalize_session(results)
        except Exception as exc:
            logger.warning("[ScienceIteration] hook %s 失败: %s", hook, exc)
        return None

    def _capture_iteration_snapshot(self, round_num: int, results: Dict[str, Any], label: str = "") -> Dict[str, Any]:
        """P1-4: 捕获假设/计划版本快照供跨轮对比。"""
        hr = results.get("hypothesis_review") or {}
        reviews = hr.get("reviews") or []
        ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
        primary_idx = ensemble.get("target_hypothesis_index", hr.get("primary_index", 0))
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0
        primary_idx = min(max(0, primary_idx), len(reviews) - 1) if reviews else 0

        from app.services.iterative_experiment_service import resolve_ed_sv_from_results

        _, ed, sv = resolve_ed_sv_from_results(results)
        sb = sv.get("sandbox_execution") or {}
        fp = sv.get("federated_pilot") or {}

        hg = results.get("hypothesis_generation") or {}
        hypotheses = hg.get("hypotheses") or []
        primary_hypo: Dict[str, Any] = {}
        if hypotheses:
            pidx = primary_idx
            if pidx < len(hypotheses) and isinstance(hypotheses[pidx], dict):
                primary_hypo = hypotheses[pidx]
        from app.core.iterative_science import compute_evidence_provenance_summary

        prov = compute_evidence_provenance_summary(primary_hypo) if primary_hypo else {}
        vspec = (
            primary_hypo.get("verifiable_spec")
            or ed.get("verifiable_hypothesis")
            or hg.get("primary_verifiable_spec")
            or {}
        )

        hypo_text = (
            (reviews[primary_idx].get("hypothesis") if reviews else "")
            or str(primary_hypo.get("hypothesis") or "")
        )
        snapshot = {
            "round": round_num,
            "label": label or f"R{round_num}",
            "hypothesis": hypo_text,
            "hypothesis_full": hypo_text,
            "rationale_preview": ((reviews[primary_idx].get("rationale") or "")[:300] if reviews else ""),
            "experimental_steps_preview": (ed.get("experimental_steps") or "")[:500],
            "methods_preview": (ed.get("methods") or "")[:300],
            "ensemble_overall": ensemble.get("overall") or hr.get("ensemble_overall"),
            "ensemble_decision": ensemble.get("decision") or hr.get("ensemble_decision"),
            "sandbox_success": sb.get("success"),
            "sandbox_metrics": sb.get("metrics"),
            "federated_best_method": fp.get("best_method"),
            "federated_execution_mode": fp.get("execution_mode"),
            "federated_gate_passed": (fp.get("alignment_gate") or {}).get("passed"),
            "replan_action_count": len(fp.get("replan_actions") or []),
            "supporting_fact_count": prov.get("supporting_fact_count", 0),
            "supporting_fact_ids_sample": prov.get("supporting_fact_ids_sample") or [],
            "data_evidence_count": len(primary_hypo.get("data_evidence_ids") or []),
            "dataset_field_count": len(primary_hypo.get("dataset_field_refs") or []),
            "evidence_level": prov.get("evidence_level"),
            "verifiable_spec_summary": (vspec.get("claim") or "")[:200],
            "verifiable_primary_metric": vspec.get("primary_metric"),
        }
        self._iteration_snapshots.append(snapshot)
        return snapshot

    def _apply_post_validation_updates(self, results: Dict[str, Any], validation_result: Dict[str, Any]) -> None:
        """验证完成后：更新反馈约束、假设树 pilot 分。"""
        project_mode = self._get_project_mode(
            self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        )
        validation_result = annotate_validation_execution_metadata(
            validation_result, project_mode=project_mode
        )
        results["small_validation"] = validation_result

        from app.core.iterative_science import (
            evaluate_verifiable_spec_against_validation,
        )
        from app.services.iterative_experiment_service import resolve_ed_sv_from_results

        _, ed, _ = resolve_ed_sv_from_results(results)
        # 写回顶层旧键，供仍读 experiment_design 的下游兼容
        if ed and not results.get("experiment_design"):
            results["experiment_design"] = ed
        ie = results.get("iterative_experiment")
        if isinstance(ie, dict):
            ie = dict(ie)
            ie["small_validation"] = validation_result
            if ed and not ie.get("experiment_design"):
                ie["experiment_design"] = ed
            results["iterative_experiment"] = ie

        hg = results.get("hypothesis_generation") or {}
        vspec = (
            ed.get("verifiable_hypothesis")
            or hg.get("primary_verifiable_spec")
            or validation_result.get("verifiable_hypothesis")
        )
        if vspec:
            checks = evaluate_verifiable_spec_against_validation(validation_result, vspec)
            validation_result["verifiable_hypothesis"] = vspec
            validation_result["verifiable_checks"] = checks
            validation_result["verifiable_passed"] = (
                all(c.get("passed") for c in checks if c.get("check_id") == "sandbox_success")
                if any(c.get("check_id") == "sandbox_success" for c in checks)
                else all(c.get("passed") for c in checks[:3]) if checks else None
            )
            results["small_validation"] = validation_result

        from app.core.iterative_science import build_general_replan_actions

        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        data_context = self._build_data_context(project_id) if project_id else {}
        _, ed_for_replan, _ = resolve_ed_sv_from_results(results)
        replan_actions = build_general_replan_actions(
            ed_for_replan, validation_result, data_context
        )
        if replan_actions:
            validation_result["replan_actions"] = replan_actions
            results["small_validation"] = validation_result

        _, ed, _ = resolve_ed_sv_from_results(results)
        self._validation_feedback_constraints = self._build_validation_feedback_constraints(
            validation_result, ed
        )
        self._last_pilot_results = self._build_pilot_results_payload(validation_result)

        hg = results.get("hypothesis_generation") or {}
        tree = hg.get("hypothesis_tree")
        hypotheses = hg.get("hypotheses") or []
        if tree and isinstance(tree, dict):
            from app.services.hypothesis_tree_service import get_hypothesis_tree_service

            updated = get_hypothesis_tree_service().apply_pilot_feedback(
                tree, validation_result, hypotheses
            )
            hg["hypothesis_tree"] = updated
            results["hypothesis_generation"] = hg
            if updated.get("pilot_feedback_applied"):
                self._record_closed_loop_event(
                    "hypothesis_tree_pilot",
                    {
                        "round": len(self._iteration_snapshots),
                        "pilot_success": (validation_result.get("sandbox_execution") or {}).get("success"),
                        "selected_branch": updated.get("selected_branch_id"),
                        "quality_trend_entry": {
                            "stage": "pilot_feedback",
                            "score": updated["branches"][0]["pilot_score"]
                            if updated.get("branches") and updated["branches"][0].get("pilot_score") is not None
                            else (8.0 if (validation_result.get("sandbox_execution") or {}).get("success") else 3.0),
                        },
                    },
                )


    def _merge_science_iteration_run_options(self, project_id: str) -> None:
        """将 project.config.science_iteration 合并进 run_options。"""
        if not project_id:
            return
        try:
            from app.models.project import Project
            from app.services.science_iteration_service import resolve_science_iteration_config
            import json

            row = self.db.query(Project).filter(Project.id == project_id).first()
            pcfg: Dict[str, Any] = {}
            if row and row.config:
                pcfg = json.loads(row.config) if isinstance(row.config, str) else dict(row.config or {})
            sci = resolve_science_iteration_config(pcfg, self._run_options)
            if sci.enabled and "validation_fail" in (sci.auto_triggers or []):
                self._run_options["enable_experiment_self_correction"] = True
                self._run_options["experiment_self_correction_max"] = max(
                    int(self._run_options.get("experiment_self_correction_max") or 2),
                    int(sci.max_rounds or 2),
                )
        except Exception as exc:
            logger.warning("[Pipeline] science_iteration 配置合并失败: %s", exc)

    def _try_auto_gap_enrichment(self, project_id: str, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """数据缺口时尝试自动补搜/导入外部数据集。"""
        if not project_id:
            return None
        if not self._run_options.get("auto_gap_enrichment_on_data_gap", True):
            return None
        if not self._run_options.get("enable_gap_search", False):
            return None
        try:
            from app.services.data_finder_service import get_data_finder_service

            ed = results.get("experiment_design") or {}
            gaps = ed.get("data_gap") or (ed.get("data_requirements") or {}).get("gaps") or []
            queries = [str(g)[:120] for g in gaps[:4]]
            hr = results.get("hypothesis_review") or {}
            reviews = hr.get("reviews") or []
            if reviews and isinstance(reviews[0], dict):
                rq = reviews[0].get("required_data") or reviews[0].get("hypothesis") or ""
                if rq:
                    queries.insert(0, str(rq)[:200])
            enrichment = get_data_finder_service(self.db).run_gap_enrichment_sync(
                project_id=project_id,
                refinement_queries=queries,
                auto_import=bool(self._run_options.get("enable_hf_auto_import", True)),
                run_options=self._run_options,
                round_num=self._experiment_correction_count + 1,
            )
            if enrichment and not enrichment.get("skipped"):
                self._record_closed_loop_event(
                    "data_gap_enrichment",
                    {
                        "round": self._experiment_correction_count + 1,
                        "imported_count": (enrichment.get("import_meta") or {}).get("imported_count"),
                        "summary": enrichment.get("summary") or "gap enrichment",
                    },
                )
            return enrichment
        except Exception as exc:
            logger.warning("[Pipeline] 自动 gap enrichment 失败: %s", exc)
            return None


    def _apply_plot_quality_loop(
        self,
        result: Dict[str, Any],
        *,
        hypothesis: str = "",
        data_rows: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """P4: VLM/规则图表质量环。"""
        if not self._run_options.get("enable_plot_vlm_critique", True):
            return result
        plots = result.get("plots") or []
        artifacts = result.get("artifacts") or {}
        if not plots:
            sandbox_plots = artifacts.get("plots") or []
            actual = (result.get("results") or {}).get("actual_results") or {}
            plots = sandbox_plots or actual.get("sandbox_plots") or []
        if not plots:
            return result

        from app.services.plot_quality_loop_service import get_plot_quality_loop_service
        from app.services.experiment_sandbox_service import RUNS_ROOT

        output_dir = str(RUNS_ROOT / self.run_id / "plot_critique")
        loop = get_plot_quality_loop_service().run_quality_loop_sync(
            plots=plots,
            hypothesis=hypothesis,
            output_dir=output_dir,
            data_rows=data_rows,
        )
        result["plots"] = loop.get("plots") or plots
        result["plot_quality"] = {
            "critique": loop.get("critique"),
            "redraw_count": loop.get("redraw_count"),
            "needs_human_review": loop.get("needs_human_review"),
        }
        if loop.get("needs_human_review"):
            result["human_review_required"] = True
        avg = (loop.get("critique") or {}).get("average_score")
        if avg is not None:
            discovery_loop = (getattr(self, "_stage_results", None) or {}).get("discovery_loop") or {}
            self._record_closed_loop_event(
                "plot_vlm_critique",
                {
                    "round": discovery_loop.get("rounds_executed", 1),
                    "average_score": avg,
                    "needs_human_review": loop.get("needs_human_review"),
                    "quality_trend_entry": {"stage": "plot_critique", "score": avg},
                },
            )
        return result

    def _resume_phase_to_start_idx(self, resume_phase: str) -> int:
        # 与 STAGE_DEFS 下标对齐（0..6）；超出 len 表示后续不再执行
        mapping = {
            "after_hypothesis_generation": 4,
            "after_hypothesis_review": 5,
            "after_iterative_experiment": 6,
            # legacy 别名 → 报告阶段
            "after_experiment_design": 6,
            "after_small_validation": 6,
            "after_data_acquisition": 2,
            "after_report_generation": 7,
        }
        return mapping.get(resume_phase, 0)

    @staticmethod
    def _is_truncated_stage_output(output: Any) -> bool:
        return isinstance(output, dict) and output.get("_truncated") is True

    def _load_stage_output_from_db(self, stage_key: str) -> Optional[Dict[str, Any]]:
        for idx, d in enumerate(STAGE_DEFS):
            if d["key"] != stage_key:
                continue
            exec_row = self.db_stage_executions.get(idx + 1)
            if exec_row and exec_row.output_data and isinstance(exec_row.output_data, dict):
                if not self._is_truncated_stage_output(exec_row.output_data):
                    return exec_row.output_data
            break
        return None

    def _hydrate_hypothesis_generation(
        self,
        hypothesis_generation: Optional[Dict[str, Any]],
        project_id: str = "",
    ) -> Dict[str, Any]:
        """确保 hypothesis_generation 含 hypotheses（checkpoint 截断或缺失时从 DB 回填）。"""
        hg = dict(hypothesis_generation or {})
        if hg.get("hypotheses"):
            return hg

        db_out = self._load_stage_output_from_db("hypothesis_generation")
        if db_out and db_out.get("hypotheses"):
            hg.update(db_out)
            return hg

        if project_id and self.db:
            db_hypos = HypothesisService(self.db).get_hypotheses_by_project(project_id, limit=20)
            if db_hypos:
                hyps: List[Dict[str, Any]] = []
                for row in db_hypos:
                    sfi = row.supporting_fact_ids
                    if isinstance(sfi, str):
                        try:
                            sfi = json.loads(sfi)
                        except (TypeError, ValueError):
                            sfi = []
                    hyps.append({
                        "hypothesis": row.hypothesis,
                        "rationale": row.rationale or "",
                        "novelty": row.novelty or "",
                        "testability": row.testability or "",
                        "required_data": row.required_data or "",
                        "possible_method": row.possible_method or "",
                        "risk": row.risk or "",
                        "supporting_fact_ids": sfi or [],
                        "evidence_level": row.evidence_level or "medium",
                        "validation_target": row.validation_target or "",
                        "expected_measurable_effect": row.expected_measurable_effect or "",
                    })
                hg["hypotheses"] = hyps
                if db_out:
                    hg.setdefault("alignment", db_out.get("alignment"))
                    hg.setdefault("summary", db_out.get("summary"))
        return hg

    def _repair_checkpoint_results(self, results: Dict[str, Any], start_idx: int) -> int:
        """HITL checkpoint 恢复后修复截断阶段输出，必要时回退 start_idx 以重跑失败阶段。"""
        for idx in range(min(start_idx, len(STAGE_DEFS))):
            key = STAGE_DEFS[idx]["key"]
            if key in results and self._is_truncated_stage_output(results[key]):
                db_out = self._load_stage_output_from_db(key)
                if db_out:
                    results[key] = db_out
                    logger.info(
                        "[Pipeline] checkpoint 阶段 %s 已从 DB 回填 run_id=%s",
                        key,
                        self.run_id,
                    )

        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        hg = self._hydrate_hypothesis_generation(results.get("hypothesis_generation"), project_id)
        if hg.get("hypotheses"):
            results["hypothesis_generation"] = hg

        hr = results.get("hypothesis_review") or {}
        reviews = hr.get("reviews") or []
        hyps = (results.get("hypothesis_generation") or {}).get("hypotheses") or []
        if hyps and not reviews and start_idx >= 5:
            for stale_key in (
                "hypothesis_review",
                "experiment_design",
                "small_validation",
                "report_generation",
            ):
                results.pop(stale_key, None)
            logger.warning(
                "[Pipeline] 假设评审无有效 reviews，回退至 hypothesis_review 重跑 run_id=%s",
                self.run_id,
            )
            return 4
        return start_idx

    def _sync_db_stages_for_start_idx(self, start_idx: int, results: Dict[str, Any]) -> None:
        """HITL 恢复时，将跳过的阶段在 DB 中标记为已完成，避免误显示为从头运行。"""
        if start_idx <= 0:
            return
        from app.services.data_finder_slim import slim_stage_output

        now = datetime.now(CHINA_TZ)
        changed = False
        for idx in range(start_idx):
            order = idx + 1
            stage_def = STAGE_DEFS[idx]
            key = stage_def["key"]
            existing = self.db_stage_executions.get(order)
            if not existing:
                continue
            output = results.get(key) or existing.output_data
            if output is None:
                continue
            slimmed = slim_stage_output(output, stage_key=key) if isinstance(output, dict) else output
            if existing.status != DB_PipelineStatus.COMPLETED or not existing.output_data:
                existing.status = DB_PipelineStatus.COMPLETED
                existing.output_data = slimmed
                existing.error_message = None
                if not existing.completed_at:
                    existing.completed_at = now
                if existing.started_at and not existing.duration_ms:
                    try:
                        started = existing.started_at
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=CHINA_TZ)
                        existing.duration_ms = max(
                            0,
                            int((now - started).total_seconds() * 1000),
                        )
                    except Exception:
                        pass
                changed = True
        if changed:
            self.db.commit()
            logger.info(
                "[Pipeline] 已同步 DB 阶段状态至 start_idx=%s run_id=%s",
                start_idx,
                self.run_id,
            )

    def _maybe_bump_start_idx_for_hitl(self, start_idx: int, results: Dict[str, Any], meta: Dict[str, Any]) -> int:
        """安全网：假设已生成但 start_idx 仍为 0 时，强制从 hypothesis_review 继续。"""
        if start_idx >= 4:
            return start_idx
        gate = meta.get("hitl_gate") or {}
        cp = meta.get("pipeline_checkpoint") or {}
        paused_stage = gate.get("stage") or ""
        hg_exec = self.db_stage_executions.get(4)
        hr_exec = self.db_stage_executions.get(5)
        hg_done = hg_exec and hg_exec.status == DB_PipelineStatus.COMPLETED and hg_exec.output_data
        hr_pending = not hr_exec or hr_exec.status in (
            DB_PipelineStatus.PENDING,
            DB_PipelineStatus.RUNNING,
        )
        should_bump = (
            hg_done
            and hr_pending
            and (
                paused_stage == "hypothesis_generation"
                or cp.get("resume_phase") == "after_hypothesis_generation"
                or gate.get("resume_phase") == "after_hypothesis_generation"
            )
        )
        if not should_bump:
            return start_idx
        if hg_exec and hg_exec.output_data and "hypothesis_generation" not in results:
            results["hypothesis_generation"] = hg_exec.output_data
        if cp.get("results") and isinstance(cp["results"], dict):
            results.update(cp["results"])
        logger.warning(
            "[Pipeline] HITL 安全恢复: start_idx %s -> 4 (假设已生成) run_id=%s",
            start_idx,
            self.run_id,
        )
        return 4

    def _run_pipeline_stages(self, research_question: str, project_id: str) -> PipelineRunResult:
        """执行 Pipeline 所有阶段（支持从中间阶段 rerun）。"""
        project_mode = self._get_project_mode(project_id)
        self._run_options = self._get_run_options()
        self._merge_science_iteration_run_options(project_id)
        try:
            from app.services.feedback_hub_service import get_feedback_hub_service

            fb_constraints = get_feedback_hub_service(self.db).get_active_constraints(project_id)
            for c in fb_constraints:
                if c and c not in self._human_feedback_constraints:
                    self._human_feedback_constraints.append(c)
        except Exception as fb_err:
            logger.warning("[Pipeline] Feedback Hub 约束加载失败: %s", fb_err)
        start_idx = getattr(self, "_start_idx", 0) or 0
        logger.info(
            f"[Pipeline] ====== 开始执行 Pipeline run_id={self.run_id} "
            f"project_id={project_id} mode={project_mode} pipeline_mode={self._run_options.get('pipeline_mode')} "
            f"num_ideas={self._run_options.get('num_ideas')} "
            f"pro_con={self._run_options.get('enable_pro_con_adversarial')} "
            f"adv_mode={self._run_options.get('adversarial_mode')} "
            f"start_idx={start_idx} ======"
        )

        stages: List[PipelineStageLog] = [
            PipelineStageLog(stage=d["stage_enum"], status=PipelineStageStatus.PENDING)
            for d in STAGE_DEFS
        ]

        results: Dict[str, Any] = dict(self._seeded_results or {})
        run_meta = (
            self.db_pipeline_run.extra_metadata
            if isinstance(self.db_pipeline_run.extra_metadata, dict)
            else {}
        )

        if getattr(self, "_checkpoint_resume", None):
            cp = self._checkpoint_resume
            cp_results = cp.get("results") or {}
            if isinstance(cp_results, dict):
                results.update(cp_results)
            resume_phase = cp.get("resume_phase") or ""
            start_idx = max(start_idx, self._resume_phase_to_start_idx(resume_phase))
            if resume_phase in {
                "after_small_validation",
                "after_experiment_design",
                "after_iterative_experiment",
            }:
                self._skip_to_post_validation = True
            elif resume_phase == "after_report_generation":
                self._finalize_report_after_gate = True
            self._checkpoint_resume = None
            self._checkpoint_was_loaded = True
            logger.info(f"[Pipeline] 从 HITL checkpoint 恢复 phase={resume_phase} start_idx={start_idx}")

        start_idx = self._maybe_bump_start_idx_for_hitl(start_idx, results, run_meta)
        if getattr(self, "_checkpoint_was_loaded", False):
            start_idx = self._repair_checkpoint_results(results, start_idx)

        for idx, d in enumerate(STAGE_DEFS):
            if idx < start_idx:
                key = d["key"]
                if key in results:
                    stage_out = results[key]
                    if self._is_truncated_stage_output(stage_out):
                        exec_row = self.db_stage_executions.get(idx + 1)
                        if (
                            exec_row
                            and exec_row.output_data
                            and not self._is_truncated_stage_output(exec_row.output_data)
                        ):
                            stage_out = exec_row.output_data
                            results[key] = stage_out
                    stages[idx].status = PipelineStageStatus.COMPLETED
                    stages[idx].output_data = stage_out
                else:
                    exec_row = self.db_stage_executions.get(idx + 1)
                    if exec_row and exec_row.output_data:
                        stages[idx].status = PipelineStageStatus.COMPLETED
                        stages[idx].output_data = exec_row.output_data
                        results[key] = exec_row.output_data

        self._sync_db_stages_for_start_idx(start_idx, results)

        final_report_id: Optional[str] = None
        pipeline_start = datetime.now(CHINA_TZ)
        self._pipeline_start = pipeline_start  # 供 _build_pipeline_run_info 实时计算耗时
        
        try:
            # 更新 Pipeline 状态为运行中
            self.db_pipeline_run.status = DB_PipelineStatus.RUNNING
            self.db_pipeline_run.started_at = pipeline_start
            self.db.commit()

            # 同步更新项目状态为 in_progress
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.IN_PROGRESS
                project.updated_at = pipeline_start
                self.db.commit()
                logger.info(f"[Pipeline] 项目 {project_id} 状态已更新为 IN_PROGRESS")
            else:
                logger.warning(f"[Pipeline] 项目 {project_id} 未找到，无法更新状态")
            
            # ── 阶段 1: ProblemUnderstandingAgent ──
            if start_idx <= 0:
                self._run_stage(stages, 0, results, research_question, project_id,
                    lambda: self._exec_problem_understanding(research_question, project_id))
            
            # ── 阶段 2: LiteratureMiningAgent ──
            if start_idx <= 1:
                self._run_stage(stages, 1, results, research_question, project_id,
                    lambda: self._exec_literature_mining_stage(
                        project_id, research_question, results
                    ))

            # ── 阶段 3: KnowledgeGapAgent ──
            if start_idx <= 2:
                self._run_stage(stages, 2, results, research_question, project_id,
                    lambda: self._exec_knowledge_gap(
                        self._enrich_and_store_literature_mining(results),
                        project_id,
                        results.get("problem_understanding"),
                    ))
            
            # ── 阶段 4: HypothesisGenerationAgent ──
            if start_idx <= 3:
                # 缺口完成后立即更新 current_stage，避免轮询间隙 UI 仍显示缺口运行中
                self.db_pipeline_run.current_stage = STAGE_DEFS[3]["key"]
                self.db.commit()

                # ── P3: Ideation 新颖性预检（OpenAlex + Semantic Scholar）──
                try:
                    ideation = self._exec_ideation_novelty(
                        results.get("problem_understanding"),
                        results.get("knowledge_gap"),
                    )
                    if ideation:
                        results["ideation_novelty"] = ideation
                        self._record_closed_loop_event(
                            "ideation_novelty",
                            {
                                "round": 0,
                                "novelty_score": ideation.get("novelty_score"),
                                "external_papers": ideation.get("external_papers_count"),
                                "num_ideas": ideation.get("num_ideas_requested"),
                                "summary": (ideation.get("assessment") or "")[:200],
                                "quality_trend_entry": {
                                    "stage": "ideation_novelty",
                                    "score": ideation.get("novelty_score"),
                                },
                            },
                        )
                except Exception as ide_err:
                    logger.warning(f"Ideation 新颖性检查失败: {ide_err}")

                self._run_stage(stages, 3, results, research_question, project_id,
                    lambda: self._exec_hypothesis_generation(
                        results.get("problem_understanding"),
                        # 假设生成前强制用项目文献库回填 facts（含手动上传 PDF 的 chunk）
                        self._enrich_and_store_literature_mining(results),
                        results.get("knowledge_gap"),
                        results.get("ideation_novelty"),
                    ))

                if results.get("ideation_novelty") and results.get("hypothesis_generation"):
                    hg = results["hypothesis_generation"]
                    if isinstance(hg, dict):
                        hg["ideation_novelty"] = results["ideation_novelty"]
                        results["hypothesis_generation"] = hg

                try:
                    self._exec_evidence_reasoning(project_id, research_question, results)
                except Exception as er_err:
                    logger.warning(f"证据链迭代验证失败: {er_err}")

                # ── P1: 假设树评分与剪枝 ──
                try:
                    self._exec_hypothesis_tree(results, research_question)
                except Exception as ht_err:
                    logger.warning(f"假设树剪枝失败: {ht_err}")

                try:
                    self._save_hypotheses(project_id, research_question, results)
                except Exception as save_err:
                    logger.warning(f"保存假设/证据链失败: {save_err}")
                self._run_science_iteration_hooks(
                    "after_hypothesis_generation", results, research_question, project_id, project_mode,
                )
            
            # ── 阶段 5: HypothesisReviewAgent ──
            if start_idx <= 4:
                self._run_stage(stages, 4, results, research_question, project_id,
                    lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
                self._run_science_iteration_hooks(
                    "after_hypothesis_review", results, research_question, project_id, project_mode,
                )
                results.pop("counterfactual_preview", None)
                self._stage_results.pop("counterfactual_preview", None)
                self._ensure_counterfactual_preview(results, research_question)
                # 可行性评估后暂停：迭代实验 / 报告改由「迭代实验」页人工完成
                self._pause_for_feasibility_handoff(results)

            # ── 阶段 6: 迭代实验（仅 discovery / 显式关闭暂停 / 单阶段重跑时执行）──
            teaching_report_ran = False
            if start_idx <= 5 and not self._should_defer_iterative_experiment():
                self._ensure_counterfactual_preview(results, research_question)
                self._run_stage(stages, 5, results, research_question, project_id,
                    lambda: self._exec_iterative_experiment(
                        results.get("hypothesis_review"),
                        project_id,
                        project_mode,
                    ))
                ie = results.get("iterative_experiment") or {}
                if isinstance(ie, dict) and ie.get("small_validation"):
                    self._apply_post_validation_updates(results, ie["small_validation"])
            elif start_idx <= 5 and self._should_defer_iterative_experiment():
                results["iterative_experiment"] = {
                    "status": "deferred_to_experiments_page",
                    "warning": "请在「迭代实验」页完成实验设计与沙箱验证后再生成报告",
                }

            # ── 阶段 7: ReportGenerationAgent（默认不自动触发；由迭代实验页「生成报告」触发）──
            # 生成前用迭代实验页最新勾选快照覆盖 stage-6 陈旧输出（常见：blocked_need_data），
            # 否则显式重跑 report_generation 会被旧状态误跳过，阶段一直停在 pending。
            if project_id and start_idx <= 6:
                try:
                    from app.services.iterative_experiment_service import (
                        get_iterative_experiment_service,
                    )

                    snap = get_iterative_experiment_service().snapshot_for_report(project_id)
                    if isinstance(snap, dict) and (
                        snap.get("experiments")
                        or snap.get("status")
                        in {
                            "completed",
                            "partial",
                            "blocked_need_data",
                            "blocked_need_hypothesis",
                            "deferred_to_experiments_page",
                        }
                    ):
                        results["iterative_experiment"] = snap
                        logger.info(
                            "[Pipeline] 报告前注入迭代实验快照 status=%s n_exp=%s report_ids=%s",
                            snap.get("status"),
                            len(snap.get("experiments") or []),
                            snap.get("report_experiment_ids"),
                        )
                except Exception as snap_err:
                    logger.warning("[Pipeline] 报告前注入迭代实验快照失败: %s", snap_err)

            ie_status = (results.get("iterative_experiment") or {}).get("status")
            block_report = ie_status in {
                "blocked_need_data",
                "blocked_need_hypothesis",
            }
            # deferred 仅在自动链路中阻断；显式重跑报告阶段时已由上方 snapshot 覆盖
            if ie_status == "deferred_to_experiments_page" and self._should_defer_auto_report():
                block_report = True
            if getattr(self, "_finalize_report_after_gate", False):
                self._finalize_report_after_gate = False
                final_report_id = self._persist_pipeline_report(project_id, results)
            elif start_idx <= 6 and not teaching_report_ran and not block_report and not self._should_defer_auto_report():
                def _exec_report():
                    pipeline_run_info = self._build_pipeline_run_info()
                    return self._exec_report_generation(
                        results, pipeline_run_info, project_mode
                    )
                self._run_stage(stages, 6, results, research_question, project_id, _exec_report)
                final_report_id = self._persist_pipeline_report(project_id, results)
            elif block_report or (start_idx <= 6 and self._should_defer_auto_report()):
                skip_payload = {
                    "status": "skipped",
                    "warning": (results.get("iterative_experiment") or {}).get("warning")
                    or "请在「迭代实验」页完成实验后手动生成报告",
                }
                results["report_generation"] = skip_payload
                stages[6].status = PipelineStageStatus.COMPLETED
                stages[6].output_data = skip_payload
                db_report = self.db_stage_executions.get(7)
                if db_report is not None:
                    self._update_stage_execution(db_report, "completed", output=skip_payload)
                logger.warning(
                    "[Pipeline] 报告生成已跳过 run_id=%s reason=%s",
                    self.run_id,
                    skip_payload.get("warning"),
                )

            
            # Pipeline 完成
            pipeline_end = datetime.now(CHINA_TZ)
            total_duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            
            logger.info(f"Pipeline 执行成功: {self.run_id}, 总耗时: {total_duration_ms}ms")
            
            self._complete_pipeline_run(pipeline_end, total_duration_ms, results, final_report_id)
            
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=project_id,
                research_question=research_question,
                status=PipelineStatus.COMPLETED,
                stages=stages,
                total_duration=total_duration_ms / 1000.0,
                problem_understanding=results.get('problem_understanding'),
                literature_mining=results.get('literature_mining'),
                knowledge_gap=results.get('knowledge_gap'),
                hypothesis_generation=results.get('hypothesis_generation'),
                hypothesis_review=results.get('hypothesis_review'),
                **self._flatten_ed_sv_fields(results),
                report_generation=results.get('report_generation'),
                final_report=results.get('report_generation'),
                final_report_id=final_report_id,
                run_id=self.run_id,
                extra_metadata=self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else None,
                created_at=pipeline_start,
                completed_at=pipeline_end,
                failed_stage=None
            )

        except HitlGatePause as pause:
            pipeline_end = datetime.now(CHINA_TZ)
            total_duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            logger.info(
                f"[Pipeline] HITL Gate 暂停 run_id={self.run_id} stage={pause.stage_key}"
            )
            meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=project_id,
                research_question=research_question,
                status=PipelineStatus.HUMAN_REVIEW_REQUIRED,
                stages=stages,
                total_duration=total_duration_ms / 1000.0,
                problem_understanding=results.get('problem_understanding'),
                literature_mining=results.get('literature_mining'),
                knowledge_gap=results.get('knowledge_gap'),
                hypothesis_generation=results.get('hypothesis_generation'),
                hypothesis_review=results.get('hypothesis_review'),
                **self._flatten_ed_sv_fields(results),
                report_generation=results.get('report_generation'),
                run_id=self.run_id,
                extra_metadata=meta,
                created_at=pipeline_start,
                completed_at=pipeline_end,
                failed_stage=None,
            )

        except SingleStageRerunComplete as done:
            pipeline_end = datetime.now(CHINA_TZ)
            total_duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            logger.info(
                f"[Pipeline] 单阶段重跑完成 run_id={self.run_id} stage={done.stage_key}"
            )
            self._finalize_in_place_rerun_metadata(done.stage_key)
            final_report_id = self.db_pipeline_run.final_report_id
            if done.stage_key == "report_generation":
                created = self._persist_pipeline_report(project_id, results)
                if created:
                    final_report_id = created
            self._complete_pipeline_run(pipeline_end, total_duration_ms, results, final_report_id)
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=project_id,
                research_question=research_question,
                status=PipelineStatus.COMPLETED,
                stages=stages,
                total_duration=total_duration_ms / 1000.0,
                problem_understanding=results.get('problem_understanding'),
                literature_mining=results.get('literature_mining'),
                knowledge_gap=results.get('knowledge_gap'),
                hypothesis_generation=results.get('hypothesis_generation'),
                hypothesis_review=results.get('hypothesis_review'),
                **self._flatten_ed_sv_fields(results),
                report_generation=results.get('report_generation'),
                final_report=results.get('report_generation'),
                final_report_id=final_report_id,
                run_id=self.run_id,
                extra_metadata=self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else None,
                created_at=pipeline_start,
                completed_at=pipeline_end,
                failed_stage=None,
            )

        except Exception as e:
            pipeline_end = datetime.now(CHINA_TZ)
            total_duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            
            failed_stage = _find_failed_stage(stages)
            failed_stage_name = None
            if failed_stage:
                failed_stage_name = failed_stage.stage.value if isinstance(failed_stage.stage, PipelineStage) else str(failed_stage.stage)
            
            logger.error(f"Pipeline 执行失败: {self.run_id}, 阶段: {failed_stage_name}, 错误: {e}", exc_info=True)
            
            self._fail_pipeline_run(pipeline_end, total_duration_ms, failed_stage_name, str(e))
            
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=project_id,
                research_question=research_question,
                status=PipelineStatus.FAILED,
                stages=stages,
                total_duration=total_duration_ms / 1000.0,
                problem_understanding=results.get('problem_understanding'),
                literature_mining=results.get('literature_mining'),
                knowledge_gap=results.get('knowledge_gap'),
                hypothesis_generation=results.get('hypothesis_generation'),
                hypothesis_review=results.get('hypothesis_review'),
                **self._flatten_ed_sv_fields(results),
                report_generation=results.get('report_generation'),
                final_report=results.get('report_generation'),
                final_report_id=None,
                run_id=self.run_id,
                created_at=pipeline_start,
                completed_at=pipeline_end,
                failed_stage=failed_stage_name
            )
    
    # ────────────── 阶段执行 ──────────────

    def _should_defer_iterative_experiment(self) -> bool:
        """默认将迭代实验 defer 到「迭代实验」页；discovery / 显式关闭暂停 / 显式重跑除外。"""
        if not self._run_options.get("pause_after_hypothesis_review", True):
            return False
        start_idx = getattr(self, "_start_idx", 0) or 0
        if getattr(self, "_rerun_single_stage_only", False) and start_idx == 5:
            return False
        meta = (
            self.db_pipeline_run.extra_metadata
            if self.db_pipeline_run and isinstance(self.db_pipeline_run.extra_metadata, dict)
            else {}
        )
        if meta.get("rerun_from_stage") == "iterative_experiment":
            return False
        return True

    def _should_defer_auto_report(self) -> bool:
        """默认不自动生成报告；由迭代实验页「生成报告」或显式重跑报告阶段触发。"""
        if not self._run_options.get("pause_after_hypothesis_review", True):
            return False
        start_idx = getattr(self, "_start_idx", 0) or 0
        if start_idx >= 6:
            return False
        meta = (
            self.db_pipeline_run.extra_metadata
            if self.db_pipeline_run and isinstance(self.db_pipeline_run.extra_metadata, dict)
            else {}
        )
        rerun_from = meta.get("rerun_from_stage")
        if rerun_from in {"report_generation", "iterative_experiment"}:
            return False
        return True

    def _pause_for_feasibility_handoff(self, results: Dict[str, Any]) -> None:
        """可行性评估完成后暂停 Pipeline，引导用户前往「迭代实验」页。"""
        if not self._run_options.get("pause_after_hypothesis_review", True):
            return
        stage_key = "hypothesis_review"
        meta = (
            self.db_pipeline_run.extra_metadata
            if isinstance(self.db_pipeline_run.extra_metadata, dict)
            else {}
        )
        gate = dict(meta.get("hitl_gate") or {})
        cleared = list(gate.get("cleared_stages") or [])
        if stage_key in cleared:
            return

        resume_phase = f"after_{stage_key}"
        gate.update({
            "paused": True,
            "stage": stage_key,
            "stage_label": HITL_GATE_STAGE_LABELS.get(stage_key, stage_key),
            "resume_phase": resume_phase,
            "paused_at": datetime.now(CHINA_TZ).isoformat(),
            "cleared_stages": cleared,
            "handoff": "iterative_experiment_page",
        })
        meta["hitl_gate"] = gate
        meta["pipeline_checkpoint"] = {
            "results": self._checkpoint_safe_results(results),
            "resume_phase": resume_phase,
        }
        self.db_pipeline_run.status = DB_PipelineStatus.HUMAN_REVIEW_REQUIRED
        self.db_pipeline_run.current_stage = stage_key
        self.db_pipeline_run.extra_metadata = meta
        self.db.commit()
        self._record_closed_loop_event(
            "hitl_gate_pause",
            {
                "stage": stage_key,
                "stage_label": gate.get("stage_label"),
                "summary": "可行性评估已完成：请前往「迭代实验」页进行实验设计与沙箱验证",
                "quality_trend_entry": {
                    "stage": "hitl_gate",
                    "score": 6.0,
                    "label": stage_key,
                },
            },
        )
        raise HitlGatePause(stage_key)

    def _should_hitl_gate(self, stage_key: str) -> bool:
        if self._run_options.get("iteration_mode") != "human":
            return False
        if not self._run_options.get("enable_hitl_gate"):
            return False
        if self._run_options.get("pipeline_mode") != PipelineMode.TEACHING.value:
            return False
        allowed = self._run_options.get("hitl_gate_stages") or []
        if stage_key not in allowed:
            return False
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        cleared = (meta.get("hitl_gate") or {}).get("cleared_stages") or []
        return stage_key not in cleared

    def _checkpoint_safe_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.data_finder_slim import slim_results_for_checkpoint

        return slim_results_for_checkpoint(results)

    def _maybe_pause_for_hitl_gate(self, stage_key: str, results: Dict[str, Any]) -> None:
        if not self._should_hitl_gate(stage_key):
            return
        resume_phase = f"after_{stage_key}"
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        gate = dict(meta.get("hitl_gate") or {})
        gate.update({
            "paused": True,
            "stage": stage_key,
            "stage_label": HITL_GATE_STAGE_LABELS.get(stage_key, stage_key),
            "resume_phase": resume_phase,
            "paused_at": datetime.now(CHINA_TZ).isoformat(),
            "cleared_stages": gate.get("cleared_stages") or [],
        })
        meta["hitl_gate"] = gate
        meta["pipeline_checkpoint"] = {
            "results": self._checkpoint_safe_results(results),
            "resume_phase": resume_phase,
        }
        self.db_pipeline_run.status = DB_PipelineStatus.HUMAN_REVIEW_REQUIRED
        self.db_pipeline_run.current_stage = stage_key
        self.db_pipeline_run.extra_metadata = meta
        self.db.commit()
        self._record_closed_loop_event(
            "hitl_gate_pause",
            {
                "stage": stage_key,
                "stage_label": gate.get("stage_label"),
                "summary": f"Teaching HITL Gate：等待确认「{gate.get('stage_label')}」后继续",
                "quality_trend_entry": {
                    "stage": "hitl_gate",
                    "score": 6.0,
                    "label": stage_key,
                },
            },
        )
        raise HitlGatePause(stage_key)

    def _restore_downstream_from_parent_run(
        self,
        stage_idx: int,
        results: Dict[str, Any],
        stages: List[PipelineStageLog],
    ) -> None:
        """单阶段重跑后，从父 run 恢复下游阶段状态与输出。"""
        parent_run_id = getattr(self, "_parent_run_id_for_rerun", None)
        if not parent_run_id:
            return
        parent = self.db.query(DB_PipelineRun).filter(DB_PipelineRun.run_id == parent_run_id).first()
        if not parent:
            return
        parent_stages = (
            self.db.query(DB_PipelineStageExecution)
            .filter(DB_PipelineStageExecution.pipeline_run_id == parent.id)
            .order_by(DB_PipelineStageExecution.stage_order)
            .all()
        )
        parent_map = {
            (s.stage.value if hasattr(s.stage, "value") else str(s.stage)): s for s in parent_stages
        }
        for idx in range(stage_idx + 1, len(STAGE_DEFS)):
            key = STAGE_DEFS[idx]["key"]
            parent_exec = parent_map.get(key)
            db_stage = self.db_stage_executions.get(idx + 1)
            if not parent_exec or not db_stage:
                continue
            db_stage.status = parent_exec.status
            db_stage.started_at = parent_exec.started_at
            db_stage.completed_at = parent_exec.completed_at
            db_stage.duration_ms = parent_exec.duration_ms
            db_stage.input_data = parent_exec.input_data
            db_stage.output_data = parent_exec.output_data
            db_stage.model_used = parent_exec.model_used
            db_stage.model_parameters = parent_exec.model_parameters
            db_stage.prompt_used = parent_exec.prompt_used
            db_stage.token_count = parent_exec.token_count
            db_stage.extra_metadata = parent_exec.extra_metadata
            effective = get_effective_output(parent_exec, use_human_modified=True)
            if effective is not None:
                results[key] = effective
                stages[idx].status = PipelineStageStatus.COMPLETED
                stages[idx].output_data = parent_exec.output_data
            elif parent_exec.output_data:
                results[key] = parent_exec.output_data
                stages[idx].status = PipelineStageStatus.COMPLETED
                stages[idx].output_data = parent_exec.output_data
        self.db.commit()
        logger.info(
            f"[Pipeline] 单阶段重跑完成，已从父 run 恢复下游阶段 parent={parent_run_id}"
        )

    def _finalize_in_place_rerun_metadata(self, stage_key: str) -> None:
        """单阶段原地重跑完成后清理临时 metadata。"""
        if not self.db_pipeline_run:
            return
        meta = dict(self.db_pipeline_run.extra_metadata or {})
        if not meta.get("in_place_rerun"):
            return
        meta["last_in_place_rerun"] = {
            "stage": stage_key,
            "at": datetime.now(CHINA_TZ).isoformat(),
        }
        for key in ("rerun_from_stage", "in_place_rerun", "rerun_mode", "feedback_constraints", "rerun_downstream_context"):
            meta.pop(key, None)
        self.db_pipeline_run.extra_metadata = meta
        flag_modified(self.db_pipeline_run, "extra_metadata")
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
    
    def _run_stage(
        self,
        stages: List[PipelineStageLog],
        idx: int,
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        executor
    ):
        """统一阶段执行器：记录日志、执行、捕获异常"""
        stage_def = STAGE_DEFS[idx]
        stage_log = stages[idx]
        stage_key = stage_def["key"]
        stage_label = stage_def["label"]

        stage_log.status = PipelineStageStatus.RUNNING
        stage_log.start_time = datetime.now(CHINA_TZ)

        logger.info(f"[Pipeline] 开始阶段 {idx+1}/8 [{stage_label}] key={stage_key} run_id={self.run_id}")

        input_data = self._build_stage_input(idx, results, research_question, project_id)

        clear_call_logs()

        db_stage = self._create_stage_execution(idx + 1, stage_def["db_stage_enum"], input_data)

        self.db_pipeline_run.current_stage = stage_key
        self.db.commit()

        output = None
        try:
            output = executor()
            from app.services.data_finder_slim import slim_stage_output

            full_output = (
                output if isinstance(output, dict) else self._safe_model_dump(output)
            )
            slimmed_output = slim_stage_output(full_output, stage_key=stage_key)
            stage_log.status = PipelineStageStatus.COMPLETED
            stage_log.output_data = slimmed_output
            results[stage_key] = full_output
            self._stage_results[stage_key] = full_output

            self._capture_model_params(db_stage)
            self._update_stage_execution(db_stage, "completed", output=slimmed_output)
            logger.info(f"[Pipeline] 阶段完成 {idx+1}/8 [{stage_label}] key={stage_key} run_id={self.run_id}")

            try:
                from app.services.project_research_backfill_service import backfill_project_research_fields
                backfill_project_research_fields(self.db, project_id, results, stage_key)
            except Exception as backfill_err:
                logger.warning(
                    f"[Pipeline] 研究问题字段回填失败 stage={stage_key} run_id={self.run_id}: {backfill_err}"
                )

            # ── 大家长 Agent 阶段检查 ──
            try:
                if self._run_options.get("enable_coordinator_agent", True):
                    self._coordinator_check(stage_key, full_output, research_question, project_id)
            except Exception as coord_err:
                logger.warning(
                    f"[Pipeline] 大家长检查失败 stage={stage_key} run_id={self.run_id}: {coord_err}"
                )

            if getattr(self, "_rerun_single_stage_only", False) and idx == getattr(self, "_start_idx", 0):
                if not getattr(self, "_in_place_rerun", False):
                    self._restore_downstream_from_parent_run(idx, results, stages)
                raise SingleStageRerunComplete(stage_key)

        except SingleStageRerunComplete as done:
            raise done
        except Exception as e:
            stage_log.status = PipelineStageStatus.FAILED
            stage_log.error_message = str(e)
            self._capture_model_params(db_stage)
            self._update_stage_execution(db_stage, "failed", error=str(e))

            self.db_pipeline_run.status = DB_PipelineStatus.FAILED
            self.db_pipeline_run.failed_stage = stage_def["db_stage_enum"]
            self.db_pipeline_run.error_message = str(e)
            self.db_pipeline_run.completed_at = datetime.now(CHINA_TZ)
            self.db.commit()

            logger.error(f"[Pipeline] 阶段失败 {idx+1}/8 [{stage_label}] key={stage_key} run_id={self.run_id} error={str(e)[:200]}", exc_info=True)
            raise
        finally:
            stage_log.end_time = datetime.now(CHINA_TZ)
            if stage_log.start_time:
                stage_log.duration = (stage_log.end_time - stage_log.start_time).total_seconds()
    
    def _capture_model_params(self, db_stage: DB_PipelineStageExecution):
        """从最近一次 Qwen 调用日志中提取 model_parameters 和 prompt_used"""
        logs = get_call_logs()
        if not logs:
            return
        
        last_call: CallLog = logs[-1]
        db_stage.model_used = last_call.model_name
        db_stage.model_parameters = {
            "temperature": last_call.temperature,
            "model_name": last_call.model_name,
            "prompt_version": last_call.prompt_version,
            "duration_ms": last_call.duration_ms,
        }
        db_stage.prompt_used = last_call.input[:2000] if last_call.input else ""
        db_stage.token_count = last_call.total_tokens
        db_stage.duration_ms = last_call.duration_ms
        self.db.commit()

    def _get_coordinator(self):
        """懒加载 CoordinatorAgent"""
        if self._coordinator is None:
            from app.agents.coordinator_agent import CoordinatorAgent
            self._coordinator = CoordinatorAgent(db=self.db)
        return self._coordinator

    def _coordinator_check(
        self,
        stage: str,
        result: Dict[str, Any],
        research_question: str,
        project_id: str,
    ) -> None:
        """大家长 Agent 阶段检查（同步）"""
        coordinator = self._get_coordinator()
        coordinator.update_context("research_question", research_question)
        coordinator.update_stage_result(stage, result)

        snapshot = coordinator.build_error_snapshot(stage, result)
        decision = coordinator.decide_remediation(stage, snapshot)

        # 记录提示
        hint_entry = {
            "id": f"{stage}_{datetime.now().isoformat()}",
            "stage": stage,
            "severity": decision.get("severity", "info"),
            "message": decision.get("message", ""),
            "remediation": decision.get("remediation"),
            "action": decision.get("action", {}),
            "source": decision.get("source", "predefined"),
            "timestamp": decision.get("timestamp", datetime.now().isoformat()),
        }
        self._coordinator_hints.append(hint_entry)

        # 自动执行补救
        action = decision.get("action", {})
        if action.get("type") == "auto":
            suggestion = action.get("suggestion")
            if suggestion == "iterate_evidence":
                # 在后台线程执行（非阻塞主流程）
                import threading
                thread = threading.Thread(
                    target=self._auto_evidence_iteration_sync,
                    args=(research_question, project_id),
                    daemon=True,
                )
                thread.start()

        # 记录闭环事件
        if decision.get("remediation"):
            self._record_closed_loop_decision(
                trigger=f"coordinator_{stage}_check",
                action=decision.get("remediation", "pass"),
                reason=decision.get("message", "")[:300],
                next_stage=stage,
                metadata={"severity": decision.get("severity", "info")},
            )

    def _auto_evidence_iteration_sync(
        self,
        research_question: str,
        project_id: str,
    ) -> None:
        """低证据假设自动证据链迭代（同步版本，后台线程使用）"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                self._auto_evidence_iteration(research_question, project_id)
            )
            loop.close()
        except Exception as e:
            logger.warning(f"自动证据链迭代（线程）失败: {e}")

    async def _auto_evidence_iteration(
        self,
        research_question: str,
        project_id: str,
    ) -> None:
        """低证据假设自动证据链迭代"""
        hypotheses = self._stage_results.get("hypothesis_generation", {}).get("hypotheses", [])
        low_evidence = [
            h for h in hypotheses
            if isinstance(h, dict) and h.get("evidence_level") == "low"
        ]
        if not low_evidence:
            return

        try:
            from app.services.evidence_reasoning_service import get_evidence_reasoning_service

            er_service = get_evidence_reasoning_service(self.db)
            lit_mining = self._stage_results.get("literature_mining") or {}

            updated = await er_service.run_for_hypotheses(
                hypotheses=low_evidence,
                research_question=research_question,
                literature_mining=lit_mining,
                max_rounds=2,
            )

            if updated:
                # 回写修订后的假设
                all_hypotheses = self._stage_results.get("hypothesis_generation", {}).get("hypotheses", [])
                updated_ids = {h.get("hypothesis_id") for h in updated if isinstance(h, dict)}
                merged = []
                for h in all_hypotheses:
                    hid = h.get("hypothesis_id") if isinstance(h, dict) else None
                    if hid and hid in updated_ids:
                        # 找到对应的修订版本
                        revised = next((u for u in updated if isinstance(u, dict) and u.get("hypothesis_id") == hid), h)
                        merged.append(revised)
                    else:
                        merged.append(h)

                if merged:
                    self._stage_results["hypothesis_generation"]["hypotheses"] = merged
                    self._stage_results["hypothesis_generation"]["auto_iterated"] = True

                self._record_closed_loop_decision(
                    trigger="coordinator_auto_evidence_iteration",
                    action="iterate_evidence",
                    reason=f"自动迭代修正 {len(updated)} 条低证据假设",
                    next_stage="hypothesis_review",
                    metadata={"hypotheses_revised": len(updated)},
                )
        except Exception as e:
            logger.warning(f"自动证据链迭代失败: {e}")

    def _build_stage_input(self, idx: int, results: Dict[str, Any], research_question: str, project_id: str) -> Dict[str, Any]:
        """构建阶段输入数据"""
        project_mode = self._get_project_mode(project_id)
        base = {
            "project_id": project_id,
            "research_question": research_question,
            "project_mode": project_mode,
        }
        if idx >= 1:
            base["literature_mining"] = results.get("literature_mining", {})
            base["data_finder"] = results.get("data_finder", {})
        if idx >= 2:
            base["knowledge_gap"] = results.get("knowledge_gap", {})
        if idx >= 3:
            base["problem_understanding"] = results.get("problem_understanding", {})
            pid = self.db_pipeline_run.project_id if self.db_pipeline_run else project_id
            data_context = self._build_data_context(pid)
            base["data_context"] = data_context
        if idx >= 4:
            base["hypothesis_generation"] = results.get("hypothesis_generation", {})
        if idx >= 5:
            base["hypothesis_review"] = results.get("hypothesis_review", {})
        if idx >= 6:
            from app.services.iterative_experiment_service import resolve_ed_sv_from_results

            ie, ed, sv = resolve_ed_sv_from_results(results)
            base["iterative_experiment"] = ie
            base["experiment_design"] = ed
            base["small_validation"] = sv
        return base
    
    def _build_pipeline_run_info(self) -> Dict[str, Any]:
        """构建 Pipeline 运行摘要信息"""
        now = datetime.now(CHINA_TZ)
        duration_ms = self.db_pipeline_run.total_duration_ms or (
            int((now - self._pipeline_start).total_seconds() * 1000)
            if hasattr(self, '_pipeline_start') and self._pipeline_start
            else 0
        )
        return {
            "run_id": self.run_id,
            "started_at": self.db_pipeline_run.started_at.isoformat() if self.db_pipeline_run and self.db_pipeline_run.started_at else None,
            "completed_at": now.isoformat(),
            "total_duration_ms": duration_ms,
            "status": "completed",
            "stages": [
                {
                    "stage": stage_exec.stage.value if hasattr(stage_exec.stage, "value") else str(stage_exec.stage),
                    "status": stage_exec.status.value if hasattr(stage_exec.status, "value") else str(stage_exec.status),
                    "started_at": stage_exec.started_at.isoformat() if stage_exec.started_at else None,
                    "completed_at": stage_exec.completed_at.isoformat() if stage_exec.completed_at else None,
                    "duration_ms": stage_exec.duration_ms
                }
                for stage_exec in self.db_stage_executions.values()
            ]
        }
    
    # ────────────── Agent 执行方法 ──────────────
    
    def _exec_problem_understanding(self, research_question: str, project_id: str = ""):
        agent = get_problem_understanding_agent()
        domain_description = None
        if project_id:
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project and project.research_domain:
                domain_description = project.research_domain.strip()
        result = agent.analyze(
            research_question=research_question,
            domain_description=domain_description,
        )
        return self._safe_model_dump(result)
    
    def _normalize_literature_bundle(
        self, literature_mining: Optional[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        from app.services.literature_bundle_service import normalize_literature_bundle

        return normalize_literature_bundle(literature_mining)

    def _enrich_literature_mining(self, literature_mining: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        from app.services.literature_bundle_service import (
            enrich_literature_mining,
            merge_project_library_into_literature_mining,
        )

        lm = enrich_literature_mining(literature_mining)
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        if not project_id:
            return lm

        # FL Starter Pack：合并项目挂载的 seed facts（不改 mining 算法）
        try:
            from app.models.project import Project
            from app.services.fl_pack_service import FlPackService

            project = self.db.query(Project).filter(Project.id == project_id).first()
            cfg = (project.config if project and isinstance(project.config, dict) else {}) or {}
            seeds = FlPackService.get_seed_facts_from_project_config(cfg)
            if seeds:
                existing = list(lm.get("facts") or [])
                seen = {
                    str(f.get("fact_id") or f.get("content") or "")[:80]
                    for f in existing
                    if isinstance(f, dict)
                }
                for seed in seeds:
                    if not isinstance(seed, dict):
                        continue
                    key = str(seed.get("fact_id") or seed.get("content") or "")[:80]
                    if key and key in seen:
                        continue
                    existing.append(seed)
                    if key:
                        seen.add(key)
                lm["facts"] = existing
        except Exception as exc:
            logger.warning("[Literature] 合并 FL seed facts 失败: %s", exc)

        # 手动上传 / 已解析文献：回填 citation + facts（摘要或 chunk）
        try:
            lm = merge_project_library_into_literature_mining(
                lm, db=self.db, project_id=project_id
            )
        except Exception as exc:
            logger.warning("[Literature] 合并项目文献库失败: %s", exc)
        return lm

    def _enrich_and_store_literature_mining(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """回填项目文献库 facts，并写回 results，供假设生成及下游共用。"""
        lm = self._enrich_literature_mining(results.get("literature_mining") or {})
        results["literature_mining"] = lm
        return lm

    def _merge_data_acquisition_context(
        self,
        data_context: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """把数据采集阶段产物并入报告 data_context。"""
        da = results.get("data_acquisition") or {}
        extract = da.get("extract") if isinstance(da.get("extract"), dict) else {}
        if extract:
            data_context = {**data_context, "data_finder_results": extract}

        # 优先加载磁盘上的完整 Data Finder 结果（含 merged / coverage / provenance）
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        if project_id:
            try:
                from app.services.data_finder_service import get_data_finder_service

                full = get_data_finder_service(self.db).load_results(project_id)
                if isinstance(full, dict) and full:
                    data_context = {**data_context, "data_finder_results": full}
            except Exception as exc:
                logger.warning("[Report] 加载完整 data_finder 结果失败: %s", exc)

        df = data_context.get("data_finder_results") if isinstance(data_context.get("data_finder_results"), dict) else {}
        candidates = list(df.get("external_candidates") or extract.get("external_candidates") or [])
        if candidates:
            data_context["recommended_datasets"] = candidates

        uploaded = []
        for cand in candidates:
            status = (cand.get("user_upload_status") or "").lower()
            if status in ("uploaded", "accepted", "ready", "merged"):
                uploaded.append(cand)
        if uploaded:
            data_context["uploaded_external_datasets"] = uploaded

        return data_context

    def _augment_query_for_rerun(self, research_question: str) -> str:
        """将人工约束与下游进展摘要并入检索 query（跨阶段重跑时）。"""
        notes = [c for c in (self._human_feedback_constraints or []) if c and str(c).strip()]
        if not notes:
            return research_question
        suffix = " ".join(str(n) for n in notes[:6])[:900]
        combined = f"{research_question} [修正约束与项目进展: {suffix}]"
        return combined[:1200]

    def _exec_literature_mining(
        self,
        project_id: str,
        research_question: str,
        results: Optional[Dict[str, Any]] = None,
    ):
        agent = get_literature_mining_agent()
        query = self._augment_query_for_rerun(research_question)
        pu = (results or {}).get("problem_understanding") or {}
        domain = (pu.get("research_domain") or "").strip() if isinstance(pu, dict) else ""
        result = agent.mine(
            project_id=project_id,
            research_question=query,
            top_k=self._get_literature_top_k(),
            db=self.db,
            research_domain=domain,
        )
        return self._safe_model_dump(result)

    def _exec_literature_mining_stage(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """文献挖掘 + 多模态 evidence 合并，并在无文献时终止工作流。"""
        dump = self._exec_literature_mining(project_id, research_question, results)
        results["literature_mining"] = dump
        try:
            self._exec_multimodal_sync(project_id, research_question, results)
        except Exception as mm_err:
            logger.warning(f"多模态 evidence 同步失败: {mm_err}")
        lm = self._enrich_literature_mining(results.get("literature_mining") or {})
        results["literature_mining"] = lm
        self._validate_literature_results(lm)
        return lm

    @staticmethod
    def _validate_literature_results(
        literature_mining: Dict[str, Any],
        *,
        allow_empty: bool = False,
    ) -> None:
        """未检索到可用文献时抛出 LiteratureNotFoundError。"""
        if not isinstance(literature_mining, dict):
            raise LiteratureNotFoundError("文献挖掘结果无效")

        facts = literature_mining.get("facts") or []
        retrieved = literature_mining.get("retrieved_papers") or []
        source_papers = literature_mining.get("source_papers") or []
        candidate_count = literature_mining.get("candidate_references_count")
        if candidate_count is None:
            candidate_count = len(retrieved)

        discovery = (literature_mining.get("skill_outputs") or {}).get("literature_discovery") or {}
        discovery_data = discovery.get("data") if isinstance(discovery, dict) else {}
        discovery_total = 0
        if isinstance(discovery_data, dict):
            discovery_total = int(discovery_data.get("total") or discovery_data.get("candidate_count") or 0)

        has_literature = bool(facts) or bool(retrieved) or bool(source_papers) or candidate_count > 0 or discovery_total > 0
        if has_literature:
            return

        warning = (literature_mining.get("warning") or "").strip()
        message = warning or "未找到相关文献，工作流已停止"
        if allow_empty:
            logger.warning("文献为空但 allow_empty=True，继续 Pipeline: %s", message)
            return
        raise LiteratureNotFoundError(message)

    def _exec_multimodal_sync(self, project_id: str, research_question: str, results: Dict[str, Any]) -> Dict[str, Any]:
        """同步项目多模态资产，并将 evidence facts 并入 literature_mining。"""
        from app.services.multimodal_service import get_multimodal_service, detect_modality
        from app.services.dataset_service import DatasetService

        mm = get_multimodal_service(self.db)
        ds_service = DatasetService(self.db)
        for ds in ds_service.get_project_datasets(project_id):
            if detect_modality(ds.filename, ds.data_type) in ("text", "image", "audio"):
                try:
                    mm.sync_from_dataset(ds, research_question)
                except Exception as exc:
                    logger.warning(f"同步多模态资产失败 {ds.filename}: {exc}")

        ctx = mm.get_multimodal_context(project_id)
        results["multimodal"] = ctx
        mm_facts = ctx.get("multimodal_evidence") or []
        if mm_facts:
            lm = results.get("literature_mining") or {}
            if isinstance(lm, dict):
                lm = dict(lm)
                existing = list(lm.get("facts") or [])
                existing_ids = {f.get("fact_id") for f in existing if f.get("fact_id")}
                for f in mm_facts:
                    if f.get("fact_id") not in existing_ids:
                        existing.append(f)
                lm["facts"] = existing
                lm["multimodal_evidence"] = mm_facts
                lm["multimodal_evidence_count"] = len(mm_facts)
                results["literature_mining"] = lm
        return ctx

    def _exec_knowledge_gap(
        self,
        literature_mining: Optional[Dict],
        project_id: str = "",
        problem_understanding: Optional[Dict] = None,
    ) -> dict:
        agent = get_knowledge_gap_agent()
        lm = self._enrich_literature_mining(literature_mining)
        facts = lm.get("facts", [])
        uncertain_points = lm.get("uncertain_points", [])
        pu = problem_understanding if isinstance(problem_understanding, dict) else {}
        rq = resolve_research_question_from_pu(
            pu,
            fallback=self.db_pipeline_run.research_question if self.db_pipeline_run else "",
        )
        expected = pu.get("expected_output") or []
        if isinstance(expected, list):
            expected_summary = "; ".join(str(x) for x in expected if x)[:500]
        else:
            expected_summary = str(expected)[:500] if expected else ""
        result = agent.analyze(
            facts=facts,
            uncertain_points=uncertain_points,
            research_question=rq,
            main_contradiction=str(pu.get("main_contradiction") or "")[:500],
            expected_output_summary=expected_summary,
        )
        kg_result = self._safe_model_dump(result)
        gaps = kg_result.get("knowledge_gaps", [])
        self._record_closed_loop_event(
            "knowledge_gap",
            payload={"gap_count": len(gaps) if isinstance(gaps, list) else 0},
        )
        return kg_result
    
    def _exec_hypothesis_generation(
        self,
        problem_understanding: Optional[Dict],
        literature_mining: Optional[Dict],
        knowledge_gap: Optional[Dict],
        ideation_novelty: Optional[Dict] = None,
    ) -> dict:
        agent = get_hypothesis_generation_agent()
        pu = problem_understanding or {}
        lm = self._enrich_literature_mining(literature_mining)
        kg = knowledge_gap or {}
        research_question = resolve_research_question_from_pu(
            pu,
            fallback=self.db_pipeline_run.research_question if self.db_pipeline_run else "",
        )
        num_ideas = int(self._run_options.get("num_ideas", 3))
        extra_constraints = list(self._discovery_refinement or []) + list(
            self._validation_feedback_constraints or []
        ) + list(self._human_feedback_constraints or [])
        extra_constraints.extend(build_scientific_logic_constraints(pu))

        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        data_context = self._build_data_context(project_id)

        literature_facts = list(lm.get("facts") or [])
        multimodal_facts = list(data_context.get("multimodal_evidence") or [])
        merged_facts = literature_facts + multimodal_facts
        logger.info(
            "[Hypothesis] 输入事实: literature=%s multimodal=%s library_docs=%s",
            len(literature_facts),
            len(multimodal_facts),
            lm.get("project_library_document_count"),
        )

        memory_pack: Dict[str, Any] = {}
        experiment_memory_guidance = ""
        if self._run_options.get("enable_experiment_memory_retrieve", True) and project_id:
            try:
                from app.services.experiment_memory import retrieve_guidance

                memory_pack = retrieve_guidance(project_id, research_question)
                experiment_memory_guidance = str(memory_pack.get("guidance") or "")
            except Exception as mem_err:
                logger.warning(f"实验记忆检索跳过: {mem_err}")

        result = agent.generate(
            research_question=research_question,
            facts=merged_facts,
            knowledge_gaps=kg.get("knowledge_gaps", []),
            constraints=list(pu.get("constraints") or []),
            project_id=project_id,
            data_context=data_context,
            project_mode=self._get_project_mode(project_id),
            num_ideas=num_ideas,
            ideation_context=ideation_novelty,
            extra_constraints=extra_constraints,
            multimodal_evidence=multimodal_facts,
            experiment_memory_guidance=experiment_memory_guidance,
        )
        result_dict = self._safe_model_dump(result)
        # 供下游 / 调试：记录本次实际喂给假设生成的文献事实规模
        result_dict["literature_facts_used"] = len(literature_facts)
        result_dict["literature_mining_enriched"] = {
            "evidence_facts": lm.get("evidence_facts"),
            "project_library_document_count": lm.get("project_library_document_count"),
            "verified_references_count": lm.get("verified_references_count"),
        }
        if memory_pack:
            skill_outputs = dict(result_dict.get("skill_outputs") or {})
            skill_outputs["experiment_memory"] = {
                "enabled": memory_pack.get("enabled", True),
                "count": memory_pack.get("count", 0),
                "guidance": experiment_memory_guidance[:2000],
                "record_ids": [
                    r.get("record_id")
                    for r in (memory_pack.get("records") or [])
                    if isinstance(r, dict)
                ],
            }
            result_dict["skill_outputs"] = skill_outputs
        if multimodal_facts:
            result_dict["multimodal_evidence"] = multimodal_facts
            result_dict["input_data"] = result_dict.get("input_data") or {}
            if isinstance(result_dict["input_data"], dict):
                result_dict["input_data"]["multimodal_evidence"] = multimodal_facts

        # ── 问题对齐检查 ──
        if research_question and result_dict.get("hypotheses"):
            try:
                alignment = self._run_alignment_skill(research_question, result_dict["hypotheses"])
                result_dict["alignment"] = alignment

                # 如果所有假设都 off_topic，重试一次
                all_off_topic = alignment.get("all_off_topic", False)
                if all_off_topic and alignment.get("off_topic_summary"):
                    logger.warning(
                        f"所有假设偏题，触发重试。摘要: {alignment['off_topic_summary'][:200]}"
                    )
                    retry = agent.generate(
                        research_question=research_question,
                        facts=merged_facts,
                        knowledge_gaps=kg.get("knowledge_gaps", []),
                        constraints=[
                            alignment["off_topic_summary"]
                        ],
                        project_id=project_id,
                        data_context=data_context,
                        num_ideas=num_ideas,
                        ideation_context=ideation_novelty,
                        extra_constraints=extra_constraints,
                        multimodal_evidence=multimodal_facts,
                        experiment_memory_guidance=experiment_memory_guidance,
                    )
                    result_dict = self._safe_model_dump(retry)
                    # 重试后再做一次对齐检查
                    if result_dict.get("hypotheses"):
                        result_dict["alignment"] = self._run_alignment_skill(
                            research_question, result_dict["hypotheses"]
                        )
            except Exception as align_err:
                logger.warning(f"问题对齐检查失败: {align_err}")

        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        if result_dict.get("hypotheses"):
            from app.core.iterative_science import attach_verifiable_specs_to_hypotheses

            mode = self._get_project_mode(project_id)
            fl_context = (data_context.get("fl_context") or {}) if data_context else {}
            result_dict = attach_verifiable_specs_to_hypotheses(
                result_dict,
                project_mode=mode,
                fl_context=fl_context,
            )

        return result_dict

    def _exec_hypothesis_tree(self, results: Dict[str, Any], research_question: str) -> Dict[str, Any]:
        from app.services.hypothesis_tree_service import get_hypothesis_tree_service

        hg = results.get("hypothesis_generation") or {}
        hypotheses = hg.get("hypotheses") or []
        if not hypotheses:
            return {}

        alignment_data = hg.get("alignment") or {}
        alignments = alignment_data.get("alignments") or []
        lit = results.get("literature_mining") or {}
        facts = lit.get("facts") or []

        tree_svc = get_hypothesis_tree_service()
        tree = tree_svc.build_and_prune(hypotheses, alignments, facts, max_branches=3)
        hg["hypothesis_tree"] = tree

        sel_idx = tree.get("selected_hypothesis_index", 0)
        if sel_idx < len(hypotheses):
            selected = hypotheses[sel_idx]
            hg["primary_hypothesis"] = selected
            hg["hypotheses"] = [selected] + [
                h for i, h in enumerate(hypotheses) if i != sel_idx and not h.get("off_topic")
            ][:2]

        results["hypothesis_generation"] = hg
        self._record_closed_loop_event(
            "hypothesis_tree",
            {
                "round": 1,
                "selected_branch": tree.get("selected_branch_id"),
                "composite_score": (tree.get("branches") or [{}])[0].get("composite_score") if tree.get("branches") else None,
                "summary": tree.get("iteration_summary"),
                "quality_trend": tree.get("quality_trend"),
            },
        )
        return tree
    
    def _exec_hypothesis_review(self, hypothesis_generation: Optional[Dict]) -> dict:
        from app.agents.hypothesis_review_agent import HypothesisCandidate
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        agent = get_hypothesis_review_agent()
        hg = self._hydrate_hypothesis_generation(hypothesis_generation, project_id)
        hypotheses = hg.get("hypotheses", [])
        if not hypotheses:
            logger.warning(
                "[Pipeline] 假设评估无候选假设 run_id=%s project_id=%s",
                self.run_id,
                project_id,
            )
        alignment_data = hg.get("alignment", {})
        alignments = alignment_data.get("alignments", []) if alignment_data else []
        enriched_candidates = []
        for i, h in enumerate(hypotheses):
            enriched_candidates.append(
                HypothesisCandidate(
                    hypothesis=h.get("hypothesis", ""),
                    rationale=h.get("rationale", ""),
                    novelty=h.get("novelty", ""),
                    testability=h.get("testability", ""),
                    required_data=h.get("required_data", ""),
                    possible_method=h.get("possible_method", ""),
                    risk=h.get("risk", ""),
                    supporting_fact_ids=h.get("supporting_fact_ids") or [],
                    validation_target=h.get("validation_target") or "",
                    expected_measurable_effect=h.get("expected_measurable_effect") or "",
                    evidence_level=h.get("evidence_level") or "",
                    verifiable_spec=h.get("verifiable_spec") or {},
                )
            )
        candidates = enriched_candidates or [
            HypothesisCandidate(
                hypothesis=h.get("hypothesis", ""),
                rationale=h.get("rationale", ""),
                novelty=h.get("novelty", ""),
                testability=h.get("testability", ""),
                required_data=h.get("required_data", ""),
                possible_method=h.get("possible_method", ""),
                risk=h.get("risk", ""),
            )
            for h in hypotheses
        ]
        original_candidates = candidates
        lit_mining = self._stage_results.get("literature_mining", {})

        result = agent.review(
            hypotheses=candidates,
            retrieved_papers=self._build_retrieved_papers(lit_mining),
            literature_facts=lit_mining.get("facts", []),
            alignments=alignments,
            original_hypotheses=original_candidates,
            research_question=self.db_pipeline_run.research_question if self.db_pipeline_run else "",
        )
        result_dict = self._safe_model_dump(result)
        ensemble = (result_dict.get("skill_outputs") or {}).get("ensemble_review") or {}
        if ensemble:
            self._record_closed_loop_event(
                "ensemble_review",
                {
                    "round": 2,
                    "overall": ensemble.get("overall"),
                    "decision": ensemble.get("decision"),
                    "quality_trend": [
                        {"stage": "hypothesis_tree", "score": (hg.get("hypothesis_tree") or {}).get("branches", [{}])[0].get("composite_score")},
                        {"stage": "ensemble_review", "score": ensemble.get("overall")},
                    ],
                },
            )
        if ensemble:
            result_dict["primary_index"] = ensemble.get("target_hypothesis_index", 0)
            result_dict["ensemble_decision"] = ensemble.get("decision")
            result_dict["ensemble_overall"] = ensemble.get("overall")
        if project_id:
            try:
                self._apply_hypothesis_review_scores(project_id, hg, result_dict)
            except Exception as exc:
                logger.warning(f"回写假设评审分数失败: {exc}")

        from app.core.iterative_science import assess_evidence_sufficiency

        for i, rev in enumerate(result_dict.get("reviews") or []):
            if i < len(hypotheses) and isinstance(hypotheses[i], dict):
                suff = assess_evidence_sufficiency(hypotheses[i])
                rev["evidence_provenance"] = suff
                rev["evidence_sufficiency"] = suff.get("evidence_sufficiency")
                rev["missing_evidence_types"] = suff.get("missing_evidence_types")

        adv_mode = self._run_options.get("adversarial_mode", "off")
        if self._run_options.get("enable_pro_con_adversarial", False) and adv_mode != "off":
            try:
                from app.services.pro_con_adversarial_service import get_pro_con_adversarial_service

                result_dict = get_pro_con_adversarial_service().enhance_review(
                    result_dict,
                    hypotheses=hypotheses,
                    literature_facts=lit_mining.get("facts", []),
                    research_question=self.db_pipeline_run.research_question if self.db_pipeline_run else "",
                    mode=adv_mode,
                    max_con_rounds=int(self._run_options.get("con_challenge_max_rounds", 2)),
                    enable_evolution=bool(self._run_options.get("enable_hypothesis_evolution", True)),
                )
                ensemble = (result_dict.get("skill_outputs") or {}).get("ensemble_review") or {}
                if ensemble:
                    result_dict["primary_index"] = ensemble.get("target_hypothesis_index", result_dict.get("primary_index"))
                    result_dict["ensemble_decision"] = ensemble.get("decision")
                    result_dict["ensemble_overall"] = ensemble.get("overall")
            except Exception as adv_err:
                logger.warning(f"红蓝对抗包装失败（已跳过，不影响后续阶段）: {adv_err}")

        # 红蓝对抗后：simplify / out_of_box 候选池（1B，不覆盖主假设）
        if self._run_options.get("enable_hypothesis_post_evolution", True):
            try:
                from app.skills.reasoning.hypothesis_evolution_skill import (
                    attach_evolution_to_review,
                    evolve_hypothesis_candidates,
                )

                skill_out = result_dict.get("skill_outputs") or {}
                pro_con = skill_out.get("pro_con_adversarial") or {}
                evo = evolve_hypothesis_candidates(
                    research_question=(
                        self.db_pipeline_run.research_question if self.db_pipeline_run else ""
                    ),
                    reviews=list(result_dict.get("reviews") or []),
                    primary_index=int(result_dict.get("primary_index") or 0),
                    pro_con_evolution=(pro_con.get("evolution") if isinstance(pro_con, dict) else None),
                )
                result_dict = attach_evolution_to_review(result_dict, evo)
            except Exception as evo_err:
                logger.warning(f"假设演化候选生成失败（已跳过，不影响后续阶段）: {evo_err}")

        return result_dict
    
    def _apply_hypothesis_review_scores(
        self,
        project_id: str,
        hypothesis_generation: Dict[str, Any],
        review_result: Dict[str, Any],
    ) -> None:
        """将集成评审结果回写至 DB 假设记录。"""
        try:
            HypothesisService(self.db).apply_review_scores_to_hypotheses(
                project_id,
                hypothesis_generation,
                review_result,
            )
        except Exception as exc:
            logger.warning(f"回写假设评审分数失败: {exc}")
    
    def _exec_iterative_experiment(
        self,
        hypothesis_review: Optional[Dict],
        project_id: str = "",
        project_mode: str = "general",
    ) -> Dict[str, Any]:
        """单一阶段：迭代实验（替换原实验设计 + 小样验证）。"""
        hr = hypothesis_review or {}
        reviews = hr.get("reviews") or []
        primary_idx = hr.get("primary_index")
        if primary_idx is None:
            ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
            primary_idx = ensemble.get("target_hypothesis_index", 0)
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0
        hypothesis_text = ""
        if reviews:
            primary_idx = min(max(0, primary_idx), len(reviews) - 1)
            hypothesis_text = (reviews[primary_idx] or {}).get("hypothesis") or ""

        from app.services.iterative_experiment_service import get_iterative_experiment_service

        out = get_iterative_experiment_service().build_pipeline_stage_output(
            project_id, hypothesis_text
        )
        # 无数据阻断时，标记 executability，防止盲目出报告伪成功
        if out.get("status") == "blocked_need_data":
            self._executability_blocked = True
        return out

    def _mark_stage_human_review(self, stage_idx: int, reason: str) -> None:
        """将阶段标记为需人工复核。"""
        db_stage = self.db_stage_executions.get(stage_idx + 1)
        if not db_stage:
            return
        db_stage.status = DB_PipelineStatus.HUMAN_REVIEW_REQUIRED
        meta = db_stage.extra_metadata if isinstance(db_stage.extra_metadata, dict) else {}
        meta["human_review_reason"] = reason
        db_stage.extra_metadata = meta
        try:
            self.db.commit()
        except Exception:
            pass

    @staticmethod
    def _report_payload_from_iterative_experiment(
        results: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """报告只读 iterative_experiment；内部仍映射为 agent 现有 ed/sv 入参形状。"""
        from app.services.iterative_experiment_service import resolve_ed_sv_from_results

        return resolve_ed_sv_from_results(results)

    @staticmethod
    def _flatten_ed_sv_fields(results: Dict[str, Any]) -> Dict[str, Any]:
        """PipelineRunResult 扁平字段：ie + 派生 ed/sv。"""
        from app.services.iterative_experiment_service import resolve_ed_sv_from_results

        ie, ed, sv = resolve_ed_sv_from_results(results)
        return {
            "iterative_experiment": ie or None,
            "experiment_design": ed or None,
            "small_validation": sv or None,
        }

    def _exec_report_generation(
        self,
        results: Dict[str, Any],
        pipeline_run_info: Optional[Dict] = None,
        project_mode: str = "general",
    ) -> dict:
        agent = get_report_generation_agent()
        pu = results.get("problem_understanding", {})
        lm = self._enrich_literature_mining(results.get("literature_mining", {}))
        results["literature_mining"] = lm
        kg = results.get("knowledge_gap", {})
        hg = results.get("hypothesis_generation", {})
        hr = results.get("hypothesis_review", {})
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        # 优先从「迭代实验」页勾选结果快照注入，避免依赖 Pipeline 阶段 6 自动跑实验
        if project_id:
            try:
                from app.services.iterative_experiment_service import get_iterative_experiment_service

                snap = get_iterative_experiment_service().snapshot_for_report(project_id)
                if isinstance(snap, dict) and snap.get("experiments"):
                    results["iterative_experiment"] = snap
            except Exception as snap_err:
                logger.warning("[报告生成] 注入迭代实验快照失败: %s", snap_err)
        ie, ed, sv = self._report_payload_from_iterative_experiment(results)

        evidence_facts, citation_map, verified_references = self._normalize_literature_bundle(lm)

        project_info = {
            "title": "研究项目",
            "id": self.run_id,
            "project_mode": project_mode,
            "iterative_experiment_id": ie.get("primary_experiment_id"),
            "report_experiment_ids": ie.get("report_experiment_ids") or [],
        }

        multimodal_datasets = []
        ed_skill_outputs = ed.get("skill_outputs", {}) if isinstance(ed, dict) else {}
        ingest_output = ed_skill_outputs.get("multimodal_data_ingest", {})
        if isinstance(ingest_output, dict) and ingest_output.get("data"):
            multimodal_datasets = ingest_output["data"].get("datasets", [])

        preliminary_analysis_outputs = sv.get("skill_outputs", {}) if isinstance(sv, dict) else {}

        data_context = {}
        if project_id:
            data_context = self._build_data_context(project_id)
        data_context = self._merge_data_acquisition_context(data_context, results)
        hg_input = hg.get("input_data") or hg
        if isinstance(hg_input, dict) and hg_input.get("data_context"):
            data_context = {**data_context, **hg_input.get("data_context", {})}
        data_context = {
            **data_context,
            "iterative_experiment": {
                "status": ie.get("status"),
                "primary_experiment_id": ie.get("primary_experiment_id"),
                "report_experiment_ids": ie.get("report_experiment_ids") or [],
                "experiment_count": len(ie.get("experiments") or []),
                "provider": ie.get("provider"),
            },
        }

        result = agent.generate_report(
            project_info=project_info,
            problem_understanding=pu,
            literature_facts=evidence_facts,
            citation_map=citation_map,
            knowledge_gaps=kg,
            all_hypotheses=hg.get("hypotheses", []),
            final_hypothesis=hr,
            experiment_design=ed,
            small_validation=sv,
            pipeline_run_info=pipeline_run_info,
            novelty_review_skill_outputs=hr.get("skill_outputs"),
            sanity_check_skill_outputs=ed.get("skill_outputs") if isinstance(ed, dict) else None,
            evidence_facts=evidence_facts,
            verified_references=verified_references,
            preliminary_analysis_skill_outputs=preliminary_analysis_outputs,
            multimodal_datasets=multimodal_datasets,
            data_context=data_context,
            project_mode=project_mode,
        )
        result_dict = self._safe_model_dump(result)
        result_dict["iterative_experiment_ref"] = {
            "primary_experiment_id": ie.get("primary_experiment_id"),
            "report_experiment_ids": ie.get("report_experiment_ids") or [],
            "status": ie.get("status"),
        }

        hypothesis = (ed.get("hypothesis") if isinstance(ed, dict) else "") or ""
        reviews = hr.get("reviews") or []
        if not hypothesis and reviews:
            hypothesis = reviews[0].get("hypothesis", "")
        data_rows = []
        for ds in multimodal_datasets:
            data_rows.extend((ds.get("preview") or [])[:100])
        result_dict = self._apply_plot_quality_loop(
            result_dict,
            hypothesis=hypothesis,
            data_rows=data_rows or None,
        )
        if result_dict.get("human_review_required"):
            self._mark_stage_human_review(6, "图表 VLM 评审未达标，需人工复核")

        return result_dict

    def _exec_evidence_reasoning(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        from app.services.evidence_reasoning_service import get_evidence_reasoning_service

        hg = results.get("hypothesis_generation", {})
        lm = self._enrich_literature_mining(results.get("literature_mining", {}))
        results["literature_mining"] = lm
        hypotheses = hg.get("hypotheses", [])
        if not hypotheses:
            return {}

        multimodal_facts: List[Dict[str, Any]] = []
        try:
            data_ctx = self._build_data_context(project_id)
            multimodal_facts = list(data_ctx.get("multimodal_evidence") or [])
            if multimodal_facts:
                lm["multimodal_evidence"] = multimodal_facts
                results["literature_mining"] = lm
        except Exception:
            pass

        service = get_evidence_reasoning_service()
        output = service.run_for_hypotheses_sync(
            hypotheses=hypotheses,
            research_question=research_question,
            literature_mining=lm,
            max_rounds=int(self._run_options.get("evidence_reasoning_max_rounds", 1)),
            multimodal_facts=multimodal_facts,
        )
        hg["hypotheses"] = output.get("hypotheses", hypotheses)
        hg["evidence_reasoning"] = output
        results["hypothesis_generation"] = hg
        results["evidence_reasoning"] = output

        revision_history = output.get("revision_history") or []
        if revision_history:
            self._iteration_snapshots.append({
                "round": len(revision_history),
                "label": "evidence_reasoning",
                "hypothesis": (output.get("hypotheses") or [{}])[0].get("hypothesis", "")[:300]
                if output.get("hypotheses")
                else "",
                "revision_count": len(revision_history),
                "revision_history": revision_history[:6],
            })
            self._record_closed_loop_event(
                "evidence_reasoning_loop",
                {
                    "rounds": len(revision_history),
                    "summary": f"证据链迭代 {len(revision_history)} 轮",
                    "revision_count": len(revision_history),
                },
            )

        logger.info(
            f"[EvidenceReasoning] 完成 {len(output.get('hypotheses', []))} 条假设证据链迭代"
            f" (multimodal={len(multimodal_facts)})"
        )
        return output
    
    def _save_hypotheses(self, project_id: str, research_question: str, results: Dict[str, Any]):
        """保存假设和证据链到数据库"""
        HypothesisService(self.db).persist_hypotheses_from_pipeline_results(
            project_id,
            research_question,
            results,
            apply_reviews=False,
        )
    
    @staticmethod
    def _safe_model_dump(obj) -> dict:
        """安全地将 Pydantic 模型转为字典"""
        if obj is None:
            return {}
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            return [PipelineService._safe_model_dump(item) for item in obj]
        return obj
    
    # ────────────── 数据库操作 ──────────────
    
    def _create_pipeline_run(self, request: PipelineRunRequest):
        """创建 Pipeline 运行记录"""
        logger.info(f"创建 PipelineRun 记录 run_id={self.run_id} project_id={request.project_id}")
        set_prompt_project_id(request.project_id)
        prompt_svc = get_prompt_override_service(self.db)
        overrides_used = {}
        for d in STAGE_DEFS:
            info = prompt_svc.get_prompt_info(request.project_id, d["key"])
            if info.get("has_override"):
                overrides_used[d["key"]] = True
        self.db_pipeline_run = DB_PipelineRun(
            id=str(uuid.uuid4()),
            run_id=self.run_id,
            project_id=request.project_id,
            research_question=request.research_question,
            status=DB_PipelineStatus.RUNNING,
            started_at=datetime.now(CHINA_TZ),
            input_data=request.model_dump(),
            version=1,
            prompt_versions_used={"overrides": overrides_used} if overrides_used else None,
            extra_metadata={"run_options": resolve_run_options((request.options or {}))},
        )
        self.db.add(self.db_pipeline_run)
        self.db.commit()
        self.db.refresh(self.db_pipeline_run)
    
    def _create_stage_execution(self, order: int, stage: DB_PipelineStage, input_data: Dict[str, Any]) -> DB_PipelineStageExecution:
        """创建或更新阶段执行记录"""
        from app.services.data_finder_slim import slim_stage_input

        input_data = slim_stage_input(input_data)
        now = datetime.now(CHINA_TZ)
        existing = self.db_stage_executions.get(order)
        if existing:
            existing.status = DB_PipelineStatus.RUNNING
            existing.started_at = now
            existing.input_data = input_data
            existing.error_message = None
            self.db.commit()
            return existing

        db_stage = DB_PipelineStageExecution(
            id=str(uuid.uuid4()),
            pipeline_run_id=self.db_pipeline_run.id,
            stage=stage,
            stage_order=order,
            status=DB_PipelineStatus.RUNNING,
            started_at=now,
            input_data=input_data
        )
        self.db.add(db_stage)
        self.db.commit()
        self.db.refresh(db_stage)
        self.db_stage_executions[order] = db_stage
        return db_stage
    
    def _update_stage_execution(self, db_stage: DB_PipelineStageExecution, status: str, output: Optional[Any] = None, error: Optional[str] = None):
        """更新阶段执行记录"""
        from app.services.data_finder_slim import slim_stage_output

        now = datetime.now(CHINA_TZ)
        stage_key = db_stage.stage.value if hasattr(db_stage.stage, "value") else str(db_stage.stage or "")
        if status == "completed":
            db_stage.status = DB_PipelineStatus.COMPLETED
            if output is not None:
                db_stage.output_data = slim_stage_output(output, stage_key=stage_key)
        elif status == "failed":
            db_stage.status = DB_PipelineStatus.FAILED
            if error:
                db_stage.error_message = error
        
        if db_stage.started_at:
            db_stage.completed_at = now
            # 如果 started_at 数据库返回的是 naive datetime，而 now 是 tz-aware，需要统一处理
            started = db_stage.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=CHINA_TZ)
            db_stage.duration_ms = int((now - started).total_seconds() * 1000)
        
        self.db.commit()
    
    def _complete_pipeline_run(self, completed_at: datetime, total_duration_ms: int, results: Dict[str, Any], final_report_id: Optional[str]):
        from app.services.data_finder_slim import slim_results_for_checkpoint

        safe_results = slim_results_for_checkpoint(results)
        self.db_pipeline_run.status = DB_PipelineStatus.COMPLETED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = total_duration_ms
        self.db_pipeline_run.output_data = safe_results
        self.db_pipeline_run.current_stage = None
        # ── 持久化大家长提示到 output_data ──
        if self._coordinator_hints:
            safe_results["coordinator_hints"] = self._coordinator_hints
            self.db_pipeline_run.output_data = safe_results
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        meta["auxiliary_results"] = {
            k: safe_results[k]
            for k in (
                "data_finder", "evidence_reasoning",
                "ideation_novelty", "discovery_loop", "teaching_auto_refinement",
                "federated_campaign_refinement", "counterfactual_preview",
            )
            if k in safe_results
        }
        meta["run_options"] = self._run_options
        meta["version_snapshots"] = self._iteration_snapshots or (
            (results.get("federated_campaign_refinement") or {}).get("version_snapshots")
            or (results.get("discovery_loop") or {}).get("version_snapshots")
            or (results.get("teaching_auto_refinement") or {}).get("version_snapshots")
            or []
        )

        from app.services.closed_loop_quality_service import compute_quality_acceptance

        meta["quality_acceptance"] = compute_quality_acceptance(
            quality_trend=meta.get("quality_trend"),
            closed_loop_events=meta.get("closed_loop_events"),
            discovery_loop=results.get("discovery_loop"),
            hypothesis_review=results.get("hypothesis_review"),
        )
        try:
            self._run_science_iteration_hooks("finalize", results, "", "", "general")
        except Exception:
            pass
        self._record_closed_loop_event(
            "quality_acceptance",
            {
                "verdict": meta["quality_acceptance"].get("verdict"),
                "summary": meta["quality_acceptance"].get("summary"),
                "accepted": meta["quality_acceptance"].get("accepted"),
                "score_improved": meta["quality_acceptance"].get("score_improved"),
            },
        )
        self.db_pipeline_run.extra_metadata = meta
        if final_report_id:
            self.db_pipeline_run.final_report_id = final_report_id
        try:
            self.db.commit()
            logger.info(f"[Pipeline] pipeline run {self.run_id} 已标记为 COMPLETED")
        except Exception:
            logger.exception("_complete_pipeline_run: commit 失败")

        try:
            project = self.db.query(Project).filter(Project.id == self.db_pipeline_run.project_id).first()
            if project:
                project.status = ProjectStatus.COMPLETED
                project.updated_at = completed_at
                self.db.commit()
                logger.info(f"[Pipeline] 项目 {project.id} 状态已更新为 COMPLETED")
            else:
                logger.warning(f"[Pipeline] 项目 {self.db_pipeline_run.project_id} 未找到，无法更新状态")
        except Exception:
            logger.exception("_complete_pipeline_run: 更新项目状态失败")

    def _record_closed_loop_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """记录闭环迭代事件，供前端展示质量趋势。"""
        if not self.db_pipeline_run:
            return
        meta = dict(self.db_pipeline_run.extra_metadata or {})
        events = list(meta.get("closed_loop_events") or [])
        from datetime import datetime, timezone, timedelta
        events.append({
            "type": event_type,
            "at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            **payload,
        })
        meta["closed_loop_events"] = events[-20:]
        trend = list(meta.get("quality_trend") or [])
        entries = infer_quality_trend_entries(event_type, payload)
        for entry in entries:
            trend.append(enrich_quality_trend_entry(entry, event_type, payload))
        meta["quality_trend"] = trend[-15:]
        self._persist_extra_metadata(meta)
        if events:
            self._persist_audit_record("closed_loop_event", events[-1])
        if trend:
            self._persist_audit_record("quality_trend_entry", trend[-1])
        try:
            self.db.commit()
        except Exception:
            pass
    
    def _fail_pipeline_run(self, completed_at: datetime, total_duration_ms: int, failed_stage_name: Optional[str], error: str):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db_pipeline_run.status = DB_PipelineStatus.FAILED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = total_duration_ms
        self.db_pipeline_run.error_message = error
        self.db_pipeline_run.current_stage = None
        if failed_stage_name:
            try:
                self.db_pipeline_run.failed_stage = DB_PipelineStage(failed_stage_name)
            except ValueError:
                self.db_pipeline_run.failed_stage = DB_PipelineStage.PROBLEM_UNDERSTANDING
        try:
            self.db.commit()
        except Exception:
            logger.exception("_fail_pipeline_run: commit 失败")
    
    @staticmethod
    def _build_retrieved_papers(lit_mining: Dict[str, Any]) -> List[Dict[str, Any]]:
        papers = []
        citation_map = lit_mining.get("citation_map", [])
        for cit in citation_map:
            papers.append({
                "title": cit.get("paper_title") or cit.get("title", ""),
                "authors": cit.get("authors", ""),
                "abstract": "",
                "external_id": cit.get("external_id", ""),
                "source_url": cit.get("source_url", ""),
            })
        return papers

    def _persist_pipeline_report(self, project_id: str, results: Dict[str, Any]) -> Optional[str]:
        """将 Pipeline 报告阶段结果落库（支持内存全量、截断摘要与磁盘 JSON）。"""
        from app.services.data_finder_slim import (
            find_recent_report_data_on_disk,
            load_report_data_from_storage,
            resolve_report_generation_payload,
        )

        stage_data = results.get("report_generation")
        memory_data = self._stage_results.get("report_generation")
        storage_data: Dict[str, Any] = {}
        for candidate in (
            (stage_data or {}).get("report_id") if isinstance(stage_data, dict) else None,
            (memory_data or {}).get("report_id") if isinstance(memory_data, dict) else None,
        ):
            if candidate:
                storage_data = load_report_data_from_storage(str(candidate))
                if storage_data:
                    break
        if not storage_data:
            started = self._pipeline_start.timestamp() if self._pipeline_start else None
            storage_data = find_recent_report_data_on_disk(
                not_before_ts=started - 120 if started else None,
                not_after_ts=datetime.now(CHINA_TZ).timestamp() + 120,
            )

        payload = resolve_report_generation_payload(
            stage_data,
            memory_fallback=memory_data,
            storage_fallback=storage_data,
        )
        if not payload:
            logger.warning(
                f"[Pipeline] 报告落库跳过：未解析到有效报告数据 run_id={self.run_id} project_id={project_id}"
            )
            return None
        return self._create_report(project_id, payload)

    def _create_report(self, project_id: str, report_data: Dict[str, Any]) -> Optional[str]:
        """创建报告记录"""
        from app.services.data_finder_slim import resolve_report_generation_payload

        report_data = resolve_report_generation_payload(
            report_data,
            memory_fallback=self._stage_results.get("report_generation"),
        )
        if not report_data:
            return None
        report_id = str(uuid.uuid4())
        title = report_data.get("paper_title", report_data.get("title", "研究报告"))
        chapters = report_data.get("chapters", {}) if isinstance(report_data.get("chapters"), dict) else {}
        file_report_id = report_data.get("report_id")

        def _to_text(val):
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, (list, dict)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)

        extra_meta = merge_report_extra_metadata(
            report_data.get("compliance_check") or {},
            report_data,
        )

        report = Report(
            id=report_id,
            project_id=project_id,
            title=title,
            paper_title=title,
            paper_abstract=_to_text(report_data.get("paper_abstract", "")),
            markdown_content="",
            problem_statement=_to_text(chapters.get("problem_statement", "")),
            rationale=_to_text(chapters.get("rationale", "")),
            technical_details=_to_text(chapters.get("technical_details", "")),
            datasets=_to_text(chapters.get("datasets", "")),
            source=_to_text(chapters.get("source", "")),
            target=_to_text(chapters.get("target", "")),
            methods=_to_text(chapters.get("methods", "")),
            experiments=_to_text(chapters.get("experiments", "")),
            results=_to_text(chapters.get("results", "")),
            references=json.dumps(chapters.get("references", []), ensure_ascii=False) if isinstance(chapters.get("references"), list) else _to_text(chapters.get("references", "")),
            created_at=datetime.now(CHINA_TZ),
            pdf_path=file_report_id or report_data.get("pdf_path"),
            status="ready",
            extra_metadata=extra_meta,
        )
        self.db.add(report)
        self.db.commit()
        return report_id


# ────────────── 工具函数 ──────────────

    def _build_data_context(self, project_id: str) -> dict:

        from app.services.dataset_service import DatasetService

        ds_service = DatasetService(self.db)

        from app.services.data_finder_slim import slim_data_context

        try:
            data_context = ds_service.get_project_data_context(project_id)
        except Exception as e:
            logger.error(f"获取项目数据上下文失败: {e}")
            data_context = {
                "dataset_count": 0,
                "available_modalities": [],
                "datasets": [],
                "field_candidates": [],
                "target_candidates": [],
                "quality_summary": {},
                "warnings": [f"获取数据上下文失败: {str(e)}"],
            }

        data_context = slim_data_context(data_context)
        # FL 模式：注入实验范式上下文（不改 Pipeline 阶段）
        try:
            from app.models.project import Project
            from app.services.fl_pack_service import (
                FlPackService,
                fl_pack_enabled,
                get_fl_pack_service,
            )

            if fl_pack_enabled():
                proj = self.db.query(Project).filter(Project.id == project_id).first()
                if proj and getattr(proj, "project_mode", None) == "federated_learning":
                    cfg = proj.config if isinstance(proj.config, dict) else {}
                    pack = cfg.get("fl_pack") or {}
                    paradigm = FlPackService.get_experiment_paradigm_context_from_config(cfg)
                    if not paradigm:
                        paradigm = get_fl_pack_service().build_experiment_paradigm_context(
                            fl_setting=FlPackService.get_fl_setting_from_config(cfg),
                            profile_id=FlPackService.get_experiment_profile_id_from_config(cfg),
                        )
                    data_context = {
                        **data_context,
                        "fl_experiment_profile": FlPackService.get_experiment_profile_id_from_config(
                            cfg
                        ),
                        "fl_experiment_context": paradigm,
                        "fl_pack_checklists_excerpt": pack.get("checklists_excerpt") or "",
                        "fl_pack_failure_cases": pack.get("failure_cases") or [],
                    }
                    if not data_context.get("fl_context"):
                        setting = FlPackService.get_fl_setting_from_config(cfg)
                        data_context["fl_context"] = {
                            "fl_setting": (
                                "vertical_fl" if setting == "vfl" else "horizontal_fl"
                            ),
                            "project_mode": "federated_learning",
                            "experiment_profile": data_context["fl_experiment_profile"],
                        }
        except Exception as exc:
            logger.debug("注入 FL 实验范式上下文失败: %s", exc)
        return data_context

    @staticmethod
    def _run_alignment_skill(research_question: str, hypotheses: List[Dict]) -> Dict[str, Any]:
        """运行问题对齐 Skill"""
        import asyncio
        from app.skills.reasoning.question_alignment_skill import QuestionAlignmentSkill

        async def _run():
            skill = QuestionAlignmentSkill()
            result = await skill.run(
                input_data={
                    "research_question": research_question,
                    "hypotheses": hypotheses,
                },
                context={"stage": "hypothesis_generation"},
            )
            return result

        try:
            skill_result = asyncio.run(_run())
            return skill_result.data
        except Exception as e:
            logger.warning(f"QuestionAlignmentSkill 异常: {e}")
            return {"alignments": [], "all_off_topic": False, "off_topic_summary": ""}


def _find_failed_stage(stages: List[PipelineStageLog]) -> Optional[PipelineStageLog]:
    """找到第一个失败的阶段"""
    for stage in stages:
        if stage.status == PipelineStageStatus.FAILED:
            return stage
    return None


def get_pipeline_service(db: Session) -> PipelineService:
    """获取 PipelineService 实例"""
    return PipelineService(db)