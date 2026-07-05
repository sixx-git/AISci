"""
Pipeline 服务 - 负责按顺序执行各个 Agent
"""
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

from app.agents.problem_understanding_agent import get_problem_understanding_agent
from app.agents.literature_mining_agent import get_literature_mining_agent
from app.agents.knowledge_gap_agent import get_knowledge_gap_agent
from app.agents.hypothesis_generation_agent import get_hypothesis_generation_agent
from app.agents.hypothesis_review_agent import get_hypothesis_review_agent
from app.agents.experiment_design_agent import get_experiment_design_agent
from app.agents.small_validation_agent import get_small_validation_agent
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
from app.core.pipeline_exceptions import HitlGatePause, DataUploadPause, SingleStageRerunComplete, LiteratureNotFoundError
from app.core.quality_scoring import enrich_quality_trend_entry
from app.services.loops.closed_loop_helpers import (
    build_data_gap_loop_payload,
    infer_quality_trend_entries,
)
from app.core.execution_metadata import annotate_validation_execution_metadata
from app.services.hypothesis_service import HypothesisService
from app.services.qwen_client import get_call_logs, clear_call_logs, CallLog
from app.services.prompt_context import set_project_id as set_prompt_project_id
from app.services.stage_human_loop_service import STAGE_KEY_ORDER, StageHumanLoopService
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
    {"idx": 2, "key": "data_acquisition", "stage_enum": PipelineStage.DATA_ACQUISITION,
     "db_stage_enum": DB_PipelineStage.DATA_ACQUISITION, "label": "多源数据采集"},
    {"idx": 3, "key": "knowledge_gap", "stage_enum": PipelineStage.KNOWLEDGE_GAP,
     "db_stage_enum": DB_PipelineStage.KNOWLEDGE_GAP, "label": "知识缺口"},
    {"idx": 4, "key": "hypothesis_generation", "stage_enum": PipelineStage.HYPOTHESIS_GENERATION,
     "db_stage_enum": DB_PipelineStage.HYPOTHESIS_GENERATION, "label": "假设生成"},
    {"idx": 5, "key": "hypothesis_review", "stage_enum": PipelineStage.HYPOTHESIS_REVIEW,
     "db_stage_enum": DB_PipelineStage.HYPOTHESIS_REVIEW, "label": "假设评估"},
    {"idx": 6, "key": "experiment_design", "stage_enum": PipelineStage.EXPERIMENT_DESIGN,
     "db_stage_enum": DB_PipelineStage.EXPERIMENT_DESIGN, "label": "实验设计"},
    {"idx": 7, "key": "small_validation", "stage_enum": PipelineStage.SMALL_VALIDATION,
     "db_stage_enum": DB_PipelineStage.SMALL_VALIDATION, "label": "小样验证"},
    {"idx": 8, "key": "report_generation", "stage_enum": PipelineStage.REPORT_GENERATION,
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
        self._finalize_report_after_gate: bool = False
        self._skip_to_post_validation: bool = False
        self._last_pilot_results: Dict[str, Any] = {}
        self._teaching_refinement_count: int = 0
        self._federated_campaign_count: int = 0
        self._fed_campaign_discovery_done: set = set()
        self._iteration_snapshots: List[Dict[str, Any]] = []
        self._executability_blocked: bool = False

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
    ) -> str:
        """从指定阶段重新运行：默认仅重跑本阶段，保留上下游结果。"""
        if from_stage not in STAGE_KEY_ORDER:
            raise ValueError(f"无效 stage: {from_stage}")
        if rerun_mode not in ("single_stage", "from_stage_onward"):
            raise ValueError(f"无效 rerun_mode: {rerun_mode}")

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
        self.db_pipeline_run = DB_PipelineRun(
            id=str(uuid.uuid4()),
            run_id=self.run_id,
            project_id=project_id,
            research_question=parent.research_question,
            status=DB_PipelineStatus.PENDING,
            input_data={"rerun_from": from_stage, "parent_run_id": parent_run_id},
            version=version,
            extra_metadata={
                "parent_run_id": parent_run_id,
                "rerun_from_stage": from_stage,
                "rerun_mode": rerun_mode,
                "use_human_modified_output": use_human_modified_output,
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
        self._rerun_single_stage_only = rerun_mode == "single_stage"
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
        du_gate_early = meta.get("data_upload_gate") or {}
        data_upload_continue = bool(
            meta.get("pipeline_checkpoint")
            and (du_gate_early.get("resumed") or du_gate_early.get("continued_at"))
        )
        if meta.get("rerun_from_stage") and not data_upload_continue:
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
            self._parent_run_id_for_rerun = parent_id

        gate = meta.get("hitl_gate") or {}
        if gate.get("resumed") and meta.get("pipeline_checkpoint"):
            self._checkpoint_resume = dict(meta["pipeline_checkpoint"])
            self._human_feedback_constraints = list(gate.get("feedback_constraints") or [])
            gate["resumed"] = False
            gate["paused"] = False
            meta["hitl_gate"] = gate
            self.db_pipeline_run.extra_metadata = meta
            try:
                self.db.commit()
            except Exception:
                pass

        du_gate = meta.get("data_upload_gate") or {}
        cp = meta.get("pipeline_checkpoint")
        if cp and (
            du_gate.get("resumed")
            or (not du_gate.get("paused") and du_gate.get("continued_at"))
        ):
            self._checkpoint_resume = dict(cp)
            du_gate["resumed"] = False
            du_gate["paused"] = False
            meta["data_upload_gate"] = du_gate
            self._persist_extra_metadata(meta)
            try:
                self.db.commit()
            except Exception:
                pass

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

    def _is_quick_report_run(self) -> bool:
        if self._run_options.get("enable_quick_report"):
            return True
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        if meta.get("quick_report"):
            return True
        input_data = self.db_pipeline_run.input_data if isinstance(self.db_pipeline_run.input_data, dict) else {}
        opts = input_data.get("options") if isinstance(input_data.get("options"), dict) else {}
        return bool(opts.get("enable_quick_report"))

    def _persist_extra_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """合并写入 extra_metadata（SQLite JSON 列需 flag_modified）。"""
        merged = dict(self.db_pipeline_run.extra_metadata or {})
        merged.update(meta)
        self.db_pipeline_run.extra_metadata = merged
        flag_modified(self.db_pipeline_run, "extra_metadata")
        return merged

    def _rebuild_checkpoint_from_stages(self) -> Dict[str, Any]:
        """从已完成阶段 output 重建 checkpoint（元数据丢失时的兜底）。"""
        results: Dict[str, Any] = {}
        if not self.db_pipeline_run:
            return {"results": results, "resume_phase": "after_data_acquisition"}
        stages = (
            self.db.query(DB_PipelineStageExecution)
            .filter(DB_PipelineStageExecution.pipeline_run_id == self.db_pipeline_run.id)
            .order_by(DB_PipelineStageExecution.stage_order)
            .all()
        )
        key_by_stage = {d["db_stage_enum"]: d["key"] for d in STAGE_DEFS}
        for s in stages:
            if s.status != DB_PipelineStatus.COMPLETED or not s.output_data:
                continue
            key = key_by_stage.get(s.stage)
            if key:
                results[key] = s.output_data
        return {"results": self._checkpoint_safe_results(results), "resume_phase": "after_data_acquisition"}

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
        rq = pu.get("research_question") or (
            self.db_pipeline_run.research_question if self.db_pipeline_run else ""
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

    def _build_discovery_refined_context(
        self,
        results: Dict[str, Any],
        refinement_notes: List[str],
    ) -> Dict[str, Any]:
        """从评审弱点 + ideation 方向构建文献刷新 query。"""
        ideation = results.get("ideation_novelty") or {}
        angles = list(ideation.get("suggested_angles") or [])[:3]
        avoid = list(ideation.get("avoid_topics") or [])[:2]
        gaps = results.get("knowledge_gap") or {}
        gap_texts = []
        for g in (gaps.get("knowledge_gaps") or gaps.get("gaps") or [])[:3]:
            if isinstance(g, dict):
                gap_texts.append(str(g.get("gap") or g.get("description") or "")[:80])
            elif g:
                gap_texts.append(str(g)[:80])

        refinement_queries = list(refinement_notes or [])[:6]
        refinement_queries.extend(gap_texts)
        keywords = angles + [f"NOT {a}" for a in avoid if a]
        pu = results.get("problem_understanding") or {}
        if pu.get("keywords"):
            kw = pu["keywords"]
            if isinstance(kw, list):
                keywords.extend(kw[:5])
            elif isinstance(kw, str):
                keywords.extend(k.strip() for k in kw.split(",") if k.strip())

        return {
            "refinement_queries": refinement_queries,
            "keywords": list(dict.fromkeys(k for k in keywords if k))[:10],
            "suggested_angles": angles,
        }

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

        fp = sv.get("federated_pilot") or {}
        if fp:
            mode = fp.get("execution_mode", "")
            gate = fp.get("alignment_gate") or {}
            if gate and not gate.get("skipped") and not gate.get("passed"):
                constraints.append(
                    f"VFL 对齐 gate 未通过: {gate.get('reason', '')}；"
                    "下一轮须先满足 alignment_success_rate 阈值再设计训练实验。"
                )
            if fp.get("best_method"):
                constraints.append(
                    f"联邦 pilot 最佳方法={fp.get('best_method')}（mode={mode}）；"
                    "实验设计须围绕该结果做对照/ablation。"
                )
            from app.core.iterative_science import actions_to_feedback_constraints

            actions = fp.get("replan_actions") or (
                (fp.get("skill_outputs") or {}).get("federated_replanning") or {}
            ).get("replan_actions") or []
            constraints.extend(actions_to_feedback_constraints(actions))

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

        ed = results.get("experiment_design") or {}
        sv = results.get("small_validation") or {}
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

        snapshot = {
            "round": round_num,
            "label": label or f"R{round_num}",
            "hypothesis": (reviews[primary_idx].get("hypothesis") if reviews else "") or "",
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

        ed = results.get("experiment_design") or {}
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

        ed = results.get("experiment_design") or {}
        self._validation_feedback_constraints = self._build_validation_feedback_constraints(
            validation_result, ed
        )
        self._last_pilot_results = self._build_pilot_results_payload(validation_result)

        sv = validation_result or {}
        fp = sv.get("federated_pilot") or {}
        if fp:
            gate = fp.get("alignment_gate") or {}
            self._record_closed_loop_event(
                "federated_campaign",
                {
                    "execution_mode": fp.get("execution_mode"),
                    "best_method": fp.get("best_method"),
                    "gate_passed": gate.get("passed") if gate else None,
                    "replan_actions": (fp.get("replan_actions") or [])[:4],
                    "summary": fp.get("analysis", {}).get("summary") or fp.get("result_source", ""),
                    "quality_trend_entry": {
                        "stage": "federated_pilot",
                        "score": 8.5 if fp.get("execution_mode") == "uploaded_csv"
                        else (5.0 if fp.get("execution_mode") == "gate_blocked" else 6.5),
                        "label": "联邦 Pilot",
                    },
                },
            )

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

    def _exec_literature_mining_refresh(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
        discovery_round: int,
        refinement_notes: List[str],
    ) -> dict:
        """Discovery 回退：刷新文献库检索与外部论文搜索。"""
        ctx = self._build_discovery_refined_context(results, refinement_notes)
        agent = get_literature_mining_agent()
        previous = results.get("literature_mining") or {}
        response = agent.mine_discovery_refresh(
            project_id=project_id,
            research_question=research_question,
            refinement_queries=ctx["refinement_queries"],
            keywords=ctx["keywords"],
            previous=previous if isinstance(previous, dict) else None,
            discovery_round=discovery_round,
            top_k=15,
            db=self.db,
        )
        return self._enrich_literature_mining(self._safe_model_dump(response))

    def _discovery_rollback_to_ideation(
        self,
        stages: List[PipelineStageLog],
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        project_mode: str,
        round_num: int,
        refinement_notes: List[str],
    ) -> Dict[str, Any]:
        """低分 Discovery 回退：刷新文献 → 知识缺口 → ideation → 再进入假设生成。"""
        logger.info(f"[Discovery R{round_num}] 回退到 ideation 并刷新文献")

        self._run_stage(
            stages, 1, results, research_question, project_id,
            lambda: self._exec_literature_mining_refresh(
                project_id, research_question, results, round_num, refinement_notes,
            ),
        )
        lm = results.get("literature_mining") or {}
        refresh_meta = lm.get("discovery_refresh") if isinstance(lm, dict) else {}

        self._run_stage(
            stages, 3, results, research_question, project_id,
            lambda: self._exec_knowledge_gap(lm, project_id),
        )

        try:
            df_out = self._exec_data_acquisition(
                project_id,
                research_question,
                results,
                project_mode,
                refinement_queries=refinement_notes,
            )
            refresh_meta = dict(refresh_meta or {})
            refresh_meta["data_finder_rerun"] = True
            refresh_meta["data_finder_tables"] = len(
                (df_out.get("extract") or {}).get("extracted_tables") or []
            )
        except Exception as df_err:
            logger.warning(f"Discovery R{round_num} Data Finder 重跑失败: {df_err}")

        ideation = {}
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
                        "round": round_num,
                        "novelty_score": ideation.get("novelty_score"),
                        "external_papers": ideation.get("external_papers_count"),
                        "summary": (ideation.get("assessment") or "")[:200],
                        "quality_trend_entry": {
                            "stage": f"ideation_r{round_num}",
                            "score": ideation.get("novelty_score"),
                        },
                    },
                )
        except Exception as exc:
            logger.warning(f"Discovery R{round_num} ideation 失败: {exc}")

        self._record_closed_loop_event(
            "discovery_literature_refresh",
            {
                "round": round_num,
                "facts_before": (refresh_meta or {}).get("facts_before"),
                "facts_after": (refresh_meta or {}).get("facts_after"),
                "new_facts": (refresh_meta or {}).get("new_facts"),
                "search_query": ((refresh_meta or {}).get("search_query") or "")[:120],
                "quality_trend_entry": {
                    "stage": f"literature_r{round_num}",
                    "score": min(10.0, 5.0 + float((refresh_meta or {}).get("new_facts") or 0)),
                },
            },
        )

        return {
            "round": round_num,
            "literature_refresh": refresh_meta,
            "ideation_novelty_score": ideation.get("novelty_score") if ideation else None,
            "refinement_count": len(refinement_notes),
        }

    def _needs_teaching_auto_refinement(self, results: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """P2-6: 判断 Teaching 模式是否需从实验设计自动重跑。"""
        sv = results.get("small_validation") or {}
        ed = results.get("experiment_design") or {}
        reasons: List[str] = []

        sb = sv.get("sandbox_execution") or {}
        if sb and not sb.get("success"):
            reasons.append("沙箱验证失败")

        sc = ((ed.get("skill_outputs") or {}).get("experiment_sanity_check") or {}).get("data") or {}
        if sc and sc.get("executable") is False:
            reasons.append("实验 sanity check 未通过")

        gate = ed.get("executability_gate") or {}
        if gate and not gate.get("passed"):
            reasons.append(
                f"实验可执行性 Gate 未通过 (score={gate.get('score')})"
            )

        if sv.get("human_review_required"):
            reasons.append("验证阶段标记需人工复核")

        pq = sv.get("plot_quality") or {}
        if pq.get("needs_human_review"):
            reasons.append("图表质量未达标")

        return bool(reasons), reasons

    def _run_teaching_auto_refinement(
        self,
        stages: List[PipelineStageLog],
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        project_mode: str,
    ) -> Optional[Dict[str, Any]]:
        """P2-6: Teaching 轻量自动闭环 — 验证/sanity 失败时重跑实验设计→验证→报告。"""
        if self._run_options.get("pipeline_mode") != PipelineMode.TEACHING.value:
            return None
        if not self._run_options.get("enable_teaching_auto_refinement", True):
            return None
        max_rounds = int(self._run_options.get("teaching_auto_refinement_max", 1))
        if self._teaching_refinement_count >= max_rounds:
            return None

        needs, reasons = self._needs_teaching_auto_refinement(results)
        if not needs:
            return None

        self._teaching_refinement_count += 1
        round_num = self._teaching_refinement_count
        logger.info(f"[Teaching] 自动闭环 R{round_num}: {reasons}")

        pre_snapshot = self._capture_iteration_snapshot(round_num, results, label=f"teaching_R{round_num}_before")
        self._validation_feedback_constraints = self._build_validation_feedback_constraints(
            results.get("small_validation"),
            results.get("experiment_design"),
        )
        self._last_pilot_results = self._build_pilot_results_payload(results.get("small_validation"))

        self._record_closed_loop_event(
            "teaching_auto_refinement",
            {
                "round": round_num,
                "reasons": reasons,
                "quality_trend_entry": {"stage": f"teaching_refine_r{round_num}", "score": 5.0},
            },
        )

        self._run_stage(stages, 6, results, research_question, project_id,
            lambda: self._exec_experiment_design(
                results.get("hypothesis_review"), project_id, project_mode,
            ))
        self._apply_executability_gate(results, project_id, round_num=round_num)
        if not (
            self._executability_blocked
            and self._run_options.get("enable_executability_gate", True)
        ):
            self._run_stage(stages, 7, results, research_question, project_id,
                lambda: self._exec_small_validation(
                    results.get("experiment_design"),
                    results.get("hypothesis_review"),
                    project_id,
                    project_mode,
                ))
        sv_result = results.get("small_validation")
        if isinstance(sv_result, dict):
            self._apply_post_validation_updates(results, sv_result)
        self._executability_blocked = False

        def _exec_report():
            return self._exec_report_generation(results, self._build_pipeline_run_info(), project_mode)

        self._run_stage(stages, 8, results, research_question, project_id, _exec_report)
        final_report_id = self._create_report(project_id, results.get("report_generation", {}))
        post_snapshot = self._capture_iteration_snapshot(round_num, results, label=f"teaching_R{round_num}_after")

        return {
            "round": round_num,
            "reasons": reasons,
            "reran": True,
            "report_ran": True,
            "final_report_id": final_report_id,
            "snapshot_before": pre_snapshot,
            "snapshot_after": post_snapshot,
            "version_snapshots": list(self._iteration_snapshots),
        }

    def _run_federated_campaign_refinement(
        self,
        stages: List[PipelineStageLog],
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        project_mode: str,
        discovery_round: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """联邦 Campaign 自动第二轮：pilot 反馈 → 修订实验设计 → 重跑 pilot。"""
        if project_mode != ProjectMode.FEDERATED_LEARNING.value:
            return None
        if not self._run_options.get("enable_federated_campaign_loop", True):
            return None

        if discovery_round:
            dedup_key = f"discovery_r{discovery_round}"
            if dedup_key in self._fed_campaign_discovery_done:
                return None
        else:
            max_rounds = int(self._run_options.get("federated_campaign_max", 2))
            if self._federated_campaign_count >= max_rounds - 1:
                return None

        from app.core.iterative_science import (
            evaluate_pilot_improvement,
            needs_federated_campaign_refinement,
        )

        sv = results.get("small_validation") or {}
        needs, reasons = needs_federated_campaign_refinement(sv)
        if not needs:
            return None

        if discovery_round:
            self._fed_campaign_discovery_done.add(f"discovery_r{discovery_round}")
            round_num = discovery_round
        else:
            self._federated_campaign_count += 1
            round_num = self._federated_campaign_count + 1

        pilot_before = dict(sv.get("federated_pilot") or {})

        logger.info(f"[Federated Campaign] 自动 R{round_num}: {reasons}")

        pre_snapshot = self._capture_iteration_snapshot(
            round_num, results, label=f"FL_Campaign_R{round_num}_before"
        )
        self._validation_feedback_constraints = self._build_validation_feedback_constraints(
            sv, results.get("experiment_design")
        )
        self._last_pilot_results = self._build_pilot_results_payload(sv)

        self._record_closed_loop_event(
            "federated_campaign_refine",
            {
                "round": round_num,
                "reasons": reasons,
                "pilot_mode_before": pilot_before.get("execution_mode"),
                "quality_trend_entry": {"stage": f"federated_r{round_num}", "score": 5.5},
            },
        )

        self._run_stage(stages, 6, results, research_question, project_id,
            lambda: self._exec_experiment_design(
                results.get("hypothesis_review"), project_id, project_mode,
            ))
        self._run_stage(stages, 7, results, research_question, project_id,
            lambda: self._exec_small_validation(
                results.get("experiment_design"),
                results.get("hypothesis_review"),
                project_id,
                project_mode,
            ))
        sv_after = results.get("small_validation")
        if isinstance(sv_after, dict):
            self._apply_post_validation_updates(results, sv_after)

        pilot_after = (sv_after or {}).get("federated_pilot") or {}
        improvement = evaluate_pilot_improvement(pilot_before, pilot_after)
        post_snapshot = self._capture_iteration_snapshot(
            round_num, results, label=f"FL_Campaign_R{round_num}_after"
        )

        self._record_closed_loop_event(
            "federated_campaign",
            {
                "round": round_num,
                "execution_mode": pilot_after.get("execution_mode"),
                "best_method": pilot_after.get("best_method"),
                "gate_passed": (pilot_after.get("alignment_gate") or {}).get("passed"),
                "replan_actions": (pilot_after.get("replan_actions") or [])[:4],
                "summary": improvement.get("summary"),
                "improved": improvement.get("improved"),
                "quality_trend_entry": {
                    "stage": f"federated_pilot_r{round_num}",
                    "score": 8.0 if improvement.get("improved") else 5.5,
                    "label": f"FL R{round_num}",
                },
            },
        )

        return {
            "round": round_num,
            "reasons": reasons,
            "reran": True,
            "improvement": improvement,
            "snapshot_before": pre_snapshot,
            "snapshot_after": post_snapshot,
            "pilot_before_mode": pilot_before.get("execution_mode"),
            "pilot_after_mode": pilot_after.get("execution_mode"),
            "version_snapshots": list(self._iteration_snapshots),
        }

    def _run_discovery_loop(
        self,
        stages: List[PipelineStageLog],
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        project_mode: str,
    ) -> Dict[str, Any]:
        """P5: Discovery 模式 — while not accept: ideate → experiment → write → review → refine。"""
        max_rounds = int(self._run_options.get("discovery_max_rounds", 3))
        history: List[Dict[str, Any]] = []
        final_report_id = None

        self._capture_iteration_snapshot(1, results, label="R1_initial")

        for round_num in range(2, max_rounds + 1):
            meta = (
                self.db_pipeline_run.extra_metadata
                if self.db_pipeline_run and isinstance(self.db_pipeline_run.extra_metadata, dict)
                else {}
            )
            from app.services.loops.discovery_runner import (
                check_discovery_acceptance,
                check_discovery_stagnation,
            )

            continuation = check_discovery_stagnation(
                meta.get("quality_trend"),
                round_num=round_num,
                min_improvement_delta=float(
                    self._run_options.get("min_improvement_delta", 3.0)
                ),
            )
            if continuation.get("action") == "stop_stagnant":
                self._record_closed_loop_decision(
                    trigger="cqs_stagnant",
                    action="stop_discovery",
                    reason=continuation.get("reason", "CQS 停滞"),
                    next_stage="human_review",
                    round_num=round_num,
                    metadata={"cqs_delta": continuation.get("cqs_delta")},
                )
                history.append({
                    "round": round_num,
                    "status": "stagnant",
                    "overall": None,
                    "stagnation": continuation,
                })
                break

            hr = results.get("hypothesis_review") or {}
            accepted, accept_meta = check_discovery_acceptance(
                hr,
                results.get("small_validation") or {},
                project_mode=project_mode,
            )
            if accepted:
                history.append({
                    "round": round_num - 1,
                    "status": accept_meta.get("status", "accepted"),
                    "overall": accept_meta.get("overall"),
                    **({k: v for k, v in accept_meta.items() if k not in ("status", "overall")}),
                })
                break

            ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
            decision = ensemble.get("decision") or hr.get("ensemble_decision")
            overall = ensemble.get("overall") or hr.get("ensemble_overall")
            fed_accept = accept_meta.get("federated_acceptance") or {}

            weaknesses = list(ensemble.get("weaknesses") or [])[:4]
            suggestions = list(ensemble.get("revision_suggestions") or [])[:4]
            self._discovery_refinement = weaknesses + suggestions
            if project_mode == ProjectMode.FEDERATED_LEARNING.value and fed_accept.get("blockers"):
                self._discovery_refinement.extend(fed_accept["blockers"][:3])
            pre_snapshot = self._capture_iteration_snapshot(round_num - 1, results, label=f"R{round_num - 1}_before_refine")
            df_before = None
            try:
                from app.services.data_finder_service import get_data_finder_service

                df_before = get_data_finder_service(self.db).load_results(project_id)
            except Exception:
                pass

            history.append({
                "round": round_num,
                "status": "refining",
                "decision": decision,
                "overall": overall,
                "refinement_notes": self._discovery_refinement,
                "snapshot_before": pre_snapshot,
            })
            self._record_closed_loop_event(
                "discovery_refine",
                {
                    "round": round_num,
                    "decision": decision,
                    "overall": overall,
                    "quality_trend_entry": {"stage": f"discovery_r{round_num}", "score": overall},
                },
            )

            self._record_closed_loop_decision(
                trigger="ensemble_not_accept",
                action="discovery_refine",
                reason=f"评审未 Accept (decision={decision}, overall={overall})",
                next_stage="literature_refresh",
                round_num=round_num,
                metadata={"weaknesses": weaknesses[:3]},
            )

            rollback_meta = self._discovery_rollback_to_ideation(
                stages,
                results,
                research_question,
                project_id,
                project_mode,
                round_num,
                self._discovery_refinement,
            )
            history[-1]["rollback"] = rollback_meta

            self._validation_feedback_constraints = self._build_validation_feedback_constraints(
                results.get("small_validation"),
                results.get("experiment_design"),
            )
            self._last_pilot_results = self._build_pilot_results_payload(results.get("small_validation"))

            self._run_stage(stages, 4, results, research_question, project_id,
                lambda: self._exec_hypothesis_generation(
                    results.get("problem_understanding"),
                    results.get("literature_mining"),
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
            except Exception:
                pass
            try:
                self._exec_hypothesis_tree(results, research_question)
            except Exception:
                pass
            try:
                self._save_hypotheses(project_id, research_question, results)
            except Exception:
                pass

            self._run_stage(stages, 5, results, research_question, project_id,
                lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
            self._run_stage(stages, 6, results, research_question, project_id,
                lambda: self._exec_experiment_design(
                    results.get("hypothesis_review"), project_id, project_mode,
                ))
            self._apply_executability_gate(results, project_id, round_num=round_num)
            skip_validation = self._executability_blocked and self._run_options.get(
                "enable_executability_gate", True
            )
            if not skip_validation:
                self._run_stage(stages, 7, results, research_question, project_id,
                    lambda: self._exec_small_validation(
                        results.get("experiment_design"),
                        results.get("hypothesis_review"),
                        project_id,
                        project_mode,
                    ))
            sv_result = results.get("small_validation")
            if isinstance(sv_result, dict):
                self._apply_post_validation_updates(results, sv_result)
            elif skip_validation:
                self._record_closed_loop_decision(
                    trigger="executability_blocked",
                    action="skip_validation",
                    reason="可执行性 Gate 未通过，跳过本轮沙箱验证",
                    next_stage="report_generation",
                    round_num=round_num,
                )

            if project_mode == ProjectMode.FEDERATED_LEARNING.value:
                fed_ref = self._run_federated_campaign_refinement(
                    stages,
                    results,
                    research_question,
                    project_id,
                    project_mode,
                    discovery_round=round_num,
                )
                if fed_ref:
                    history[-1]["federated_campaign"] = fed_ref
                    fed_accept = evaluate_discovery_federated_acceptance(
                        results.get("hypothesis_review") or {}, results.get("small_validation") or {}
                    )
                    history[-1]["federated_acceptance"] = fed_accept

            def _exec_report():
                return self._exec_report_generation(
                    results, self._build_pipeline_run_info(), project_mode,
                )

            self._run_stage(stages, 8, results, research_question, project_id, _exec_report)
            final_report_id = self._create_report(project_id, results.get("report_generation", {}))
            post_snapshot = self._capture_iteration_snapshot(round_num, results, label=f"R{round_num}_after_refine")
            history[-1]["snapshot_after"] = post_snapshot

            from app.core.closed_loop_decisions import build_iteration_causal_summary

            df_after = None
            try:
                from app.services.data_finder_service import get_data_finder_service

                df_after = get_data_finder_service(self.db).load_results(project_id)
            except Exception:
                pass
            causal = build_iteration_causal_summary(
                pre_snapshot,
                post_snapshot,
                rollback_meta=rollback_meta,
                data_finder_before=df_before,
                data_finder_after=df_after,
                refinement_notes=self._discovery_refinement,
            )
            history[-1].update(causal)
            self._executability_blocked = False

        return {
            "pipeline_mode": PipelineMode.DISCOVERY.value,
            "max_rounds": max_rounds,
            "rounds_executed": len(history) + 1,
            "history": history,
            "final_report_id": final_report_id,
            "version_snapshots": self._iteration_snapshots,
        }

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
            self._record_closed_loop_event(
                "plot_vlm_critique",
                {
                    "round": results.get("discovery_loop", {}).get("rounds_executed", 1),
                    "average_score": avg,
                    "needs_human_review": loop.get("needs_human_review"),
                    "quality_trend_entry": {"stage": "plot_critique", "score": avg},
                },
            )
        return result

    def _run_pipeline_stages(self, research_question: str, project_id: str) -> PipelineRunResult:
        """执行 Pipeline 所有阶段（支持从中间阶段 rerun）。"""
        project_mode = self._get_project_mode(project_id)
        self._run_options = self._get_run_options()
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
            f"num_ideas={self._run_options.get('num_ideas')} start_idx={start_idx} ======"
        )

        stages: List[PipelineStageLog] = [
            PipelineStageLog(stage=d["stage_enum"], status=PipelineStageStatus.PENDING)
            for d in STAGE_DEFS
        ]

        results: Dict[str, Any] = dict(self._seeded_results or {})
        for idx, d in enumerate(STAGE_DEFS):
            if idx < start_idx:
                key = d["key"]
                if key in results:
                    stages[idx].status = PipelineStageStatus.COMPLETED
                    stages[idx].output_data = results[key]
                else:
                    exec_row = self.db_stage_executions.get(idx + 1)
                    if exec_row and exec_row.output_data:
                        stages[idx].status = PipelineStageStatus.COMPLETED
                        stages[idx].output_data = exec_row.output_data
                        results[key] = exec_row.output_data

        if getattr(self, "_checkpoint_resume", None):
            cp = self._checkpoint_resume
            cp_results = cp.get("results") or {}
            if isinstance(cp_results, dict):
                results.update(cp_results)
            resume_phase = cp.get("resume_phase") or ""
            if resume_phase == "after_hypothesis_generation":
                start_idx = max(start_idx, 5)
            elif resume_phase == "after_hypothesis_review":
                start_idx = max(start_idx, 6)
            elif resume_phase == "after_experiment_design":
                start_idx = max(start_idx, 7)
            elif resume_phase == "after_small_validation":
                start_idx = max(start_idx, 8)
                self._skip_to_post_validation = True
            elif resume_phase == "after_data_acquisition":
                start_idx = 3
            elif resume_phase == "after_report_generation":
                start_idx = max(start_idx, 8)
                self._finalize_report_after_gate = True
            self._checkpoint_resume = None
            logger.info(f"[Pipeline] 从 HITL checkpoint 恢复 phase={resume_phase} start_idx={start_idx}")

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

            if start_idx <= 2:
                self._run_stage(stages, 2, results, research_question, project_id,
                    lambda: self._exec_data_acquisition(project_id, research_question, results, project_mode))

                self._maybe_pause_for_data_upload(project_id, results)
            
            # ── 阶段 4: KnowledgeGapAgent ──
            if start_idx <= 3:
                self._run_stage(stages, 3, results, research_question, project_id,
                    lambda: self._exec_knowledge_gap(
                        results.get("literature_mining"),
                        project_id,
                    ))
            
            # ── 阶段 5: HypothesisGenerationAgent ──
            if start_idx <= 4:
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

                self._run_stage(stages, 4, results, research_question, project_id,
                    lambda: self._exec_hypothesis_generation(
                        results.get("problem_understanding"),
                        results.get("literature_mining"),
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
                self._maybe_pause_for_hitl_gate("hypothesis_generation", results)
            
            # ── 阶段 6: HypothesisReviewAgent ──
            if start_idx <= 5:
                self._run_stage(stages, 5, results, research_question, project_id,
                    lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
                self._maybe_pause_for_hitl_gate("hypothesis_review", results)
            
            # ── 阶段 7: ExperimentDesignAgent ──
            if start_idx <= 6:
                self._run_stage(stages, 6, results, research_question, project_id,
                    lambda: self._exec_experiment_design(
                        results.get("hypothesis_review"),
                        project_id,
                        project_mode,
                    ))
                self._apply_executability_gate(results, project_id)
                self._maybe_pause_for_hitl_gate("experiment_design", results)
            
            # ── 阶段 7: SmallValidationAgent ──
            teaching_report_ran = False
            skip_validation_run = getattr(self, "_skip_to_post_validation", False)
            if self._executability_blocked and self._run_options.get("enable_executability_gate", True):
                skip_validation_run = True
            if start_idx <= 7 and not skip_validation_run:
                self._run_stage(stages, 7, results, research_question, project_id,
                    lambda: self._exec_small_validation(
                        results.get("experiment_design"),
                        results.get("hypothesis_review"),
                        project_id,
                        project_mode,
                    ))
                sv_first = results.get("small_validation")
                if isinstance(sv_first, dict):
                    self._apply_post_validation_updates(results, sv_first)
                if project_mode == ProjectMode.FEDERATED_LEARNING.value:
                    self._capture_iteration_snapshot(1, results, label="FL_Campaign_R1")
                if self._run_options.get("pipeline_mode") == PipelineMode.TEACHING.value:
                    self._capture_iteration_snapshot(0, results, label="teaching_R0_initial")
                self._maybe_pause_for_hitl_gate("small_validation", results)
            elif skip_validation_run:
                sv_first = results.get("small_validation")
                if isinstance(sv_first, dict):
                    self._apply_post_validation_updates(results, sv_first)
                self._skip_to_post_validation = False

            # ── 联邦 Campaign 自动第二轮（实验设计→pilot 迭代）──
            if start_idx <= 7 and project_mode == ProjectMode.FEDERATED_LEARNING.value:
                fed_campaign_meta = self._run_federated_campaign_refinement(
                    stages, results, research_question, project_id, project_mode
                )
                if fed_campaign_meta:
                    results["federated_campaign_refinement"] = fed_campaign_meta

            # ── P2-6: Teaching 轻量自动闭环 ──
            if start_idx <= 7:
                teaching_meta = self._run_teaching_auto_refinement(
                    stages, results, research_question, project_id, project_mode
                )
                if teaching_meta:
                    results["teaching_auto_refinement"] = teaching_meta
                    if teaching_meta.get("final_report_id"):
                        final_report_id = teaching_meta["final_report_id"]
                        teaching_report_ran = True
            
            # ── 阶段 9: ReportGenerationAgent ──
            if getattr(self, "_finalize_report_after_gate", False):
                self._finalize_report_after_gate = False
                final_report_id = self._create_report(project_id, results.get("report_generation", {}))
            elif start_idx <= 8 and not teaching_report_ran:
                def _exec_report():
                    pipeline_run_info = self._build_pipeline_run_info()
                    return self._exec_report_generation(
                        results, pipeline_run_info, project_mode
                    )
                self._run_stage(stages, 8, results, research_question, project_id, _exec_report)
                self._maybe_pause_for_hitl_gate("report_generation", results)
                final_report_id = self._create_report(project_id, results.get("report_generation", {}))

            # ── P5: Discovery 开放循环（Sakana-like）──
            if start_idx <= 4 and self._run_options.get("pipeline_mode") == PipelineMode.DISCOVERY.value:
                discovery_meta = self._run_discovery_loop(
                    stages, results, research_question, project_id, project_mode
                )
                if discovery_meta:
                    results["discovery_loop"] = discovery_meta
                    if discovery_meta.get("final_report_id"):
                        final_report_id = discovery_meta["final_report_id"]
            
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
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
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
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
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
            final_report_id = self.db_pipeline_run.final_report_id
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
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
                report_generation=results.get('report_generation'),
                final_report=results.get('report_generation'),
                final_report_id=final_report_id,
                run_id=self.run_id,
                extra_metadata=self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else None,
                created_at=pipeline_start,
                completed_at=pipeline_end,
                failed_stage=None,
            )

        except DataUploadPause as pause:
            pipeline_end = datetime.now(CHINA_TZ)
            total_duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            logger.info(
                f"[Pipeline] 数据上传暂停 run_id={self.run_id} pending={pause.pending_count}"
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
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
                report_generation=results.get('report_generation'),
                run_id=self.run_id,
                extra_metadata=meta,
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
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
                report_generation=results.get('report_generation'),
                final_report=results.get('report_generation'),
                final_report_id=None,
                run_id=self.run_id,
                created_at=pipeline_start,
                completed_at=pipeline_end,
                failed_stage=failed_stage_name
            )
    
    # ────────────── 阶段执行 ──────────────

    def _pending_manual_upload_count(self, project_id: str) -> int:
        from app.services.data_finder_service import get_data_finder_service
        from app.services.external_candidate_service import (
            STATUS_PENDING,
            list_manual_candidates,
        )

        try:
            df = get_data_finder_service(self.db).load_results(project_id) or {}
            manual = list_manual_candidates(df.get("external_candidates"))
            return sum(1 for c in manual if c.get("user_upload_status") == STATUS_PENDING)
        except Exception:
            return 0

    def _uploaded_manual_count(self, project_id: str) -> int:
        from app.services.data_finder_service import get_data_finder_service
        from app.services.external_candidate_service import (
            STATUS_MERGED,
            list_manual_candidates,
        )

        try:
            df = get_data_finder_service(self.db).load_results(project_id) or {}
            manual = list_manual_candidates(df.get("external_candidates"))
            return sum(1 for c in manual if c.get("user_upload_status") == STATUS_MERGED)
        except Exception:
            return 0

    def _refresh_data_acquisition_results(
        self,
        project_id: str,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        from app.services.data_finder_service import get_data_finder_service

        from app.services.data_finder_slim import slim_data_acquisition_output, slim_data_finder_payload

        final = get_data_finder_service(self.db).load_results(project_id) or {}
        slim_final = slim_data_finder_payload(final)
        da = final.get("data_acquisition") or {}
        output = {
            "data_acquisition": da,
            "search": slim_final,
            "extract": slim_final,
            "paper_link_extractions": final.get("paper_extractions", [])[:20],
            "refinement_queries": results.get("data_acquisition", {}).get("refinement_queries", [])
            if isinstance(results.get("data_acquisition"), dict)
            else [],
            "gap_enrichment": final.get("gap_enrichment") or {},
        }
        results["data_acquisition"] = slim_data_acquisition_output(output)
        results["data_finder"] = results["data_acquisition"]
        return results

    def resume_after_data_upload(self, run_id: str, *, force: bool = False) -> Dict[str, Any]:
        """一键报告：用户上传外部数据后继续 Pipeline。"""
        self.db_pipeline_run = self.db.query(DB_PipelineRun).filter(
            DB_PipelineRun.run_id == run_id
        ).first()
        if not self.db_pipeline_run:
            raise ValueError(f"Pipeline run 未找到: {run_id}")

        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        gate = dict(meta.get("data_upload_gate") or {})
        status_val = self.db_pipeline_run.status
        project_id = self.db_pipeline_run.project_id or ""
        uploaded = self._uploaded_manual_count(project_id)
        if not gate.get("paused"):
            if (
                self._is_quick_report_run()
                and status_val == DB_PipelineStatus.HUMAN_REVIEW_REQUIRED
            ):
                gate.setdefault("paused", True)
                gate.setdefault("resume_phase", "after_data_acquisition")
                if not meta.get("pipeline_checkpoint"):
                    meta["pipeline_checkpoint"] = self._rebuild_checkpoint_from_stages()
                meta["data_upload_gate"] = gate
                self._persist_extra_metadata(meta)
                self.db.commit()
            elif (
                status_val == DB_PipelineStatus.COMPLETED
                and uploaded >= 1
            ):
                # 报告已生成但用户事后上传了外部数据：从数据采集后继续重跑下游
                if not meta.get("pipeline_checkpoint"):
                    meta["pipeline_checkpoint"] = self._rebuild_checkpoint_from_stages()
                gate.setdefault("paused", True)
                gate.setdefault("resume_phase", "after_data_acquisition")
                if meta.get("rerun_from_stage"):
                    meta["prior_rerun_from_stage"] = meta.get("rerun_from_stage")
                    meta.pop("rerun_from_stage", None)
                    meta.pop("rerun_mode", None)
                meta["data_upload_gate"] = gate
                self._persist_extra_metadata(meta)
                self.db.commit()
            else:
                raise ValueError("Pipeline 未处于数据上传等待状态")

        pending = self._pending_manual_upload_count(project_id)
        uploaded = self._uploaded_manual_count(project_id)
        from app.services.dataset_service import DatasetService

        project_datasets = DatasetService(self.db).get_project_datasets(project_id)
        if not force:
            if uploaded < 1 and not project_datasets:
                raise ValueError("请至少上传一个数据集后再继续生成报告")

        checkpoint = dict(meta.get("pipeline_checkpoint") or {})
        results = dict(checkpoint.get("results") or {})

        from app.services.data_finder_service import get_data_finder_service

        df_svc = get_data_finder_service(self.db)
        try:
            if df_svc.load_results(project_id):
                df_svc.run_align_schema_sync(project_id)
                df_svc.run_merge_sync(project_id)
        except Exception as align_err:
            logger.warning("[QuickReport] align/merge 续跑失败: %s", align_err)

        results = self._refresh_data_acquisition_results(project_id, results)

        gate["paused"] = False
        gate["resumed"] = True
        gate["continued_at"] = datetime.now(CHINA_TZ).isoformat()
        gate["uploaded_count"] = uploaded
        if force and pending > 0:
            gate["skipped_pending"] = pending
        meta["data_upload_gate"] = gate
        meta["pipeline_checkpoint"] = {
            "results": self._checkpoint_safe_results(results),
            "resume_phase": "after_data_acquisition",
        }
        self.db_pipeline_run.status = DB_PipelineStatus.RUNNING
        self._persist_extra_metadata(meta)
        self.db.commit()

        return {
            "action": "continue",
            "status": "running",
            "run_id": run_id,
            "project_id": project_id,
        }

    def _maybe_pause_for_data_upload(self, project_id: str, results: Dict[str, Any]) -> None:
        if not self._run_options.get("enable_quick_report"):
            return
        pending = self._pending_manual_upload_count(project_id)
        from app.services.dataset_service import DatasetService

        has_project_data = bool(DatasetService(self.db).get_project_datasets(project_id))
        # 无相关外部数据集待下载时，不阻断理论/综述类报告流程
        if pending <= 0:
            return

        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        gate = dict(meta.get("data_upload_gate") or {})
        gate.update({
            "paused": True,
            "pending_count": pending,
            "paused_at": datetime.now(CHINA_TZ).isoformat(),
            "resume_phase": "after_data_acquisition",
            "require_user_upload": pending <= 0,
        })
        checkpoint = {
            "results": self._checkpoint_safe_results(results),
            "resume_phase": "after_data_acquisition",
        }
        self._persist_extra_metadata({
            "data_upload_gate": gate,
            "pipeline_checkpoint": checkpoint,
            "quick_report": True,
        })
        self.db_pipeline_run.status = DB_PipelineStatus.HUMAN_REVIEW_REQUIRED
        self.db_pipeline_run.current_stage = "data_acquisition"
        self.db.commit()
        summary = (
            f"一键报告：{pending} 个外部数据集需下载后上传"
            if pending > 0
            else "一键报告：请上传研究数据后继续生成报告"
        )
        self._record_closed_loop_event(
            "data_upload_pause",
            {"pending_count": pending, "summary": summary},
        )
        raise DataUploadPause(pending)

    def _should_hitl_gate(self, stage_key: str) -> bool:
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
            if parent_exec.output_data:
                results[key] = parent_exec.output_data
                stages[idx].status = PipelineStageStatus.COMPLETED
                stages[idx].output_data = parent_exec.output_data
        self.db.commit()
        logger.info(
            f"[Pipeline] 单阶段重跑完成，已从父 run 恢复下游阶段 parent={parent_run_id}"
        )
    
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

            slimmed_output = slim_stage_output(
                output if isinstance(output, dict) else self._safe_model_dump(output),
                stage_key=stage_key,
            )
            stage_log.status = PipelineStageStatus.COMPLETED
            stage_log.output_data = slimmed_output
            results[stage_key] = slimmed_output
            self._stage_results[stage_key] = slimmed_output

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

            if getattr(self, "_rerun_single_stage_only", False) and idx == getattr(self, "_start_idx", 0):
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
            base["experiment_design"] = results.get("experiment_design", {})
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
        from app.services.literature_bundle_service import enrich_literature_mining

        return enrich_literature_mining(literature_mining)

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

    def _exec_literature_mining(self, project_id: str, research_question: str):
        agent = get_literature_mining_agent()
        result = agent.mine(project_id=project_id, research_question=research_question, db=self.db)
        return self._safe_model_dump(result)

    def _exec_literature_mining_stage(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """文献挖掘 + 多模态 evidence 合并，并在无文献时终止工作流。"""
        dump = self._exec_literature_mining(project_id, research_question)
        results["literature_mining"] = dump
        try:
            self._exec_multimodal_sync(project_id, research_question, results)
        except Exception as mm_err:
            logger.warning(f"多模态 evidence 同步失败: {mm_err}")
        lm = self._enrich_literature_mining(results.get("literature_mining") or {})
        results["literature_mining"] = lm
        allow_empty = bool(self._run_options.get("enable_quick_report"))
        self._validate_literature_results(lm, allow_empty=allow_empty)
        return lm

    @staticmethod
    def _validate_literature_results(
        literature_mining: Dict[str, Any],
        *,
        allow_empty: bool = False,
    ) -> None:
        """未检索到可用文献时抛出 LiteratureNotFoundError（一键报告 allow_empty 时仅警告）。"""
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

    def _exec_data_acquisition(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
        project_mode: str,
        refinement_queries: Optional[List[str]] = None,
        selected_hypothesis: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.services.data_finder_service import get_data_finder_service

        hg = results.get("hypothesis_generation", {})
        hypotheses = hg.get("hypotheses", []) if hg else []
        if not selected_hypothesis and hypotheses:
            tree = hg.get("hypothesis_tree") or {}
            sel_idx = tree.get("selected_hypothesis_index", 0)
            if 0 <= sel_idx < len(hypotheses):
                selected_hypothesis = hypotheses[sel_idx].get("hypothesis", "")
            else:
                selected_hypothesis = hypotheses[0].get("hypothesis", "")
        if not selected_hypothesis:
            ideation = results.get("ideation_novelty") or {}
            angles = ideation.get("suggested_angles") or []
            if angles:
                selected_hypothesis = str(angles[0])[:200]

        service = get_data_finder_service(self.db)
        search_query = research_question
        if refinement_queries:
            search_query = f"{research_question} {' '.join(refinement_queries[:4])}"[:500]

        gap_options = {
            "enable_gap_search": (
                False
                if self._run_options.get("enable_quick_report")
                else self._run_options.get("enable_gap_search", True)
            ),
            "auto_import": (
                False
                if self._run_options.get("enable_quick_report")
                else self._run_options.get("enable_hf_auto_import", True)
            ),
            "coverage_gap_threshold": self._run_options.get("coverage_gap_threshold"),
            "data_spec_gap_threshold": self._run_options.get("data_spec_gap_threshold"),
            "max_gap_rounds": self._run_options.get("max_gap_rounds"),
            "refinement_queries": refinement_queries,
            "quick_report_fast": bool(self._run_options.get("enable_quick_report")),
        }
        auto_import = (
            False
            if self._run_options.get("enable_quick_report")
            else self._run_options.get("enable_hf_auto_import", True)
        )
        final = service.run_data_acquisition_sync(
            project_id=project_id,
            research_question=search_query,
            selected_hypothesis=selected_hypothesis or "",
            project_mode=project_mode,
            auto_import=auto_import,
            gap_options=gap_options,
        )

        gap_meta = final.get("gap_enrichment") or {}
        da = final.get("data_acquisition") or {}
        gap_loop = da.get("step_details", {}).get("gap_loop") if isinstance(da.get("step_details"), dict) else None
        if gap_loop:
            gap_meta = {"loop": gap_loop, "rounds": len(gap_loop) if isinstance(gap_loop, list) else 0}
            gap_payload = build_data_gap_loop_payload(gap_loop, gap_meta)
            self._record_closed_loop_event("data_gap_loop", gap_payload)
            if gap_meta.get("rounds", 0) > 0:
                self._record_closed_loop_decision(
                    trigger="data_gap_loop",
                    action="gap_enrichment",
                    reason=gap_payload.get("summary", "Gap 补搜完成"),
                    next_stage="knowledge_gap",
                    metadata={"rounds": gap_meta.get("rounds")},
                )

        from app.services.data_finder_slim import slim_data_acquisition_output, slim_data_finder_payload

        slim_final = slim_data_finder_payload(final)
        output = {
            "data_acquisition": final.get("data_acquisition", {}),
            "search": slim_final,
            "extract": slim_final,
            "paper_link_extractions": final.get("paper_extractions", [])[:20],
            "refinement_queries": refinement_queries or [],
            "gap_enrichment": gap_meta,
        }
        slim_output = slim_data_acquisition_output(output)
        results["data_acquisition"] = slim_output
        results["data_finder"] = slim_output
        logger.info(
            f"[DataAcquisition] 完成: tables={len(final.get('extracted_tables', []))} "
            f"merged={(final.get('merged') or {}).get('row_count')}"
        )
        return slim_output

    def _exec_data_finder(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
        project_mode: str,
        refinement_queries: Optional[List[str]] = None,
        selected_hypothesis: Optional[str] = None,
    ) -> Dict[str, Any]:
        """兼容别名 → 多源数据采集。"""
        return self._exec_data_acquisition(
            project_id, research_question, results, project_mode,
            refinement_queries=refinement_queries,
            selected_hypothesis=selected_hypothesis,
        )

    def _exec_knowledge_gap(
        self,
        literature_mining: Optional[Dict],
        project_id: str = "",
    ) -> dict:
        agent = get_knowledge_gap_agent()
        lm = self._enrich_literature_mining(literature_mining)
        facts = lm.get("facts", [])
        uncertain_points = lm.get("uncertain_points", [])
        result = agent.analyze(facts=facts, uncertain_points=uncertain_points)
        return self._safe_model_dump(result)
    
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
        research_question = pu.get("research_question", "")
        num_ideas = int(self._run_options.get("num_ideas", 3))
        extra_constraints = list(self._discovery_refinement or []) + list(
            self._validation_feedback_constraints or []
        ) + list(self._human_feedback_constraints or [])

        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        data_context = self._build_data_context(project_id)

        literature_facts = list(lm.get("facts") or [])
        multimodal_facts = list(data_context.get("multimodal_evidence") or [])
        merged_facts = literature_facts + multimodal_facts

        result = agent.generate(
            research_question=research_question,
            facts=merged_facts,
            knowledge_gaps=kg.get("knowledge_gaps", []),
            constraints=[],
            project_id=project_id,
            data_context=data_context,
            project_mode=self._get_project_mode(project_id),
            num_ideas=num_ideas,
            ideation_context=ideation_novelty,
            extra_constraints=extra_constraints,
            multimodal_evidence=multimodal_facts,
        )
        result_dict = self._safe_model_dump(result)
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
        hg = hypothesis_generation or {}
        hypotheses = hg.get("hypotheses", [])
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

        return result_dict
    
    def _apply_hypothesis_review_scores(
        self,
        project_id: str,
        hypothesis_generation: Dict[str, Any],
        review_result: Dict[str, Any],
    ) -> None:
        """将集成评审结果回写至 DB 假设记录。"""
        from app.services.hypothesis_service import HypothesisService

        hypo_svc = HypothesisService(self.db)
        db_hypos = hypo_svc.get_hypotheses_by_project(project_id, limit=50)
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
            db_hypo = None
            if i < len(db_hypos):
                db_hypo = db_hypos[i]
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
            hypo_svc.update_hypothesis(db_hypo.id, {"confidence": confidence, "status": status})

        if 0 <= primary_idx < len(db_hypos):
            hypo_svc.set_primary_hypothesis(project_id, db_hypos[primary_idx].id)
    
    def _exec_experiment_design(
        self,
        hypothesis_review: Optional[Dict],
        project_id: str = "",
        project_mode: str = "general",
    ):
        agent = get_experiment_design_agent()
        hr = hypothesis_review or {}
        reviews = hr.get("reviews", [])
        if not reviews:
            return {}

        primary_idx = hr.get("primary_index")
        if primary_idx is None:
            ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
            primary_idx = ensemble.get("target_hypothesis_index", 0)
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0
        primary_idx = min(max(0, primary_idx), len(reviews) - 1)
        best_review = reviews[primary_idx]
        data_context = self._build_data_context(project_id) if project_id else {}
        data_files: List[str] = []
        for ds in data_context.get("datasets") or []:
            if isinstance(ds, dict) and ds.get("file_path"):
                data_files.append(str(ds["file_path"]))
        merged_csv = data_context.get("data_finder_merged_csv")
        if merged_csv and merged_csv not in data_files:
            data_files.insert(0, str(merged_csv))
        lit_mining = self._stage_results.get("literature_mining", {})

        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            from app.services.federated_experiment_service import get_federated_experiment_service
            import asyncio

            fl_context = data_context.get("fl_context") or {}
            fl_service = get_federated_experiment_service(self.db)
            plan = asyncio.run(
                fl_service.build_experiment_plan(
                    hypothesis=best_review.get("hypothesis", ""),
                    fl_context=fl_context,
                )
            )
            if self._validation_feedback_constraints or self._federated_campaign_count > 0:
                sv = self._stage_results.get("small_validation") or {}
                fp = sv.get("federated_pilot") or {}
                plan = fl_service.apply_campaign_feedback(
                    plan,
                    validation_feedback=self._validation_feedback_constraints,
                    replan_actions=fp.get("replan_actions"),
                    campaign_round=self._federated_campaign_count + 2,
                )
            return fl_service.build_experiment_design_result(
                hypothesis=best_review.get("hypothesis", ""),
                fl_context=fl_context,
                plan=plan,
            )

        result = agent.design_experiment(
            hypothesis=best_review.get("hypothesis", ""),
            rationale=best_review.get("rationale"),
            novelty=str(best_review.get("novelty", "")),
            testability=str(best_review.get("testability", "")),
            required_data=best_review.get("required_data"),
            possible_method=best_review.get("possible_method"),
            risk=str(best_review.get("risk", "")),
            data_files=data_files,
            literature_facts=lit_mining.get("facts", []),
            project_mode=project_mode,
            validation_feedback=list(self._validation_feedback_constraints or [])
            + list(self._human_feedback_constraints or []),
            pilot_results=self._last_pilot_results or None,
        )
        result_dict = result if isinstance(result, dict) else self._safe_model_dump(result)
        project_datasets = data_context.get("datasets") or []
        if project_datasets:
            result_dict["project_datasets"] = project_datasets
            if not (result_dict.get("datasets") or "").strip():
                result_dict["datasets"] = "\n".join(
                    f"- {d.get('filename', 'dataset')} "
                    f"({d.get('data_type', 'unknown')}, {d.get('n_rows', '?')} 行 × {d.get('n_columns', '?')} 列)"
                    for d in project_datasets
                    if isinstance(d, dict)
                )
            result_dict["data_gap"] = []
            src_lines = []
            for d in project_datasets:
                if not isinstance(d, dict):
                    continue
                cols = d.get("columns") or []
                col_preview = ", ".join(str(c) for c in cols[:12])
                src_lines.append(
                    f"{d.get('filename', 'dataset')}: {col_preview or '无列信息'}"
                )
            if src_lines and not (result_dict.get("source_data") or "").strip():
                result_dict["source_data"] = "\n".join(src_lines)
        hg = self._stage_results.get("hypothesis_generation") or {}
        hypotheses = hg.get("hypotheses") or []
        hypo_meta = hypotheses[primary_idx] if hypotheses and primary_idx < len(hypotheses) else {}
        from app.core.iterative_science import (
            attach_verifiable_specs_to_hypotheses,
            build_verifiable_hypothesis_spec_for_mode,
        )

        spec = build_verifiable_hypothesis_spec_for_mode(
            best_review.get("hypothesis", ""),
            project_mode=project_mode,
            hypo_meta=hypo_meta if isinstance(hypo_meta, dict) else {},
            experiment_design=result_dict,
        )
        result_dict["verifiable_hypothesis"] = spec
        if hg.get("hypotheses"):
            refreshed = attach_verifiable_specs_to_hypotheses(
                hg,
                project_mode=project_mode,
                experiment_design=result_dict,
            )
            self._stage_results["hypothesis_generation"] = refreshed
        return result_dict
    
    def _exec_small_validation(
        self,
        experiment_design: Optional[Dict],
        hypothesis_review: Optional[Dict] = None,
        project_id: str = "",
        project_mode: str = "general",
    ):
        agent = get_small_validation_agent()
        ed = experiment_design or {}
        hr = hypothesis_review or {}
        reviews = hr.get("reviews", [])
        hypothesis = ed.get("hypothesis") or (
            reviews[0].get("hypothesis", "") if reviews else ""
        )

        multimodal_datasets = []
        ed_skill_outputs = ed.get("skill_outputs", {})
        ingest_output = ed_skill_outputs.get("multimodal_data_ingest", {})
        if isinstance(ingest_output, dict) and ingest_output.get("data"):
            multimodal_datasets = ingest_output["data"].get("datasets", [])

        modeling_results = []
        if project_id:
            from app.services.modeling_service import ModelingService
            from app.services.dataset_service import DatasetService
            from app.services.data_finder_service import get_data_finder_service

            modeling_results = ModelingService(self.db).load_project_modeling_results(project_id)
            if not multimodal_datasets:
                ds_service = DatasetService(self.db)
                for ds in ds_service.get_project_datasets(project_id):
                    if ds.data_type != "tabular":
                        continue
                    multimodal_datasets.append(
                        {
                            "dataset_id": ds.id,
                            "filename": ds.filename,
                            "file_path": ds.file_path,
                            "data_type": ds.data_type,
                            "n_rows": ds.n_rows,
                            "n_columns": ds.n_columns,
                            "columns": json.loads(ds.columns_json) if ds.columns_json else [],
                            "dtypes": json.loads(ds.dtypes_json) if ds.dtypes_json else {},
                            "statistics": json.loads(ds.statistics_json) if ds.statistics_json else {},
                            "preview": json.loads(ds.preview_json) if ds.preview_json else [],
                        }
                    )
                df_results = get_data_finder_service(self.db).load_results(project_id)
                merged_path = (df_results or {}).get("merged", {}).get("cleaned_csv_path") or (
                    (df_results or {}).get("merged", {}).get("merged_csv_path")
                )
                if merged_path and os.path.exists(merged_path):
                    multimodal_datasets.insert(0, {
                        "dataset_id": "data_finder_merged",
                        "filename": os.path.basename(merged_path),
                        "file_path": merged_path,
                        "data_type": "tabular",
                        "source": "data_finder",
                    })

        csv_data_path = None
        for ds in multimodal_datasets:
            fp = ds.get("file_path")
            if fp and os.path.exists(fp) and ds.get("data_type", "tabular") == "tabular":
                csv_data_path = fp
                break

        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            from app.services.federated_experiment_service import get_federated_experiment_service
            import asyncio

            data_context = self._build_data_context(project_id) if project_id else {}
            fl_context = data_context.get("fl_context") or ed.get("fl_context") or {}
            fl_service = get_federated_experiment_service(self.db)
            federated_plan = ed.get("federated_plan") or {}
            pilot = asyncio.run(
                fl_service.run_pilot_validation(
                    datasets=multimodal_datasets,
                    fl_context=fl_context,
                    experiment_plan=federated_plan,
                )
            )
            return {
                "hypothesis": hypothesis,
                "project_mode": project_mode,
                "federated_pilot": pilot,
                "results": {
                    "actual_results": pilot if pilot.get("execution_mode") == "uploaded_csv" else [],
                    "simulated_results": pilot if pilot.get("execution_mode") == "simulation" else [],
                    "expected_results": pilot.get("next_round_suggestions", []),
                    "result_source": pilot.get("result_source", pilot.get("execution_mode")),
                    "gate_blocked": pilot.get("execution_mode") == "gate_blocked",
                },
                "skill_outputs": pilot.get("skill_outputs", {}),
                "analysis_summary": pilot.get("analysis", {}).get("summary", ""),
                "replan_actions": pilot.get("replan_actions", []),
                "verifiable_checks": [
                    a.get("expected_check") for a in (pilot.get("replan_actions") or []) if a.get("expected_check")
                ],
            }

        result = agent.generate_validation(
            hypothesis=hypothesis,
            methods=ed.get("methods", ""),
            datasets=ed.get("datasets", ""),
            metrics=ed.get("metrics", ""),
            csv_data_path=csv_data_path,
            experiment_design=ed,
            multimodal_datasets=multimodal_datasets,
            modeling_results=modeling_results,
            project_mode=project_mode,
            run_id=self.run_id,
            project_id=project_id,
            sandbox_use_docker=bool(self._run_options.get("sandbox_use_docker")),
        )
        if isinstance(result, dict) and result.get("sandbox_execution"):
            self._record_closed_loop_event(
                "sandbox_validation",
                {
                    "round": 3,
                    "success": result["sandbox_execution"].get("success"),
                    "metrics": result["sandbox_execution"].get("metrics"),
                    "experiment_id": result["sandbox_execution"].get("experiment_id"),
                    "quality_trend_entry": {
                        "stage": "sandbox",
                        "score": 8.0 if result["sandbox_execution"].get("success") else 3.0,
                    },
                },
            )

        if self._run_options.get("force_sandbox"):
            sb = (result or {}).get("sandbox_execution") or {}
            if not sb.get("success"):
                result["human_review_required"] = True
                result.setdefault("warnings", []).append(
                    "Discovery 模式要求沙箱实测成功；当前执行未通过，需人工介入或补充数据。"
                )

        if isinstance(result, dict):
            data_rows = []
            for ds in multimodal_datasets:
                data_rows.extend((ds.get("preview") or ds.get("sample_data") or [])[:100])
            result = self._apply_plot_quality_loop(
                result,
                hypothesis=hypothesis,
                data_rows=data_rows or None,
            )

        return result if isinstance(result, dict) else self._safe_model_dump(result)

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
        ed = results.get("experiment_design", {})
        sv = results.get("small_validation", {})

        evidence_facts, citation_map, verified_references = self._normalize_literature_bundle(lm)
        
        project_info = {
            "title": "研究项目",
            "id": self.run_id,
            "project_mode": project_mode,
        }

        multimodal_datasets = []
        ed_skill_outputs = ed.get("skill_outputs", {})
        ingest_output = ed_skill_outputs.get("multimodal_data_ingest", {})
        if isinstance(ingest_output, dict) and ingest_output.get("data"):
            multimodal_datasets = ingest_output["data"].get("datasets", [])

        preliminary_analysis_outputs = sv.get("skill_outputs", {})

        data_context = {}
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        if project_id:
            data_context = self._build_data_context(project_id)
        data_context = self._merge_data_acquisition_context(data_context, results)
        hg_input = hg.get("input_data") or hg
        if isinstance(hg_input, dict) and hg_input.get("data_context"):
            data_context = {**data_context, **hg_input.get("data_context", {})}

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
            sanity_check_skill_outputs=ed.get("skill_outputs"),
            evidence_facts=evidence_facts,
            verified_references=verified_references,
            preliminary_analysis_skill_outputs=preliminary_analysis_outputs,
            multimodal_datasets=multimodal_datasets,
            data_context=data_context,
            project_mode=project_mode,
        )
        result_dict = self._safe_model_dump(result)

        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            from app.services.federated_experiment_service import get_federated_experiment_service

            fl_service = get_federated_experiment_service(self.db)
            chapters = result_dict.get("chapters", {})
            if isinstance(chapters, dict):
                result_dict["chapters"] = fl_service.enrich_report_sections(
                    chapters,
                    data_context.get("fl_context") or ed.get("fl_context") or {},
                    ed,
                    sv.get("federated_pilot") or {},
                    iteration_snapshots=self._iteration_snapshots,
                )
                result_dict["report_mode"] = ProjectMode.FEDERATED_LEARNING.value

        hypothesis = ed.get("hypothesis") or ""
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
            self._mark_stage_human_review(7, "图表 VLM 评审未达标，需人工复核")

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
            max_rounds=2,
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
        hg = results.get("hypothesis_generation", {})
        lm = results.get("literature_mining", {})
        if not hg or not hg.get("hypotheses"):
            return

        alignment_data = hg.get("alignment", {})
        alignments = alignment_data.get("alignments", []) if alignment_data else []

        # 为每条假设附上对齐结果
        hypotheses_with_alignment = []
        for i, h in enumerate(hg["hypotheses"]):
            h = dict(h)
            if i < len(alignments):
                a = alignments[i]
                h["alignment_score"] = a.get("alignment_score")
                h["off_topic"] = a.get("off_topic")
                h["off_topic_reason"] = a.get("off_topic_reason")
                h["matched_keywords"] = a.get("matched_keywords")
                h["missing_keywords"] = a.get("missing_keywords")
            hypotheses_with_alignment.append(h)

        hypo_service = HypothesisService(self.db)
        created_hypos = hypo_service.create_hypotheses_batch(
            project_id=project_id,
            research_question=research_question,
            hypotheses_list=hypotheses_with_alignment
        )

        from app.services.evidence_reasoning_service import get_evidence_reasoning_service
        er_service = get_evidence_reasoning_service()

        # ── 为每条假设创建证据链：优先 evidence_chain，其次 supporting_fact_ids ──
        all_facts = lm.get("facts", [])
        for idx, db_hypo in enumerate(created_hypos):
            hypo_data = hypotheses_with_alignment[idx] if idx < len(hypotheses_with_alignment) else {}
            chain = hypo_data.get("evidence_chain")
            if chain:
                er_service.save_evidence_chain(project_id, db_hypo.id, chain)
                final_text = chain.get("final_version") or hypo_data.get("hypothesis")
                if final_text and final_text != db_hypo.hypothesis:
                    hypo_service.update_hypothesis(db_hypo.id, {"hypothesis": final_text, "rationale": db_hypo.rationale})

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
                    hypo_service.create_evidence_batch(
                        project_id=project_id,
                        hypothesis_id=db_hypo.id,
                        facts=facts_for_db,
                    )
                continue

            raw_ids = db_hypo.supporting_fact_ids
            try:
                target_ids = json.loads(raw_ids) if raw_ids else []
            except (json.JSONDecodeError, TypeError):
                target_ids = []
            if not isinstance(target_ids, list):
                target_ids = []

            if target_ids:
                # 只保留与 supporting_fact_ids 匹配的事实
                matched_facts = [f for f in all_facts if f.get("fact_id") in target_ids]
            else:
                # 没有 supporting_fact_ids: 不创建证据链
                matched_facts = []

            if matched_facts:
                hypo_service.create_evidence_batch(
                    project_id=project_id,
                    hypothesis_id=db_hypo.id,
                    facts=matched_facts,
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
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        meta["auxiliary_results"] = {
            k: safe_results[k]
            for k in (
                "data_finder", "evidence_reasoning",
                "ideation_novelty", "discovery_loop", "teaching_auto_refinement",
                "federated_campaign_refinement",
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

    def _create_report(self, project_id: str, report_data: Dict[str, Any]) -> Optional[str]:
        """创建报告记录"""
        if not report_data:
            return None
        report_id = str(uuid.uuid4())
        title = report_data.get("paper_title", report_data.get("title", "研究报告"))
        chapters = report_data.get("chapters", {})

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
            pdf_path=report_data.get("report_id"),
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

        return slim_data_context(data_context)

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


def try_resume_after_dataset_upload(db: Session, project_id: str) -> Optional[Dict[str, Any]]:
    """用户上传数据集后，若 Pipeline 处于数据上传等待态则自动续跑。"""
    import threading

    from app.core.database import SessionLocal
    from app.models.pipeline import PipelineRun

    run = (
        db.query(PipelineRun)
        .filter(PipelineRun.project_id == project_id)
        .order_by(PipelineRun.created_at.desc())
        .first()
    )
    if not run:
        return None

    meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
    gate = meta.get("data_upload_gate") or {}
    status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
    is_quick = bool(meta.get("quick_report"))
    input_opts = (run.input_data or {}).get("options") if isinstance(run.input_data, dict) else {}
    if isinstance(input_opts, dict) and input_opts.get("enable_quick_report"):
        is_quick = True

    awaiting = bool(gate.get("paused")) or (
        status_val.lower() == "human_review_required" and (is_quick or bool(gate))
    )
    if not awaiting:
        return None

    from app.services.dataset_service import DatasetService

    if not DatasetService(db).get_project_datasets(project_id):
        return None

    svc = get_pipeline_service(db)
    try:
        result = svc.resume_after_data_upload(run.run_id)
    except ValueError:
        return None

    run_id = run.run_id

    def _bg() -> None:
        bg_db = SessionLocal()
        try:
            get_pipeline_service(bg_db).execute_pipeline_run(run_id)
        except Exception as exc:
            logger.exception("[Pipeline] 数据集上传后续跑失败 run_id=%s: %s", run_id, exc)
        finally:
            bg_db.close()

    threading.Thread(target=_bg, daemon=True).start()
    return result


def _find_failed_stage(stages: List[PipelineStageLog]) -> Optional[PipelineStageLog]:
    """找到第一个失败的阶段"""
    for stage in stages:
        if stage.status == PipelineStageStatus.FAILED:
            return stage
    return None


def get_pipeline_service(db: Session) -> PipelineService:
    """获取 PipelineService 实例"""
    return PipelineService(db)