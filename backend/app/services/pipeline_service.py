"""
Pipeline 服务 - 负责按顺序执行各个 Agent
"""
import uuid
import json
import logging
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
from app.models.project import Report
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

    def execute_pipeline_run(self, run_id: str, request: PipelineRunRequest):
        """
        在后台线程中执行完整 Pipeline（供 start_pipeline_async 调用）。

        Args:
            run_id: 已创建的 Pipeline 运行 ID
            request: Pipeline 运行请求
        """
        self.run_id = run_id

        self.db_pipeline_run = self.db.query(DB_PipelineRun).filter(
            DB_PipelineRun.run_id == run_id
        ).first()
        if not self.db_pipeline_run:
            logger.error(f"Pipeline run not found: {run_id}")
            return

        existing_stages = (
            self.db.query(DB_PipelineStageExecution)
            .filter(DB_PipelineStageExecution.pipeline_run_id == self.db_pipeline_run.id)
            .order_by(DB_PipelineStageExecution.stage_order)
            .all()
        )
        for s in existing_stages:
            self.db_stage_executions[s.stage_order] = s

        self._run_pipeline_stages(request)

    def run_pipeline(self, request: PipelineRunRequest) -> PipelineRunResult:
        """
        同步运行完整的 Pipeline（兼容旧调用方式）。

        Args:
            request: Pipeline 运行请求

        Returns:
            PipelineRunResult: Pipeline 运行结果
        """
        self.start_pipeline_async(request)
        return self._run_pipeline_stages(request)

    def _run_pipeline_stages(self, request: PipelineRunRequest) -> PipelineRunResult:
        """
        执行 Pipeline 所有阶段（内部方法，供 start_pipeline_async 和 run_pipeline 共用）。

        Args:
            request: Pipeline 运行请求

        Returns:
            PipelineRunResult: Pipeline 运行结果
        """
        logger.info(f"开始执行 Pipeline 阶段: {self.run_id}, 项目: {request.project_id}")

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
            
            # ── 阶段 1: ProblemUnderstandingAgent ──
            self._run_stage(stages, 0, results, request, lambda: self._exec_problem_understanding(request.research_question))
            
            # ── 阶段 2: LiteratureMiningAgent ──
            self._run_stage(stages, 1, results, request, lambda: self._exec_literature_mining(request.project_id, request.research_question))
            
            # ── 阶段 3: KnowledgeGapAgent ──
            self._run_stage(stages, 2, results, request,
                lambda: self._exec_knowledge_gap(results.get("literature_mining")))
            
            # ── 阶段 4: HypothesisGenerationAgent ──
            self._run_stage(stages, 3, results, request,
                lambda: self._exec_hypothesis_generation(
                    results.get("problem_understanding"),
                    results.get("literature_mining"),
                    results.get("knowledge_gap")
                ))
            
            # 保存假设到数据库
            try:
                self._save_hypotheses(request.project_id, request.research_question, results)
            except Exception as save_err:
                logger.warning(f"保存假设/证据链失败: {save_err}")
            
            # ── 阶段 5: HypothesisReviewAgent ──
            self._run_stage(stages, 4, results, request,
                lambda: self._exec_hypothesis_review(results.get("hypothesis_generation")))
            
            # ── 阶段 6: ExperimentDesignAgent ──
            self._run_stage(stages, 5, results, request,
                lambda: self._exec_experiment_design(results.get("hypothesis_review")))
            
            # ── 阶段 7: SmallValidationAgent ──
            # experiment_design 不含 hypothesis 字段，需要从 hypothesis_review 补充
            self._run_stage(stages, 6, results, request,
                lambda: self._exec_small_validation(
                    results.get("experiment_design"),
                    results.get("hypothesis_review")
                ))
            
            # ── 阶段 8: ReportGenerationAgent ──
            def _exec_report():
                pipeline_run_info = self._build_pipeline_run_info()
                return self._exec_report_generation(
                    results, pipeline_run_info
                )
            self._run_stage(stages, 7, results, request, _exec_report)
            
            # 创建报告记录
            final_report_id = self._create_report(request.project_id, results.get("report_generation", {}))
            
            # Pipeline 完成
            pipeline_end = datetime.now(CHINA_TZ)
            total_duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            
            logger.info(f"Pipeline 执行成功: {self.run_id}, 总耗时: {total_duration_ms}ms")
            
            self._complete_pipeline_run(pipeline_end, total_duration_ms, results, final_report_id)
            
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=request.project_id,
                research_question=request.research_question,
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
                project_id=request.project_id,
                research_question=request.research_question,
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
        request: PipelineRunRequest,
        executor
    ):
        """统一阶段执行器：记录日志、执行、捕获异常"""
        stage_def = STAGE_DEFS[idx]
        stage_log = stages[idx]
        stage_key = stage_def["key"]
        
        stage_log.status = PipelineStageStatus.RUNNING
        stage_log.start_time = datetime.now(CHINA_TZ)
        
        input_data = self._build_stage_input(idx, results, request)
        
        # 清空之前的 call logs 以便捕获本阶段新产生的调用日志
        clear_call_logs()
        
        db_stage = self._create_stage_execution(idx + 1, stage_def["db_stage_enum"], input_data)
        
        output = None
        try:
            output = executor()
            stage_log.status = PipelineStageStatus.COMPLETED
            stage_log.output_data = output if isinstance(output, dict) else self._safe_model_dump(output)
            results[stage_key] = stage_log.output_data
            self._stage_results[stage_key] = stage_log.output_data
            
            # 捕获模型调用参数
            self._capture_model_params(db_stage)
            self._update_stage_execution(db_stage, "completed", output=stage_log.output_data)
            
        except Exception as e:
            stage_log.status = PipelineStageStatus.FAILED
            stage_log.error_message = str(e)
            self._capture_model_params(db_stage)
            self._update_stage_execution(db_stage, "failed", error=str(e))
            logger.error(f"{stage_def['label']}阶段失败: {e}", exc_info=True)
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
    
    def _build_stage_input(self, idx: int, results: Dict[str, Any], request: PipelineRunRequest) -> Dict[str, Any]:
        """构建阶段输入数据"""
        base = {"project_id": request.project_id, "research_question": request.research_question}
        # 根据阶段补充上游输出
        if idx >= 1:
            base["literature_mining"] = results.get("literature_mining", {})
        if idx >= 2:
            base["knowledge_gap"] = results.get("knowledge_gap", {})
        if idx >= 3:
            base["problem_understanding"] = results.get("problem_understanding", {})
            project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else request.project_id
            data_context = self._build_data_context(project_id)
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
        result = agent.mine(project_id=project_id, research_question=research_question)
        return self._safe_model_dump(result)
    
    def _exec_knowledge_gap(self, literature_mining: Optional[Dict]) -> dict:
        agent = get_knowledge_gap_agent()
        lm = literature_mining or {}
        # 从 dict 重建事实和不确定点
        facts = lm.get("facts", [])
        uncertain_points = lm.get("uncertain_points", [])
        result = agent.analyze(facts=facts, uncertain_points=uncertain_points)
        return self._safe_model_dump(result)
    
    def _exec_hypothesis_generation(self, problem_understanding: Optional[Dict], literature_mining: Optional[Dict], knowledge_gap: Optional[Dict]) -> dict:
        agent = get_hypothesis_generation_agent()
        pu = problem_understanding or {}
        lm = literature_mining or {}
        kg = knowledge_gap or {}
        research_question = pu.get("research_question", "")

        # ── 构建数据上下文 ──
        project_id = self.db_pipeline_run.project_id if self.db_pipeline_run else ""
        data_context = self._build_data_context(project_id)
        multimodal_datasets = data_context.pop("_multimodal_datasets", [])
        data_linking_evidence = data_context.pop("_data_linking_evidence", [])

        result = agent.generate(
            research_question=research_question,
            facts=lm.get("facts", []),
            knowledge_gaps=kg.get("knowledge_gaps", []),
            constraints=[],
            project_id=project_id,
            data_context=data_context,
            multimodal_datasets=multimodal_datasets,
            data_linking_evidence=data_linking_evidence,
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
                        multimodal_datasets=multimodal_datasets,
                        data_linking_evidence=data_linking_evidence,
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
        result = agent.review(
            hypotheses=candidates,
            retrieved_papers=self._build_retrieved_papers(lit_mining),
            literature_facts=lit_mining.get("facts", []),
            alignments=alignments,
        )
        return self._safe_model_dump(result)
    
    def _exec_experiment_design(self, hypothesis_review: Optional[Dict]):
        agent = get_experiment_design_agent()
        hr = hypothesis_review or {}
        reviews = hr.get("reviews", [])
        if reviews:
            best_review = reviews[0]
            result = agent.design_experiment(
                hypothesis=best_review.get("hypothesis", ""),
                rationale=best_review.get("rationale"),
                novelty=str(best_review.get("novelty", "")),
                testability=str(best_review.get("testability", "")),
                required_data=best_review.get("required_data"),
                possible_method=best_review.get("possible_method"),
                risk=str(best_review.get("risk", ""))
            )
            return result if isinstance(result, dict) else self._safe_model_dump(result)
        return {}
    
    def _exec_small_validation(self, experiment_design: Optional[Dict], hypothesis_review: Optional[Dict] = None):
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

        result = agent.generate_validation(
            hypothesis=hypothesis,
            methods=ed.get("methods", ""),
            datasets=ed.get("datasets", ""),
            metrics=ed.get("metrics", ""),
            experiment_design=ed,
            multimodal_datasets=multimodal_datasets,
        )
        return result if isinstance(result, dict) else self._safe_model_dump(result)
    
    def _exec_report_generation(self, results: Dict[str, Any], pipeline_run_info: Optional[Dict] = None) -> dict:
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
        
        project_info = {"title": "研究项目", "id": self.run_id}

        multimodal_datasets = []
        ed_skill_outputs = ed.get("skill_outputs", {})
        ingest_output = ed_skill_outputs.get("multimodal_data_ingest", {})
        if isinstance(ingest_output, dict) and ingest_output.get("data"):
            multimodal_datasets = ingest_output["data"].get("datasets", [])

        preliminary_analysis_outputs = sv.get("skill_outputs", {})

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
        )
        return self._safe_model_dump(result)
    
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
        # ── 为每条假设创建证据链：只关联其 supporting_fact_ids 对应的事实 ──
        all_facts = lm.get("facts", [])
        for db_hypo in created_hypos:
            # 从存储的 JSON 反序列化 supporting_fact_ids
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
        """完成 Pipeline 运行"""
        self.db_pipeline_run.status = DB_PipelineStatus.COMPLETED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = total_duration_ms
        self.db_pipeline_run.output_data = results
        if final_report_id:
            self.db_pipeline_run.final_report_id = final_report_id
        self.db.commit()
    
    def _fail_pipeline_run(self, completed_at: datetime, total_duration_ms: int, failed_stage_name: Optional[str], error: str):
        """失败 Pipeline 运行"""
        self.db_pipeline_run.status = DB_PipelineStatus.FAILED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = total_duration_ms
        self.db_pipeline_run.error_message = error
        if failed_stage_name:
            try:
                self.db_pipeline_run.failed_stage = DB_PipelineStage(failed_stage_name)
            except ValueError:
                self.db_pipeline_run.failed_stage = DB_PipelineStage.PROBLEM_UNDERSTANDING
        self.db.commit()
    
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

        extra_meta = report_data.get("compliance_check") or {}
        if report_data.get("plots"):
            extra_meta["plots"] = report_data["plots"]

        report = Report(
            id=report_id,
            project_id=project_id,
            title=title,
            paper_title=title,
            paper_abstract=report_data.get("paper_abstract", ""),
            markdown_content=report_data.get("markdown_content", ""),
            problem_statement=chapters.get("problem_statement", ""),
            rationale=chapters.get("rationale", ""),
            technical_details=chapters.get("technical_details", ""),
            datasets=chapters.get("datasets", ""),
            source=chapters.get("source", ""),
            target=chapters.get("target", ""),
            methods=chapters.get("methods", ""),
            experiments=chapters.get("experiments", ""),
            results=chapters.get("results", ""),
            references=json.dumps(chapters.get("references", []), ensure_ascii=False) if isinstance(chapters.get("references"), list) else chapters.get("references", ""),
            created_at=datetime.now(CHINA_TZ),
            pdf_path=report_data.get("report_id"),
            status="ready",
            extra_metadata=extra_meta,
        )
        self.db.add(report)
        self.db.commit()
        return report_id


