import math
import random
import time
from datetime import datetime

from schemas.experiment import ExperimentPlan, VariableDefinition
from schemas.result import IterationResult, DataPoint
from executors.base import BaseExecutor


class SimulationExecutor(BaseExecutor):
    """
    模拟实验执行器 - 模拟药物剂量优化场景

    模拟函数:
    - efficacy(dosage, frequency) 基于对数曲线 + 余弦波动
    - side_effect(dosage) 基于幂函数

    最优点大约在 dosage≈70, frequency≈3
    """
    executor_type = "simulation"

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed)

    def run(self, plan: ExperimentPlan) -> IterationResult:
        start_time = datetime.now().isoformat()

        # 从 plan.parameters 提取参数
        params = plan.parameters
        dosage = float(params.get("dosage", 50))
        frequency = int(params.get("frequency", 2))

        # 模拟计算（带随机噪声）
        efficacy = self._calc_efficacy(dosage, frequency)
        side_effect = self._calc_side_effect(dosage)
        overall_score = efficacy - 0.3 * side_effect  # 综合评分

        data_points = [
            DataPoint(key="efficacy_score", value=round(efficacy, 4)),
            DataPoint(key="side_effect_score", value=round(side_effect, 4)),
            DataPoint(key="overall_score", value=round(overall_score, 4)),
            DataPoint(key="dosage", value=dosage),
            DataPoint(key="frequency", value=frequency),
            DataPoint(key="sample_size", value=plan.sample_size),
        ]

        end_time = datetime.now().isoformat()

        return IterationResult(
            iteration_number=0,  # 由 engine 设置
            plan_used=plan.model_dump(),
            start_time=start_time,
            end_time=end_time,
            status="success",
            data_points=data_points,
            summary=f"剂量={dosage}mg, 频率={frequency}次/天 → 疗效={efficacy:.3f}, 副作用={side_effect:.3f}, 综合={overall_score:.3f}",
        )

    def validate_plan(self, plan: ExperimentPlan) -> list[str]:
        errors = []
        params = plan.parameters
        dosage = params.get("dosage")
        frequency = params.get("frequency")

        if dosage is None:
            errors.append("缺少必需参数: dosage")
        elif not (10 <= float(dosage) <= 100):
            errors.append("dosage 必须在 10-100 之间")

        if frequency is None:
            errors.append("缺少必需参数: frequency")
        elif not (1 <= int(frequency) <= 4):
            errors.append("frequency 必须在 1-4 之间")

        return errors

    def _calc_efficacy(self, dosage: float, frequency: int) -> float:
        """疗效计算: 对数曲线 + 频率调制 + 噪声"""
        base = 1 - math.exp(-0.04 * dosage)
        freq_mod = 0.1 * math.sin(0.8 * frequency)
        noise = self.rng.gauss(0, 0.03)
        return max(0, min(1, base + freq_mod + noise))

    def _calc_side_effect(self, dosage: float) -> float:
        """副作用计算: 幂函数 + 噪声"""
        base = 0.0001 * dosage ** 1.5
        noise = self.rng.gauss(0, 0.02)
        return max(0, min(1, base + noise))
