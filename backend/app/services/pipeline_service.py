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

from app.schemas.pipeline import (
    PipelineStatus,
    PipelineStage,
    PipelineStageStatus,
    PipelineStageLog,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineRunResult
)

logger = logging.getLogger(__name__)


class PipelineService:
    """Pipeline 服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pipeline_id = str(uuid.uuid4())
        
    def run_pipeline(self, request: PipelineRunRequest) -> PipelineRunResult:
        """
        运行完整的 Pipeline
        
        Args:
            request: Pipeline 运行请求
            
        Returns:
            PipelineRunResult: Pipeline 运行结果
        """
        logger.info(f"开始执行 Pipeline: {self.pipeline_id}, 项目: {request.project_id}")
        
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
        
        try:
            # 阶段 1: ProblemUnderstandingAgent
            stage_idx = 0
            stages[stage_idx].status = PipelineStageStatus.RUNNING
            stages[stage_idx].start_time = datetime.now()
            try:
                problem_understanding = self._run_problem_understanding(request.research_question)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = problem_understanding.model_dump()
                results['problem_understanding'] = problem_understanding.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                literature_mining = self._run_literature_mining(request.project_id, request.research_question)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = literature_mining.model_dump()
                results['literature_mining'] = literature_mining.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                knowledge_gap = self._run_knowledge_gap(literature_mining)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = knowledge_gap.model_dump()
                results['knowledge_gap'] = knowledge_gap.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                hypothesis_generation = self._run_hypothesis_generation(problem_understanding, literature_mining, knowledge_gap)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = hypothesis_generation.model_dump()
                results['hypothesis_generation'] = hypothesis_generation.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                hypothesis_review = self._run_hypothesis_review(hypothesis_generation)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = hypothesis_review.model_dump()
                results['hypothesis_review'] = hypothesis_review.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                experiment_design = self._run_experiment_design(hypothesis_review)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = experiment_design.model_dump()
                results['experiment_design'] = experiment_design.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                small_validation = self._run_small_validation(experiment_design)
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = small_validation.model_dump()
                results['small_validation'] = small_validation.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            try:
                report_generation = self._run_report_generation(
                    problem_understanding,
                    literature_mining,
                    knowledge_gap,
                    hypothesis_generation,
                    hypothesis_review,
                    experiment_design,
                    small_validation
                )
                stages[stage_idx].status = PipelineStageStatus.COMPLETED
                stages[stage_idx].output_data = report_generation.model_dump()
                results['report_generation'] = report_generation.model_dump()
            except Exception as e:
                stages[stage_idx].status = PipelineStageStatus.FAILED
                stages[stage_idx].error_message = str(e)
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
            
            logger.info(f"Pipeline 执行成功: {self.pipeline_id}, 总耗时: {total_duration:.2f}s")
            
            return PipelineRunResult(
                pipeline_id=self.pipeline_id,
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
            
            logger.error(f"Pipeline 执行失败: {self.pipeline_id}, 错误: {e}", exc_info=True)
            
            return PipelineRunResult(
                pipeline_id=self.pipeline_id,
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
        hypothesis_generation,
        hypothesis_review,
        experiment_design,
        small_validation
    ):
        """运行报告生成 Agent"""
        agent = get_report_generation_agent()
        project_info = {
            "title": "研究项目",
            "id": self.pipeline_id
        }
        return agent.generate_report(
            project_info=project_info,
            problem_understanding=problem_understanding.model_dump(),
            literature_facts=[f.model_dump() for f in literature_mining.facts],
            citation_map=[c.model_dump() for c in literature_mining.citation_map],
            knowledge_gaps=knowledge_gaps.model_dump(),
            final_hypothesis=hypothesis_review.model_dump() if hypothesis_review else {},
            experiment_design=experiment_design or {},
            small_validation=small_validation or {}
        )


# 全局单例
_service_instance: Optional[PipelineService] = None


def get_pipeline_service(db: Session) -> PipelineService:
    """获取 PipelineService 实例"""
    return PipelineService(db)
