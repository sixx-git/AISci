"""
Pipeline 服务 - 负责按顺序执行各个 Agent
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
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

from app.schemas.pipeline import (
    PipelineStatus,
    PipelineStage,
    PipelineStageStatus,
    PipelineStageLog,
    PipelineRunRequest,
    PipelineRunResult
)

logger = logging.getLogger(__name__)


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
        stages = [
            PipelineStageLog(
                stage=PipelineStage.PROBLEM_UNDERSTANDING,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.LITERATURE_MINING,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.KNOWLEDGE_GAP,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.HYPOTHESIS_GENERATION,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.HYPOTHESIS_REVIEW,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.EXPERIMENT_DESIGN,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.SMALL_VALIDATION,
                status=PipelineStageStatus.PENDING
            ),
            PipelineStageLog(
                stage=PipelineStage.REPORT_GENERATION,
                status=PipelineStageStatus.PENDING
            )
        ]
        
        # 存储各阶段结果
        results = {}
        
        # Pipeline 开始时间
        pipeline_start = datetime.now()
        
        final_report_id: Optional[str] = None
        
        try:
            # 更新 Pipeline 状态为运行中
            self.db_pipeline_run.status = DB_PipelineStatus.RUNNING
            self.db_pipeline_run.started_at = pipeline_start
            self.db.commit()
            
            # 阶段 1: ProblemUnderstandingAgent
            stage_idx = 0
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(0, DB_PipelineStage.PROBLEM_UNDERSTANDING, {"research_question": request.research_question})
            try:
                problem_understanding = self._run_problem_understanding(request.research_question)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = problem_understanding.model_dump()
                results['problem_understanding'] = problem_understanding.model_dump()
                self._update_stage_execution(db_stage, "completed", output=problem_understanding.model_dump())
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"问题理解阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 2: LiteratureMiningAgent
            stage_idx = 1
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(1, DB_PipelineStage.LITERATURE_MINING, {"project_id": request.project_id, "research_question": request.research_question})
            try:
                literature_mining = self._run_literature_mining(request.project_id, request.research_question)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = literature_mining.model_dump()
                results['literature_mining'] = literature_mining.model_dump()
                self._update_stage_execution(db_stage, "completed", output=literature_mining.model_dump())
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"文献挖掘阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 3: KnowledgeGapAgent
            stage_idx = 2
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(2, DB_PipelineStage.KNOWLEDGE_GAP, {})
            try:
                knowledge_gap = self._run_knowledge_gap(literature_mining)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = knowledge_gap.model_dump()
                results['knowledge_gap'] = knowledge_gap.model_dump()
                self._update_stage_execution(db_stage, "completed", output=knowledge_gap.model_dump())
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"知识缺口阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 4: HypothesisGenerationAgent
            stage_idx = 3
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(3, DB_PipelineStage.HYPOTHESIS_GENERATION, {})
            try:
                hypothesis_generation = self._run_hypothesis_generation(problem_understanding, literature_mining, knowledge_gap)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = hypothesis_generation.model_dump()
                results['hypothesis_generation'] = hypothesis_generation.model_dump()
                self._update_stage_execution(db_stage, "completed", output=hypothesis_generation.model_dump())
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"假设生成阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 5: HypothesisReviewAgent
            stage_idx = 4
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(4, DB_PipelineStage.HYPOTHESIS_REVIEW, {})
            try:
                hypothesis_review = self._run_hypothesis_review(hypothesis_generation)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = hypothesis_review.model_dump()
                results['hypothesis_review'] = hypothesis_review.model_dump()
                self._update_stage_execution(db_stage, "completed", output=hypothesis_review.model_dump())
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"假设评估阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 6: ExperimentDesignAgent
            stage_idx = 5
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(5, DB_PipelineStage.EXPERIMENT_DESIGN, {})
            try:
                experiment_design = self._run_experiment_design(hypothesis_review)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = experiment_design
                results['experiment_design'] = experiment_design
                self._update_stage_execution(db_stage, "completed", output=experiment_design)
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"实验设计阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 7: SmallValidationAgent
            stage_idx = 6
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(6, DB_PipelineStage.SMALL_VALIDATION, {})
            try:
                small_validation = self._run_small_validation(experiment_design)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = small_validation
                results['small_validation'] = small_validation
                self._update_stage_execution(db_stage, "completed", output=small_validation)
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"小样验证阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # 阶段 8: ReportGenerationAgent
            stage_idx = 7
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            db_stage = self._create_stage_execution(7, DB_PipelineStage.REPORT_GENERATION, {})
            try:
                # 构建运行摘要信息
                pipeline_run_info = {
                    "run_id": self.run_id,
                    "started_at": self.db_pipeline_run.started_at.isoformat() if self.db_pipeline_run and self.db_pipeline_run.started_at else None,
                    "completed_at": datetime.now().isoformat(),
                    "total_duration_ms": self.db_pipeline_run.total_duration_ms if self.db_pipeline_run else 0,
                    "status": "completed",
                    "stages": [
                        {
                            "stage": str(stage.stage),
                            "status": str(stage.status),
                            "started_at": stage.started_at.isoformat() if stage.started_at else None,
                            "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                            "duration_ms": stage.duration_ms
                        }
                        for stage in self.db_stage_executions.values()
                    ]
                }
                
                report_generation = self._run_report_generation(
                    problem_understanding,
                    literature_mining,
                    knowledge_gap,
                    hypothesis_review,
                    experiment_design,
                    small_validation,
                    pipeline_run_info
                )
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = report_generation
                results['report_generation'] = report_generation
                self._update_stage_execution(db_stage, "completed", output=report_generation)
                
                # 创建报告记录
                final_report_id = self._create_report(request.project_id, report_generation)
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
                self._update_stage_execution(db_stage, "failed", error=str(e))
                logger.error(f"报告生成阶段失败: {e}", exc_info=True)
                raise
            finally:
                stages[stage_idx].end_time = datetime.now()
                stages[stage_idx].duration = (
                    (stages[stage_idx].end_time - stages[stage_idx].start_time).total_seconds()
                    if stages[stage_idx].start_time else None
                )
            
            # Pipeline 完成
            pipeline_end = datetime.now()
            total_duration = (pipeline_end - pipeline_start).total_seconds()
            
            logger.info(f"Pipeline 执行成功: {self.run_id}, 总耗时: {total_duration:.2f}s")
            
            # 更新数据库
            self._complete_pipeline_run(pipeline_end, total_duration, results, final_report_id)
            
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=request.project_id,
                research_question=request.research_question,
                status=PipelineStatus.COMPLETED,
                stages=stages,
                total_duration=total_duration,
                problem_understanding=results.get('problem_understanding'),
                literature_mining=results.get('literature_mining'),
                knowledge_gap=results.get('knowledge_gap'),
                hypothesis_generation=results.get('hypothesis_generation'),
                hypothesis_review=results.get('hypothesis_review'),
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
                report_generation=results.get('report_generation'),
                final_report=results.get('report_generation'),
                created_at=pipeline_start,
                completed_at=pipeline_end
            )
            
        except Exception as e:
            # 计算总耗时
            pipeline_end = datetime.now()
            total_duration = (pipeline_end - pipeline_start).total_seconds()
            
            # 找到失败的阶段
            failed_stage = None
            for _, stage in enumerate(stages):
                if stage.status == PipelineStageStatus.FAILED:
                    failed_stage = stage
                    break
            
            logger.error(f"Pipeline 执行失败: {self.run_id}, 错误: {e}", exc_info=True)
            
            # 更新数据库
            self._fail_pipeline_run(pipeline_end, total_duration, results, failed_stage, str(e))
            
            return PipelineRunResult(
                pipeline_id=self.run_id,
                project_id=request.project_id,
                research_question=request.research_question,
                status=PipelineStatus.FAILED,
                stages=stages,
                total_duration=total_duration,
                problem_understanding=results.get('problem_understanding'),
                literature_mining=results.get('literature_mining'),
                knowledge_gap=results.get('knowledge_gap'),
                hypothesis_generation=results.get('hypothesis_generation'),
                hypothesis_review=results.get('hypothesis_review'),
                experiment_design=results.get('experiment_design'),
                small_validation=results.get('small_validation'),
                report_generation=results.get('report_generation'),
                final_report=None,
                created_at=pipeline_start,
                completed_at=pipeline_end
            )
    
    def _create_pipeline_run(self, request: PipelineRunRequest):
        """创建 Pipeline 运行记录"""
        self.db_pipeline_run = DB_PipelineRun(
            id=str(uuid.uuid4()),
            run_id=self.run_id,
            project_id=request.project_id,
            research_question=request.research_question,
            status=DB_PipelineStatus.RUNNING,
            started_at=datetime.now(),
            input_data=request.model_dump(),
            version=1
        )
        self.db.add(self.db_pipeline_run)
        self.db.commit()
        self.db.refresh(self.db_pipeline_run)
    
    def _create_stage_execution(self, order: int, stage: DB_PipelineStage, input_data: Dict[str, Any]) -> DB_PipelineStageExecution:
        """创建阶段执行记录"""
        now = datetime.now()
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
        now = datetime.now()
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
            db_stage.duration_ms = int((now - db_stage.started_at).total_seconds() * 1000)
        
        self.db.commit()
    
    def _complete_pipeline_run(self, completed_at: datetime, total_duration: float, results: Dict[str, Any], final_report_id: Optional[str]):
        """完成 Pipeline 运行"""
        self.db_pipeline_run.status = DB_PipelineStatus.COMPLETED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = int(total_duration * 1000)
        self.db_pipeline_run.output_data = results
        if final_report_id:
            self.db_pipeline_run.final_report_id = final_report_id
        self.db.commit()
    
    def _fail_pipeline_run(self, completed_at: datetime, total_duration: float, results: Dict[str, Any], failed_stage: Optional[PipelineStageLog], error: str):
        """失败 Pipeline 运行"""
        self.db_pipeline_run.status = DB_PipelineStatus.FAILED
        self.db_pipeline_run.completed_at = completed_at
        self.db_pipeline_run.total_duration_ms = int(total_duration * 1000)
        self.db_pipeline_run.error_message = error
        if failed_stage:
            self.db_pipeline_run.failed_stage = DB_PipelineStage(failed_stage.stage.value)
        self.db.commit()
    
    def _create_report(self, project_id: str, report_data: Dict[str, Any]) -> str:
        """创建报告记录"""
        report_id = str(uuid.uuid4())
        title = report_data.get("paper_title", "研究报告")
        report = Report(
            id=report_id,
            project_id=project_id,
            title=title,
            full_content=report_data.get("markdown_content", ""),
            status="ready"
        )
        self.db.add(report)
        self.db.commit()
        return report_id
    
    def _run_problem_understanding(self, research_question: str):
        """运行问题理解 Agent"""
        agent = get_problem_understanding_agent()
        return agent.analyze(research_question=research_question)
    
    def _run_literature_mining(self, project_id: str, research_question: str):
        """运行文献挖掘 Agent"""
        agent = get_literature_mining_agent()
        return agent.mine(project_id=project_id, research_question=research_question)
    
    def _run_knowledge_gap(self, literature_mining):
        """运行知识缺口 Agent"""
        agent = get_knowledge_gap_agent()
        return agent.analyze(
            facts=literature_mining.facts,
            uncertain_points=literature_mining.uncertain_points
        )
    
    def _run_hypothesis_generation(self, problem_understanding, literature_mining, knowledge_gap):
        """运行假设生成 Agent"""
        agent = get_hypothesis_generation_agent()
        return agent.generate(
            research_question=problem_understanding.research_question,
            facts=[f.model_dump() for f in literature_mining.facts],
            knowledge_gaps=[g.model_dump() for g in knowledge_gap.knowledge_gaps],
            constraints=[]
        )
    
    def _run_hypothesis_review(self, hypothesis_generation):
        """运行假设评估 Agent"""
        from app.agents.hypothesis_review_agent import HypothesisCandidate
        agent = get_hypothesis_review_agent()
        # 转换为 HypothesisCandidate 格式
        candidates = [
            HypothesisCandidate(
                hypothesis=h.hypothesis,
                rationale=h.rationale,
                novelty=h.novelty,
                testability=h.testability,
                required_data=h.required_data,
                possible_method=h.possible_method,
                risk=h.risk
            )
            for h in hypothesis_generation.hypotheses
        ]
        return agent.review(hypotheses=candidates)
    
    def _run_experiment_design(self, hypothesis_review):
        """运行实验设计 Agent"""
        agent = get_experiment_design_agent()
        # 取最高分的假设
        if hypothesis_review.reviews:
            best_review = hypothesis_review.reviews[0]  # 按综合得分降序，第一个是最高的
            return agent.design_experiment(
                hypothesis=best_review.hypothesis
            )
        return None
    
    def _run_small_validation(self, experiment_design):
        """运行小样验证 Agent"""
        agent = get_small_validation_agent()
        if experiment_design:
            return agent.generate_validation(
                hypothesis=experiment_design.get("hypothesis", ""),
                methods=experiment_design.get("methods", ""),
                datasets=experiment_design.get("datasets", ""),
                metrics=experiment_design.get("metrics", "")
            )
        return None
    
    def _run_report_generation(
        self,
        problem_understanding,
        literature_mining,
        knowledge_gaps,
        hypothesis_review,
        experiment_design,
        small_validation,
        pipeline_run_info=None
    ):
        """运行报告生成 Agent"""
        agent = get_report_generation_agent()
        project_info = {
            "title": "研究项目",
            "id": self.run_id
        }
        return agent.generate_report(
            project_info=project_info,
            problem_understanding=problem_understanding.model_dump(),
            literature_facts=[f.model_dump() for f in literature_mining.facts],
            citation_map=[c.model_dump() for c in literature_mining.citation_map],
            knowledge_gaps=knowledge_gaps.model_dump(),
            final_hypothesis=hypothesis_review.model_dump() if hypothesis_review else {},
            experiment_design=experiment_design or {},
            small_validation=small_validation or {},
            pipeline_run_info=pipeline_run_info
        )


def get_pipeline_service(db: Session) -> PipelineService:
    """获取 PipelineService 实例"""
    return PipelineService(db)
