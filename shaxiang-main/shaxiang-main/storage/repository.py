from abc import ABC, abstractmethod
from typing import Optional
from schemas.experiment import Experiment
from schemas.result import IterationResult
from schemas.analysis import AnalysisReport, IterationDecision


class IterationRecord:
    """一轮迭代的完整记录"""
    def __init__(
        self,
        iteration_number: int,
        plan: dict = None,
        result: dict = None,
        analysis: dict = None,
        decision: dict = None,
        metrics: dict = None,
        status: str = "pending",
        error_message: str = "",
        duration_seconds: float = 0,
    ):
        self.iteration_number = iteration_number
        self.plan = plan or {}
        self.result = result or {}
        self.analysis = analysis or {}
        self.decision = decision or {}
        self.metrics = metrics or {}
        self.status = status
        self.error_message = error_message
        self.duration_seconds = duration_seconds


class Repository(ABC):
    """实验数据存储抽象接口"""

    # --- 实验 ---
    @abstractmethod
    def save_experiment(self, experiment: Experiment) -> str:
        ...

    @abstractmethod
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        ...

    @abstractmethod
    def list_experiments(self, status: str = None) -> list[Experiment]:
        ...

    @abstractmethod
    def update_experiment(self, experiment: Experiment) -> None:
        ...

    @abstractmethod
    def delete_experiment(self, experiment_id: str) -> None:
        """删除实验及其所有迭代记录"""
        ...

    # --- 迭代记录 ---
    @abstractmethod
    def save_iteration(self, experiment_id: str, record: IterationRecord) -> None:
        ...

    @abstractmethod
    def get_iterations(self, experiment_id: str) -> list[IterationRecord]:
        ...

    @abstractmethod
    def get_latest_iteration(self, experiment_id: str) -> Optional[IterationRecord]:
        ...

    # --- 指标 ---
    @abstractmethod
    def get_metrics_history(self, experiment_id: str) -> list[dict]:
        """获取所有轮次的指标数据，用于趋势图绘制"""
        ...