# ────────────── 工具函数 ──────────────

    def _build_data_context(self, project_id: str) -> Dict[str, Any]:
        """构建项目数据上下文，供 HypothesisGenerationAgent 使用"""
        context: Dict[str, Any] = {
            "datasets": [],
            "dataset_count": 0,
            "available_modalities": [],
            "field_candidates": [],
            "target_candidates": [],
            "summary": "",
            "warnings": [],
        }
        multimodal_datasets: List[Dict] = []
        data_linking_evidence: List[Dict] = []

        if not project_id:
            context["warnings"].append("未提供 project_id，无法构建数据上下文")
            return context

        try:
            import json
            from app.models.project import Document, DocumentStatus
            from app.models.research import Dataset

            docs = self.db.query(Document).filter(
                Document.project_id == project_id,
                Document.status == DocumentStatus.PROCESSED,
            ).all()

            fields_set: List[str] = []
            modalities_set: set = set()
            doc_summaries: List[str] = []
            target_candidate_fields: List[str] = []

            for doc in docs:
                if doc.title:
                    doc_summaries.append(doc.title[:100])
                if doc.abstract:
                    doc_summaries.append(f"摘要: {doc.abstract[:150]}")
                if doc.keywords:
                    fields_set.extend([k.strip() for k in doc.keywords.split(",") if k.strip()])
                if doc.extra_metadata:
                    metadata = doc.extra_metadata
                    if isinstance(metadata, dict):
                        ds_fields = metadata.get("fields") or metadata.get("columns") or metadata.get("features")
                        if isinstance(ds_fields, list):
                            fields_set.extend([str(f) for f in ds_fields])
                        ds_info = {
                            "name": doc.filename or doc.title or "unknown",
                            "modality": metadata.get("modality", doc.file_type or "tabular"),
                            "fields": ds_fields if isinstance(ds_fields, list) else [],
                        }
                        multimodal_datasets.append(ds_info)
                        modalities_set.add(ds_info["modality"])

            # ── 从 Dataset 表读取用户上传的多模态数据集 ──
            datasets = self.db.query(Dataset).filter(
                Dataset.project_id == project_id,
                Dataset.preprocessing_status.in_(["completed", "pending"]),
                Dataset.use_for_hypothesis == True,
            ).all()

            dataset_entries: List[Dict[str, Any]] = []
            for ds in datasets:
                cols = []
                try:
                    if ds.columns_json:
                        cols = json.loads(ds.columns_json)
                except (json.JSONDecodeError, TypeError):
                    pass
                stats = {}
                try:
                    if ds.statistics_json:
                        stats = json.loads(ds.statistics_json)
                except (json.JSONDecodeError, TypeError):
                    pass
                preview = []
                try:
                    if ds.preview_json:
                        preview = json.loads(ds.preview_json)
                except (json.JSONDecodeError, TypeError):
                    pass
                dtypes = {}
                try:
                    if ds.dtypes_json:
                        dtypes = json.loads(ds.dtypes_json)
                except (json.JSONDecodeError, TypeError):
                    pass

                entry = {
                    "dataset_id": ds.id,
                    "filename": ds.filename,
                    "data_type": ds.data_type or "unknown",
                    "source_type": getattr(ds, "source_type", "upload") or "upload",
                    "n_rows": ds.n_rows or 0,
                    "n_columns": ds.n_columns or 0,
                    "columns": cols,
                    "dtypes": dtypes,
                    "statistics": stats,
                    "preview": preview[:5] if preview else [],
                    "missing_count": ds.missing_count or 0,
                    "missing_rate": ds.missing_rate or 0.0,
                    "use_for_hypothesis": True,
                }
                dataset_entries.append(entry)

                fields_set.extend(cols)
                modalities_set.add(ds.data_type or "unknown")

                for col in cols:
                    col_lower = col.lower()
                    if any(t in col_lower for t in ["label", "target", "class", "category",
                                                      "标签", "目标", "类别", "分类",
                                                      "score", "评分", "result", "结果",
                                                      "yield", "output"]):
                        if isinstance(ds.columns_json, str):
                            try:
                                col_list = json.loads(ds.columns_json)
                                if col in col_list:
                                    target_candidate_fields.append(f"{ds.filename}.{col}")
                            except Exception:
                                target_candidate_fields.append(f"{ds.filename}.{col}")
                        else:
                            target_candidate_fields.append(f"{ds.filename}.{col}")

                multimodal_datasets.append({
                    "name": ds.filename,
                    "dataset_id": ds.id,
                    "modality": ds.data_type,
                    "fields": cols,
                    "n_samples": ds.n_rows,
                    "missing_rate": ds.missing_rate,
                    "statistics": stats,
                })

            context["datasets"] = dataset_entries
            context["dataset_count"] = len(dataset_entries)
            context["available_modalities"] = sorted(list(modalities_set))
            context["field_candidates"] = list(dict.fromkeys(fields_set))[:50]
            context["target_candidates"] = list(dict.fromkeys(target_candidate_fields))[:20]

            if not dataset_entries:
                context["warnings"].append("当前项目缺少可用于假设生成的数据集，假设将基于文献事实和理论推测")

            summary_parts = []
            if dataset_entries:
                total_rows = sum(ds.get("n_rows", 0) or 0 for ds in dataset_entries)
                summary_parts.append(
                    f"共 {len(dataset_entries)} 个数据集，"
                    f"总行数 {total_rows}，"
                    f"总字段数 {len(context['field_candidates'])}，"
                    f"模态: {', '.join(context['available_modalities'])}"
                )
            if doc_summaries:
                summary_parts.append(f"文献摘要: {'; '.join(doc_summaries[:3])}")
            context["summary"] = " | ".join(summary_parts) if summary_parts else "无可用数据或文献摘要"

            context["statistics"] = {
                "sample_count": sum(ds.n_rows or 0 for ds in datasets) + len(docs),
                "field_count": len(fields_set),
                "missing_rate": round(
                    sum(ds.missing_rate or 0 for ds in datasets) / max(len(datasets), 1), 4
                ) if datasets else None,
                "dataset_count": len(datasets),
            }

        except Exception as e:
            logger.warning(f"构建数据上下文失败: {e}")
            context["warnings"].append(f"构建数据上下文时发生异常: {str(e)}")

        context["_multimodal_datasets"] = multimodal_datasets
        context["_data_linking_evidence"] = data_linking_evidence
        return context

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