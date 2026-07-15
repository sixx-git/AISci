"""
数据集推荐模块

职责：根据实验假设，推荐可用于验证假设的经典数据集，
区分"必须上传"和"可选补充"，并给出下载链接。
"""
import logging
from typing import Optional

from llm.client import LLMClient
from llm.prompts import DATASET_ADVISOR_SYSTEM_PROMPT, DATASET_ADVISOR_USER_TEMPLATE
from schemas.dataset import DatasetRecommendationReport
from storage.repository import Repository

logger = logging.getLogger(__name__)


class DatasetAdvisor:
    """AI 驱动的数据集推荐器"""

    def __init__(self, llm_client: LLMClient, repository: Repository):
        self.llm = llm_client
        self.repository = repository

    def recommend_datasets(
        self,
        hypothesis: str,
        constraints: list[str] = None,
        previous_result_summary: str = None,
        human_feedback: str = None,
    ) -> DatasetRecommendationReport:
        """
        根据实验假设推荐数据集

        Args:
            hypothesis: 用户的实验假设
            constraints: 约束条件
            previous_result_summary: 上一轮实验结果摘要（用于迭代推荐）
            human_feedback: 人工反馈
        """
        prompt = DATASET_ADVISOR_USER_TEMPLATE.render(
            hypothesis=hypothesis,
            constraints=constraints or [],
            previous_result_summary=previous_result_summary,
            human_feedback=human_feedback,
        )

        report = self.llm.generate_to_model(
            prompt=prompt,
            system_prompt=DATASET_ADVISOR_SYSTEM_PROMPT,
            model_class=DatasetRecommendationReport,
        )
        logger.info(f"推荐了 {len(report.recommended_datasets)} 个数据集")
        return report

    def recommend_next_datasets(
        self,
        experiment_id: str,
        human_feedback: str = None,
    ) -> DatasetRecommendationReport:
        """基于实验历史，推荐下一轮需要的数据集"""
        # 获取最新的分析和决策
        latest = self.repository.get_latest_iteration(experiment_id)
        if not latest:
            raise ValueError("无历史迭代记录")

        from schemas.analysis import AnalysisReport, IterationDecision
        analysis = AnalysisReport.model_validate(latest.analysis) if latest.analysis else None
        decision = IterationDecision.model_validate(latest.decision) if latest.decision else None

        # 获取实验信息
        from storage.sqlite_store import SQLiteRepository
        if isinstance(self.repository, SQLiteRepository):
            # 需要获取 experiment 的 hypothesis
            pass

        # 构建结果摘要
        result_summary = latest.result.get("summary", "") if latest.result else ""
        if analysis:
            result_summary += f"\n分析: {analysis.summary}"
            if analysis.identified_issues:
                result_summary += f"\n问题: {'; '.join(analysis.identified_issues)}"

        # 从 decision 中提取需要的调整方向
        needs = decision.next_plan_adjustments if decision else []

        hypothesis = needs[0] if needs else "继续验证原假设"

        return self.recommend_datasets(
            hypothesis=hypothesis,
            previous_result_summary=result_summary,
            human_feedback=human_feedback,
        )
