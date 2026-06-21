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
from app.services.hypothesis_service import HypothesisService
from app.services.qwen_client import get_call_logs, clear_call_logs, CallLog

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

        self._run_pipeline_stages(research_question, project_id)

    def run_pipeline(self, request: PipelineRunRequest) -> PipelineRunResult:
        self.start_pipeline_async(request)
        return self._run_pipeline_stages(request.research_question, request.project_id)

    def _get_project_mode(self, project_id: str) -> str:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project:
            return normalize_project_mode(getattr(project, "project_mode", None))
        return ProjectMode.GENERAL.value

    def _run_pipeline_stages(self, research_question: str, project_id: str) -> PipelineRunResult:
        """执行 Pipeline 所有阶段。"""
        project_mode = self._get_project_mode(project_id)
        logger.info(
            f"[Pipeline] ====== 开始执行全部 8 个阶段 run_id={self.run_id} "
            f"project_id={project_id} mode={project_mode} ======"
        )

        # 初始化阶段日志
        stages: List[PipelineStageLog] = [
            PipelineStageLog(stage=d["stage_enum"], status=PipelineStageStatus.PENDING)
            for d in STAGE_DEFS
        ]
        
        # 存储各阶段结果
        results: Dict[str, Any] = {}
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
            self._run_stage(stages, 0, results, research_question, project_id,
                lambda: self._exec_problem_understanding(research_question))
            
            # ── 阶段 2: LiteratureMiningAgent ──
            self._run_stage(stages, 1, results, research_question, project_id,
                lambda: self._exec_literature_mining(project_id, research_question))

            # ── 阶段 2.5: 多源数据查找与整合 ──
            try:
                self._exec_data_finder(project_id, research_question, results, project_mode)
            except Exception as df_err:
                logger.warning(f"多源数据查找失败: {df_err}")

            # ── 阶段 2.6: 知识图谱初始构建 ──
            try:
                self._exec_knowledge_graph(
                    project_id, research_question, results, project_mode, stage="initial"
                )
            except Exception as kg_err:
                logger.warning(f"知识图谱初始构建失败: {kg_err}")
            
            # ── 阶段 3: KnowledgeGapAgent ──
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
            self._run_stage(stages, 3, results, research_question, project_id,
                lambda: self._exec_hypothesis_generation(
                    results.get("problem_understanding"),
                    results.get("literature_mining"),
                    results.get("knowledge_gap")
                ))

            # ── 阶段 4.5: 科学机制推理与证据链迭代验证 ──
            try:
                self._exec_evidence_reasoning(project_id, research_question, results)
            except Exception as er_err:
                logger.warning(f"证据链迭代验证失败: {er_err}")

            try:
                self._exec_knowledge_graph(
                    project_id, research_question, results, project_mode, stage="post_evidence"
                )
            except Exception as kg_err:
                logger.warning(f"知识图谱证据链更新失败: {kg_err}")

            # 保存假设到数据库
            try:
                self._save_hypotheses(project_id, research_question, results)
            except Exception as save_err:
                logger.warning(f"保存假设/证据链失败: {save_err}")
            
            # ── 阶段 5: HypothesisReviewAgent ──
            self._run_stage(stages, 4, results, research_question, project_id,
                lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
            
            # ── 阶段 6: ExperimentDesignAgent ──
            self._run_stage(stages, 5, results, research_question, project_id,
                lambda: self._exec_experiment_design(
                    results.get("hypothesis_review"),
                    project_id,
                    project_mode,
                ))
            
            # ── 阶段 7: SmallValidationAgent ──
            self._run_stage(stages, 6, results, research_question, project_id,
                lambda: self._exec_small_validation(
                    results.get("experiment_design"),
                    results.get("hypothesis_review"),
                    project_id,
                    project_mode,
                ))
            
            # ── 阶段 8: ReportGenerationAgent ──
            def _exec_report():
                pipeline_run_info = self._build_pipeline_run_info()
                return self._exec_report_generation(
                    results, pipeline_run_info, project_mode
                )
            self._run_stage(stages, 7, results, research_question, project_id, _exec_report)
            
            # 创建报告记录
            final_report_id = self._create_report(project_id, results.get("report_generation", {}))
            
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
    
    def _exec_hypothesis_generation(self, problem_understanding: Optional[Dict], literature_mining: Optional[Dict], knowledge_gap: Optional[Dict]) -> dict:
        agent = get_hypothesis_generation_agent()
        pu = problem_understanding or {}
        lm = literature_mining or {}
        kg = knowledge_gap or {}
        research_question = pu.get("research_question", "")

        # ── 构建数据上下文 ──
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
                novelty=h.get("novelty", 0),
                testability=h.get("testability", 0),
                required_data=h.get("required_data", ""),
                possible_method=h.get("possible_method", ""),
                risk=h.get("risk", 0)
            )
            for h in hypotheses
        ]
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
        )
        result_dict = self._safe_model_dump(result)
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
        return result_dict
    
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

        best_review = reviews[0]
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
        )
        return result if isinstance(result, dict) else self._safe_model_dump(result)
    
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
        self.db_pipeline_run = DB_PipelineRun(
            id=str(uuid.uuid4()),
            run_id=self.run_id,
            project_id=request.project_id,
            research_question=request.research_question,
            status=DB_PipelineStatus.RUNNING,
            started_at=datetime.now(CHINA_TZ),
            input_data=request.model_dump(),
            version=1
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