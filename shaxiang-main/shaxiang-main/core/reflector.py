import logging
from typing import Optional

from llm.client import LLMClient
from llm.prompts import REFLECTOR_SYSTEM_PROMPT, REFLECTOR_USER_TEMPLATE
from schemas.analysis import AnalysisReport, IterationDecision
from storage.repository import Repository

logger = logging.getLogger(__name__)


class IterationReflector:
    """AI 驱动的迭代决策器"""

    def __init__(self, llm_client: LLMClient, repository: Repository):
        self.llm = llm_client
        self.repository = repository

    def reflect(
        self,
        analysis: AnalysisReport,
        experiment_id: str = None,
        max_iterations: int = 10,
        completed_iterations: int = 0,
    ) -> IterationDecision:
        """生成本轮迭代决策"""
        # 计算改进趋势
        improvement_trends = []
        if experiment_id:
            improvement_trends = self._compute_improvement_trends(experiment_id)

        prompt = REFLECTOR_USER_TEMPLATE.render(
            iteration_number=analysis.iteration_number,
            analysis=analysis,
            improvement_trends=improvement_trends if improvement_trends else None,
            completed_iterations=completed_iterations,
            max_iterations=max_iterations,
        )

        decision = self.llm.generate_to_model(
            prompt=prompt,
            system_prompt=REFLECTOR_SYSTEM_PROMPT,
            model_class=IterationDecision,
        )
        logger.info(
            f"迭代决策 (第{analysis.iteration_number}轮): "
            f"should_continue={decision.should_continue}"
        )
        return decision

    def _compute_improvement_trends(self, experiment_id: str) -> list[dict]:
        """从历史记录中计算改进趋势"""
        metrics_history = self.repository.get_metrics_history(experiment_id)
        if len(metrics_history) < 2:
            return []

        trends = []
        # 获取所有指标名（排除 iteration）
        if not metrics_history:
            return trends

        metric_keys = [k for k in metrics_history[-1].keys() if k != "iteration"]

        for key in metric_keys:
            values = []
            for h in metrics_history:
                v = h.get(key)
                if v is not None and isinstance(v, (int, float)):
                    values.append(v)

            if len(values) >= 2:
                recent = values[-1]
                previous = values[-2]
                if recent > previous:
                    direction = "improving"
                elif recent < previous:
                    direction = "declining"
                else:
                    direction = "stable"
                trends.append({
                    "metric": key,
                    "direction": direction,
                    "description": f"{previous:.3f} → {recent:.3f}",
                })

        return trends
