from abc import ABC, abstractmethod
from schemas.experiment import ExperimentPlan
from schemas.result import IterationResult


class BaseExecutor(ABC):
    """实验执行器抽象基类"""

    executor_type: str = "base"

    @abstractmethod
    def run(self, plan: ExperimentPlan) -> IterationResult:
        ...

    @abstractmethod
    def validate_plan(self, plan: ExperimentPlan) -> list[str]:
        """校验方案参数，返回错误消息列表"""
        ...
