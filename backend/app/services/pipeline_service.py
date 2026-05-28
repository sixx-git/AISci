"""
Pipeline 服务 - 负责按顺序执行各个 Agent
"""
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

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
        
    def run_pipeline(self, request: PipelineRunRequest) -> PipelineRunResult:
        """
        运行完整的 Pipeline
        
        Args:
            request: Pipeline 运行请求
            
        Returns:
            PipelineRunResult: Pipeline 运行结果
        """
        logger.info(f"开始执行 Pipeline: {self.run_id}, 项目: {request.project_id}")
        
        # 创建数据库记录
        self._create_pipeline_run(request)
        
        # 初始化阶段日志
        stages: List[PipelineStageLog] = [
            PipelineStageLog(stage=d["stage_enum"], status=PipelineStageStatus.PENDING)
            for d in STAGE_DEFS
        ]
        
        # 存储各阶段结果
        results: Dict[str, Any] = {}
        final_report_id: Optional[str] = None
        pipeline_start = datetime.now(timezone.utc)
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
            pipeline_end = datetime.now(timezone.utc)
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
            pipeline_end = datetime.now(timezone.utc)
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
        stage_log.start_time = datetime.now(timezone.utc)
        
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
            stage_log.end_time = datetime.now(timezone.utc)
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
        if idx >= 4:
            base["hypothesis_generation"] = results.get("hypothesis_generation", {})
        if idx >= 5:
            base["hypothesis_review"] = results.get("hypothesis_review", {})
        if idx >= 6:
            base["experiment_design"] = results.get("experiment_design", {})
        return base
    
    def _build_pipeline_run_info(self) -> Dict[str, Any]:
        """构建 Pipeline 运行摘要信息"""
        now = datetime.now(timezone.utc)
        # 实时计算耗时：从 pipeline 启动到当前时刻
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
        result = agent.generate(
            research_question=pu.get("research_question", ""),
            facts=lm.get("facts", []),
            knowledge_gaps=kg.get("knowledge_gaps", []),
            constraints=[]
        )
        return self._safe_model_dump(result)
    
    def _exec_hypothesis_review(self, hypothesis_generation: Optional[Dict]) -> dict:
        from app.agents.hypothesis_review_agent import HypothesisCandidate
        agent = get_hypothesis_review_agent()
        hg = hypothesis_generation or {}
        hypotheses = hg.get("hypotheses", [])
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
        result = agent.review(hypotheses=candidates)
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
        result = agent.generate_validation(
            hypothesis=hypothesis,
            methods=ed.get("methods", ""),
            datasets=ed.get("datasets", ""),
            metrics=ed.get("metrics", "")
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
        
        project_info = {"title": "研究项目", "id": self.run_id}
        result = agent.generate_report(
            project_info=project_info,
            problem_understanding=pu,
            literature_facts=lm.get("facts", []),
            citation_map=lm.get("citation_map", []),
            knowledge_gaps=kg,
            all_hypotheses=hg.get("hypotheses", []),
            final_hypothesis=hr,
            experiment_design=ed,
            small_validation=sv,
            pipeline_run_info=pipeline_run_info
        )
        return self._safe_model_dump(result)
    
    def _save_hypotheses(self, project_id: str, research_question: str, results: Dict[str, Any]):
        """保存假设和证据链到数据库"""
        hg = results.get("hypothesis_generation", {})
        lm = results.get("literature_mining", {})
        if not hg or not hg.get("hypotheses"):
            return
        hypo_service = HypothesisService(self.db)
        created_hypos = hypo_service.create_hypotheses_batch(
            project_id=project_id,
            research_question=research_question,
            hypotheses_list=hg["hypotheses"]
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
            started_at=datetime.now(timezone.utc),
            input_data=request.model_dump(),
            version=1
        )
        self.db.add(self.db_pipeline_run)
        self.db.commit()
        self.db.refresh(self.db_pipeline_run)
    
    def _create_stage_execution(self, order: int, stage: DB_PipelineStage, input_data: Dict[str, Any]) -> DB_PipelineStageExecution:
        """创建阶段执行记录"""
        now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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
                started = started.replace(tzinfo=timezone.utc)
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
    
    def _create_report(self, project_id: str, report_data: Dict[str, Any]) -> Optional[str]:
        """创建报告记录"""
        if not report_data:
            return None
        report_id = str(uuid.uuid4())
        title = report_data.get("paper_title", report_data.get("title", "研究报告"))
        chapters = report_data.get("chapters", {})
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
            pdf_path=report_data.get("report_id"),
            status="ready"
        )
        self.db.add(report)
        self.db.commit()
        return report_id


# ────────────── 工具函数 ──────────────

def _find_failed_stage(stages: List[PipelineStageLog]) -> Optional[PipelineStageLog]:
    """找到第一个失败的阶段"""
    for stage in stages:
        if stage.status == PipelineStageStatus.FAILED:
            return stage
    return None


def get_pipeline_service(db: Session) -> PipelineService:
    """获取 PipelineService 实例"""
    return PipelineService(db)