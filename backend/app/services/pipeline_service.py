"""
Pipeline 服务 - 负责按顺序执行各个 Agent
"""
import uuid
import json
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

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
)
from app.services.hypothesis_service import HypothesisService
from app.services.qwen_client import get_call_logs, clear_call_logs, CallLog
from app.services.prompt_context import set_project_id as set_prompt_project_id
from app.services.stage_human_loop_service import STAGE_KEY_ORDER, StageHumanLoopService
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
    {"idx": 5, "key": "experiment_design", "stage_enum": PipelineStage.EXPERIMENT_DESIGN,
     "db_stage_enum": DB_PipelineStage.EXPERIMENT_DESIGN, "label": "实验设计"},
    {"idx": 6, "key": "small_validation", "stage_enum": PipelineStage.SMALL_VALIDATION,
     "db_stage_enum": DB_PipelineStage.SMALL_VALIDATION, "label": "小样验证"},
    {"idx": 7, "key": "report_generation", "stage_enum": PipelineStage.REPORT_GENERATION,
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
    ) -> str:
        """从指定阶段重新运行，保留之前阶段结果（可优先使用人工修改输出）。"""
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
        if meta.get("rerun_from_stage"):
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
        return self._safe_model_dump(response)

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
            stages, 2, results, research_question, project_id,
            lambda: self._exec_knowledge_gap(lm, project_id),
        )

        try:
            self._exec_knowledge_graph(
                project_id, research_question, results, project_mode, stage="post_gap",
            )
        except Exception as kg_err:
            logger.warning(f"Discovery R{round_num} 知识图谱更新失败: {kg_err}")

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

        for round_num in range(2, max_rounds + 1):
            hr = results.get("hypothesis_review") or {}
            ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
            decision = ensemble.get("decision") or hr.get("ensemble_decision")
            overall = ensemble.get("overall") or hr.get("ensemble_overall")
            if decision == "Accept" or (overall is not None and float(overall) >= ENSEMBLE_ACCEPT_SCORE):
                history.append({"round": round_num - 1, "status": "accepted", "overall": overall})
                break

            weaknesses = list(ensemble.get("weaknesses") or [])[:4]
            suggestions = list(ensemble.get("revision_suggestions") or [])[:4]
            self._discovery_refinement = weaknesses + suggestions
            history.append({
                "round": round_num,
                "status": "refining",
                "decision": decision,
                "overall": overall,
                "refinement_notes": self._discovery_refinement,
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

            self._run_stage(stages, 3, results, research_question, project_id,
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

            self._run_stage(stages, 4, results, research_question, project_id,
                lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
            self._run_stage(stages, 5, results, research_question, project_id,
                lambda: self._exec_experiment_design(
                    results.get("hypothesis_review"), project_id, project_mode,
                ))
            self._run_stage(stages, 6, results, research_question, project_id,
                lambda: self._exec_small_validation(
                    results.get("experiment_design"),
                    results.get("hypothesis_review"),
                    project_id,
                    project_mode,
                ))

            def _exec_report():
                return self._exec_report_generation(
                    results, self._build_pipeline_run_info(), project_mode,
                )

            self._run_stage(stages, 7, results, research_question, project_id, _exec_report)
            final_report_id = self._create_report(project_id, results.get("report_generation", {}))

        return {
            "pipeline_mode": PipelineMode.DISCOVERY.value,
            "max_rounds": max_rounds,
            "rounds_executed": len(history) + 1,
            "history": history,
            "final_report_id": final_report_id,
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
                    lambda: self._exec_problem_understanding(research_question))
            
            # ── 阶段 2: LiteratureMiningAgent ──
            if start_idx <= 1:
                self._run_stage(stages, 1, results, research_question, project_id,
                    lambda: self._exec_literature_mining(project_id, research_question))

            if start_idx <= 1:
                try:
                    self._exec_data_finder(project_id, research_question, results, project_mode)
                except Exception as df_err:
                    logger.warning(f"多源数据查找失败: {df_err}")

                try:
                    self._exec_knowledge_graph(
                        project_id, research_question, results, project_mode, stage="initial"
                    )
                except Exception as kg_err:
                    logger.warning(f"知识图谱初始构建失败: {kg_err}")
            
            # ── 阶段 3: KnowledgeGapAgent ──
            if start_idx <= 2:
                self._run_stage(stages, 2, results, research_question, project_id,
                    lambda: self._exec_knowledge_gap(
                        results.get("literature_mining"),
                        project_id,
                    ))

                try:
                    self._exec_knowledge_graph(
                        project_id, research_question, results, project_mode, stage="post_gap"
                    )
                except Exception as kg_err:
                    logger.warning(f"知识图谱增量更新失败: {kg_err}")
            
            # ── 阶段 4: HypothesisGenerationAgent ──
            if start_idx <= 3:
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
                    self._exec_knowledge_graph(
                        project_id, research_question, results, project_mode, stage="post_evidence"
                    )
                except Exception as kg_err:
                    logger.warning(f"知识图谱证据链更新失败: {kg_err}")

                try:
                    self._save_hypotheses(project_id, research_question, results)
                except Exception as save_err:
                    logger.warning(f"保存假设/证据链失败: {save_err}")
            
            # ── 阶段 5: HypothesisReviewAgent ──
            if start_idx <= 4:
                self._run_stage(stages, 4, results, research_question, project_id,
                    lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
            
            # ── 阶段 6: ExperimentDesignAgent ──
            if start_idx <= 5:
                self._run_stage(stages, 5, results, research_question, project_id,
                    lambda: self._exec_experiment_design(
                        results.get("hypothesis_review"),
                        project_id,
                        project_mode,
                    ))
            
            # ── 阶段 7: SmallValidationAgent ──
            if start_idx <= 6:
                self._run_stage(stages, 6, results, research_question, project_id,
                    lambda: self._exec_small_validation(
                        results.get("experiment_design"),
                        results.get("hypothesis_review"),
                        project_id,
                        project_mode,
                    ))
            
            # ── 阶段 8: ReportGenerationAgent ──
            if start_idx <= 7:
                def _exec_report():
                    pipeline_run_info = self._build_pipeline_run_info()
                    return self._exec_report_generation(
                        results, pipeline_run_info, project_mode
                    )
                self._run_stage(stages, 7, results, research_question, project_id, _exec_report)
            
                final_report_id = self._create_report(project_id, results.get("report_generation", {}))

            # ── P5: Discovery 开放循环（Sakana-like）──
            if start_idx <= 3 and self._run_options.get("pipeline_mode") == PipelineMode.DISCOVERY.value:
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
            stage_log.status = PipelineStageStatus.COMPLETED
            stage_log.output_data = output if isinstance(output, dict) else self._safe_model_dump(output)
            results[stage_key] = stage_log.output_data
            self._stage_results[stage_key] = stage_log.output_data

            self._capture_model_params(db_stage)
            self._update_stage_execution(db_stage, "completed", output=stage_log.output_data)
            logger.info(f"[Pipeline] 阶段完成 {idx+1}/8 [{stage_label}] key={stage_key} run_id={self.run_id}")

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
            base["knowledge_graph"] = results.get("knowledge_graph", {})
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
    
    def _exec_problem_understanding(self, research_question: str):
        agent = get_problem_understanding_agent()
        result = agent.analyze(research_question=research_question)
        return self._safe_model_dump(result)
    
    def _exec_literature_mining(self, project_id: str, research_question: str):
        agent = get_literature_mining_agent()
        result = agent.mine(project_id=project_id, research_question=research_question, db=self.db)
        return self._safe_model_dump(result)

    def _exec_data_finder(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
        project_mode: str,
    ) -> Dict[str, Any]:
        from app.services.data_finder_service import get_data_finder_service

        hg = results.get("hypothesis_generation", {})
        hypotheses = hg.get("hypotheses", []) if hg else []
        selected_hypothesis = ""
        if hypotheses:
            selected_hypothesis = hypotheses[0].get("hypothesis", "")

        service = get_data_finder_service(self.db)
        search_result = service.run_search_sync(
            project_id=project_id,
            research_question=research_question,
            selected_hypothesis=selected_hypothesis,
            project_mode=project_mode,
        )
        extract_result = service.run_extract_tables_sync(project_id)
        if extract_result.get("extracted_tables"):
            service.run_align_schema_sync(project_id)
            service.run_merge_sync(project_id)
            extract_result = service.load_results(project_id) or extract_result

        output = {
            "search": search_result,
            "extract": extract_result,
            "paper_link_extractions": search_result.get("paper_extractions", []),
        }
        results["data_finder"] = output
        logger.info(
            f"[DataFinder] 完成 search + extract: tables={len(extract_result.get('extracted_tables', []))}"
        )
        return output

    def _exec_knowledge_graph(
        self,
        project_id: str,
        research_question: str,
        results: Dict[str, Any],
        project_mode: str,
        stage: str = "initial",
    ) -> Dict[str, Any]:
        from app.services.knowledge_graph_service import get_knowledge_graph_service

        lm = results.get("literature_mining", {}) or {}
        kg_gap = results.get("knowledge_gap", {}) or {}
        hg = results.get("hypothesis_generation", {}) or {}
        hypotheses = hg.get("hypotheses", []) if hg else []

        service = get_knowledge_graph_service(self.db)
        graph = service.build_graph_sync(
            project_id=project_id,
            literature_mining=lm,
            knowledge_gap=kg_gap if stage != "initial" else None,
            hypotheses=hypotheses if stage == "post_evidence" else None,
            project_mode=project_mode,
            research_question=research_question,
        )
        output = {
            "stage": stage,
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "quality_report": graph.get("quality_report", {}),
            "schema": graph.get("schema", {}),
            "evidence_graph": graph.get("evidence_graph", {}),
        }
        results["knowledge_graph"] = {**output, "graph": graph}
        logger.info(
            f"[KnowledgeGraph] {stage} 完成: nodes={output['node_count']} edges={output['edge_count']}"
        )
        return output
    
    def _exec_knowledge_gap(
        self,
        literature_mining: Optional[Dict],
        project_id: str = "",
    ) -> dict:
        agent = get_knowledge_gap_agent()
        lm = literature_mining or {}
        facts = lm.get("facts", [])
        uncertain_points = lm.get("uncertain_points", [])
        result = agent.analyze(facts=facts, uncertain_points=uncertain_points)
        result_dict = self._safe_model_dump(result)

        if project_id:
            try:
                from app.services.knowledge_graph_service import get_knowledge_graph_service

                kg_ctx = get_knowledge_graph_service(self.db).get_kg_context_for_agents(project_id)
                if kg_ctx:
                    qr = kg_ctx.get("quality_report", {})
                    graph_gaps = []
                    for iso in qr.get("isolated_nodes", [])[:5]:
                        graph_gaps.append({
                            "gap_id": f"kg_iso_{iso.get('id', '')[:8]}",
                            "description": f"图谱孤立节点需补充关系: {iso.get('label', '')}",
                            "basis": [iso.get("id", "")],
                            "potential_value": "完善证据链连接",
                            "source": "knowledge_graph",
                        })
                    missing_query = get_knowledge_graph_service(self.db).query_graph_sync(
                        project_id, "当前假设缺少哪些证据？"
                    )
                    for path in missing_query.get("graph_paths", [])[:5]:
                        graph_gaps.append({
                            "gap_id": f"kg_miss_{hash(str(path)) % 10000}",
                            "description": f"缺少证据: {' → '.join(str(p) for p in path)}",
                            "basis": [],
                            "potential_value": "假设验证需补充文献支持",
                            "source": "knowledge_graph",
                        })
                    if graph_gaps:
                        result_dict.setdefault("knowledge_gaps", []).extend(graph_gaps)
                        result_dict["kg_enrichment"] = {
                            "isolated_count": qr.get("isolated_count", 0),
                            "graph_gaps_added": len(graph_gaps),
                        }
            except Exception as kg_err:
                logger.warning(f"KG 知识缺口增强失败: {kg_err}")

        return result_dict
    
    def _exec_hypothesis_generation(
        self,
        problem_understanding: Optional[Dict],
        literature_mining: Optional[Dict],
        knowledge_gap: Optional[Dict],
        ideation_novelty: Optional[Dict] = None,
    ) -> dict:
        agent = get_hypothesis_generation_agent()
        pu = problem_understanding or {}
        lm = literature_mining or {}
        kg = knowledge_gap or {}
        research_question = pu.get("research_question", "")
        num_ideas = int(self._run_options.get("num_ideas", 3))
        extra_constraints = list(self._discovery_refinement or [])

        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        data_context = self._build_data_context(project_id)

        result = agent.generate(
            research_question=research_question,
            facts=lm.get("facts", []),
            knowledge_gaps=kg.get("knowledge_gaps", []),
            constraints=[],
            project_id=project_id,
            data_context=data_context,
            project_mode=self._get_project_mode(project_id),
            num_ideas=num_ideas,
            ideation_context=ideation_novelty,
            extra_constraints=extra_constraints,
        )
        result_dict = self._safe_model_dump(result)

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
                        facts=lm.get("facts", []),
                        knowledge_gaps=kg.get("knowledge_gaps", []),
                        constraints=[
                            alignment["off_topic_summary"]
                        ],
                        project_id=project_id,
                        data_context=data_context,
                        num_ideas=num_ideas,
                        ideation_context=ideation_novelty,
                        extra_constraints=extra_constraints,
                    )
                    result_dict = self._safe_model_dump(retry)
                    # 重试后再做一次对齐检查
                    if result_dict.get("hypotheses"):
                        result_dict["alignment"] = self._run_alignment_skill(
                            research_question, result_dict["hypotheses"]
                        )
            except Exception as align_err:
                logger.warning(f"问题对齐检查失败: {align_err}")

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
        agent = get_hypothesis_review_agent()
        hg = hypothesis_generation or {}
        hypotheses = hg.get("hypotheses", [])
        alignment_data = hg.get("alignment", {})
        alignments = alignment_data.get("alignments", []) if alignment_data else []
        candidates = [
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
        kg_evidence = {}
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        if project_id:
            try:
                from app.services.knowledge_graph_service import get_knowledge_graph_service
                kg_graph = get_knowledge_graph_service(self.db).load_graph(project_id)
                if kg_graph:
                    kg_evidence = kg_graph.get("evidence_graph", {})
            except Exception:
                pass

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
        if kg_evidence:
            result_dict["evidence_graph"] = kg_evidence
            support_edges = [
                e for e in kg_evidence.get("edges", [])
                if e.get("relation") == "supports"
            ]
            result_dict["kg_support_summary"] = {
                "support_edge_count": len(support_edges),
                "evidence_nodes": len(kg_evidence.get("nodes", [])),
            }
        if ensemble:
            result_dict["primary_index"] = ensemble.get("target_hypothesis_index", 0)
            result_dict["ensemble_decision"] = ensemble.get("decision")
            result_dict["ensemble_overall"] = ensemble.get("overall")
        if project_id:
            try:
                self._apply_hypothesis_review_scores(project_id, hg, result_dict)
            except Exception as exc:
                logger.warning(f"回写假设评审分数失败: {exc}")
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
            literature_facts=lit_mining.get("facts", []),
            project_mode=project_mode,
        )
        return result if isinstance(result, dict) else self._safe_model_dump(result)
    
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
                merged_path = (df_results or {}).get("merged", {}).get("merged_csv_path")
                if merged_path and os.path.exists(merged_path):
                    multimodal_datasets.insert(0, {
                        "dataset_id": "data_finder_merged",
                        "filename": os.path.basename(merged_path),
                        "file_path": merged_path,
                        "data_type": "tabular",
                        "source": "data_finder",
                    })

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
                },
                "skill_outputs": pilot.get("skill_outputs", {}),
                "analysis_summary": pilot.get("analysis", {}).get("summary", ""),
            }

        result = agent.generate_validation(
            hypothesis=hypothesis,
            methods=ed.get("methods", ""),
            datasets=ed.get("datasets", ""),
            metrics=ed.get("metrics", ""),
            experiment_design=ed,
            multimodal_datasets=multimodal_datasets,
            modeling_results=modeling_results,
            project_mode=project_mode,
            run_id=self.run_id,
            project_id=project_id,
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
        lm = results.get("literature_mining", {})
        kg = results.get("knowledge_gap", {})
        hg = results.get("hypothesis_generation", {})
        hr = results.get("hypothesis_review", {})
        ed = results.get("experiment_design", {})
        sv = results.get("small_validation", {})

        evidence_facts = lm.get("facts", []) if isinstance(lm.get("facts"), list) else []
        citation_map = lm.get("citation_map", []) if isinstance(lm.get("citation_map"), list) else []
        verified_references = lm.get("verified_references", []) if isinstance(lm.get("verified_references"), list) else citation_map
        
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
                )
                result_dict["report_mode"] = ProjectMode.FEDERATED_LEARNING.value

        kg_graph = results.get("knowledge_graph", {}).get("graph")
        if not kg_graph and project_id:
            try:
                from app.services.knowledge_graph_service import get_knowledge_graph_service
                kg_graph = get_knowledge_graph_service(self.db).load_graph(project_id)
            except Exception:
                kg_graph = None
        if kg_graph:
            result_dict = agent._enrich_report_with_knowledge_graph(result_dict, kg_graph)

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
        lm = results.get("literature_mining", {})
        hypotheses = hg.get("hypotheses", [])
        if not hypotheses:
            return {}

        service = get_evidence_reasoning_service()
        output = service.run_for_hypotheses_sync(
            hypotheses=hypotheses,
            research_question=research_question,
            literature_mining=lm,
            max_rounds=2,
        )
        hg["hypotheses"] = output.get("hypotheses", hypotheses)
        hg["evidence_reasoning"] = output
        results["hypothesis_generation"] = hg
        results["evidence_reasoning"] = output
        logger.info(
            f"[EvidenceReasoning] 完成 {len(output.get('hypotheses', []))} 条假设证据链迭代"
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
        now = datetime.now(CHINA_TZ)
        if status == "completed":
            db_stage.status = DB_PipelineStatus.COMPLETED
            if output is not None:
                db_stage.output_data = output
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
        self.db_pipeline_run.status = DB_PipelineStatus.COMPLETED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = total_duration_ms
        self.db_pipeline_run.output_data = results
        self.db_pipeline_run.current_stage = None
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        meta["auxiliary_results"] = {
            k: results[k]
            for k in (
                "data_finder", "knowledge_graph", "evidence_reasoning",
                "ideation_novelty", "discovery_loop",
            )
            if k in results
        }
        meta["run_options"] = self._run_options
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
        meta = self.db_pipeline_run.extra_metadata if isinstance(self.db_pipeline_run.extra_metadata, dict) else {}
        events = list(meta.get("closed_loop_events") or [])
        from datetime import datetime, timezone, timedelta
        events.append({
            "type": event_type,
            "at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            **payload,
        })
        meta["closed_loop_events"] = events[-20:]
        trend = list(meta.get("quality_trend") or [])
        qt = payload.get("quality_trend_entry") or payload.get("quality_trend")
        if isinstance(qt, dict) and qt.get("stage"):
            trend.append(qt)
        elif isinstance(qt, list):
            trend.extend(qt)
        meta["quality_trend"] = trend[-15:]
        self.db_pipeline_run.extra_metadata = meta
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

        extra_meta = report_data.get("compliance_check") or {}
        if report_data.get("plots"):
            extra_meta["plots"] = report_data["plots"]

        report = Report(
            id=report_id,
            project_id=project_id,
            title=title,
            paper_title=title,
            paper_abstract=_to_text(report_data.get("paper_abstract", "")),
            markdown_content=_to_text(report_data.get("markdown_content", "")),
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