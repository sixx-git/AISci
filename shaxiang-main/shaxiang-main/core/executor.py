import logging
from typing import Optional

from schemas.experiment import ExperimentPlan
from schemas.result import IterationResult
from executors.base import BaseExecutor
from executors.simulation import SimulationExecutor
from executors.sandbox import SandboxExecutor

logger = logging.getLogger(__name__)


class ExperimentExecutor:
    """实验执行调度器"""

    def __init__(self):
        self.registry: dict[str, BaseExecutor] = {}
        # 注册默认执行器
        self.register(SimulationExecutor())
        self.register(SandboxExecutor())

    def register(self, executor: BaseExecutor):
        self.registry[executor.executor_type] = executor

    def execute(self, plan: ExperimentPlan, executor_type: str) -> IterationResult:
        executor = self.registry.get(executor_type)
        if not executor:
            raise ValueError(f"未找到执行器类型: {executor_type}，可用类型: {list(self.registry.keys())}")

        # 校验参数
        errors = executor.validate_plan(plan)
        if errors:
            return IterationResult(
                iteration_number=0,
                plan_used=plan.model_dump(),
                status="failed",
                error_message="; ".join(errors),
                summary=f"方案校验失败: {'; '.join(errors)}",
            )

        try:
            result = executor.run(plan)
            logger.info(f"实验执行完成: {result.status}")
            return result
        except Exception as e:
            logger.error(f"实验执行异常: {e}")
            return IterationResult(
                iteration_number=0,
                plan_used=plan.model_dump(),
                status="failed",
                error_message=str(e),
                summary=f"执行异常: {e}",
            )
