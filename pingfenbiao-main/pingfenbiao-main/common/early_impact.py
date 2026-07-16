"""
早期影响力预测模块 — EarlyImpactPredictionSkill

基于当前引用趋势、领域引用特征和论文生命周期模型，预测论文未来引用量。
提供 1年、3年、5年 引用量预测和高影响概率评估。
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EarlyImpactPredictor:
    """早期影响力预测器。

    使用论文生命周期模型（生命周期曲线）进行预测：
    - 论文引用增长遵循S型曲线或幂律衰减模型
    - 早期引用速度是预测未来影响力的关键指标
    """

    def __init__(self):
        pass

    def predict(
        self,
        cited_count: int,
        publication_year: int,
        citation_velocity: float,
        field_percentile: float,
        venue_tier: str = "",  # A/B/C/Unranked/Preprint
        age_years: int | None = None,
    ) -> dict[str, Any]:
        """预测论文未来引用量。

        Args:
            cited_count: 当前引用数
            publication_year: 发表年份
            citation_velocity: 年引用速度
            field_percentile: 领域引用百分位
            venue_tier: 期刊/会议等级
            age_years: 论文年龄（年），自动计算

        Returns:
            预测结果字典。
        """
        current_year = time.localtime().tm_year
        age = age_years if age_years is not None else max(1, current_year - publication_year)

        # 1. 计算领域调整因子
        field_factor = self._field_adjustment_factor(field_percentile)

        # 2. 计算期刊等级调整因子
        venue_factor = self._venue_adjustment_factor(venue_tier)

        # 3. 计算论文生命周期阶段
        life_stage = self._life_cycle_stage(age)

        # 4. 预测未来引用量
        predictions = self._project_citations(
            cited_count=cited_count,
            velocity=citation_velocity,
            age=age,
            field_factor=field_factor,
            venue_factor=venue_factor,
            life_stage=life_stage,
        )

        # 5. 计算高影响概率
        high_impact_prob = self._high_impact_probability(
            cited_count=cited_count,
            velocity=citation_velocity,
            field_percentile=field_percentile,
            venue_factor=venue_factor,
            age=age,
        )

        # 6. 不确定性量化
        uncertainty = self._estimate_uncertainty(age, cited_count, field_percentile)

        return {
            "current_state": {
                "cited_count": cited_count,
                "age_years": age,
                "citation_velocity": citation_velocity,
                "life_stage": life_stage,
            },
            "predictions": predictions,
            "high_impact_probability": high_impact_prob,
            "uncertainty": uncertainty,
            "confidence_level": self._confidence_level(age, cited_count),
            "methodology": {
                "model": "hybrid_lifecycle_regression",
                "field_adjustment": field_factor,
                "venue_adjustment": venue_factor,
                "description": "结合论文生命周期模型和领域回归分析",
            },
        }

    def _field_adjustment_factor(self, field_percentile: float) -> float:
        """根据领域百分位计算调整因子。

        在领域内排名前10%的论文，预测增长应该更乐观。
        """
        if field_percentile >= 90:
            return 1.5
        elif field_percentile >= 75:
            return 1.3
        elif field_percentile >= 50:
            return 1.1
        elif field_percentile >= 25:
            return 0.9
        else:
            return 0.7

    def _venue_adjustment_factor(self, venue_tier: str) -> float:
        """根据期刊/会议等级计算调整因子。"""
        tier_map = {
            "A": 1.3,
            "CCF-A": 1.3,
            "B": 1.15,
            "CCF-B": 1.15,
            "C": 1.0,
            "CCF-C": 1.0,
            "Unranked": 0.85,
            "Preprint": 0.7,
        }
        return tier_map.get(venue_tier, 1.0)

    def _life_cycle_stage(self, age: int) -> str:
        """判断论文生命周期阶段。

        - infant: 1年内，引用很少，不确定性极高
        - early: 1-3年，引用快速增长期
        - mature: 3-7年，引用稳定期，预测最可靠
        - late: 7-15年，引用开始饱和
        - legacy: 15年以上，引用缓慢下降
        """
        if age <= 1:
            return "infant"
        elif age <= 3:
            return "early"
        elif age <= 7:
            return "mature"
        elif age <= 15:
            return "late"
        else:
            return "legacy"

    def _project_citations(
        self,
        cited_count: int,
        velocity: float,
        age: int,
        field_factor: float,
        venue_factor: float,
        life_stage: str,
    ) -> dict[str, Any]:
        """投影未来引用量。

        使用混合模型：
        - 短期（1年）：基于当前速度的线性外推
        - 中期（3年）：考虑增长衰减的指数模型
        - 长期（5年）：考虑领域饱和的对数模型
        """
        # 综合调整因子
        combined_factor = (field_factor + venue_factor) / 2

        # 1年预测：线性外推（考虑季节性和领域因子）
        pred_1y = round(cited_count + velocity * combined_factor)

        # 3年预测：指数衰减模型
        # 论文引用增长通常会逐渐放缓，衰减系数取决于生命周期阶段
        decay_rates = {
            "infant": 0.15,
            "early": 0.10,
            "mature": 0.20,
            "late": 0.30,
            "legacy": 0.40,
        }
        decay_rate = decay_rates.get(life_stage, 0.20)

        # 3年累计引用 = 当前 + 第1年 + 第2年 + 第3年
        year1 = velocity * combined_factor
        year2 = year1 * (1 - decay_rate) * combined_factor
        year3 = year2 * (1 - decay_rate) * combined_factor
        pred_3y = round(cited_count + year1 + year2 + year3)

        # 5年预测：对数饱和模型
        # 引用存在上限，随时间趋近于饱和值
        year4 = year3 * (1 - decay_rate * 1.2) * combined_factor
        year5 = year4 * (1 - decay_rate * 1.5) * combined_factor
        pred_5y = round(cited_count + year1 + year2 + year3 + year4 + year5)

        # 饱和引用量估算（长期上限）
        if velocity > 0 and decay_rate > 0:
            saturation_estimate = round(cited_count + velocity / decay_rate * combined_factor)
        else:
            saturation_estimate = pred_5y * 2

        return {
            "1_year": {
                "predicted_citations": max(pred_1y, cited_count),
                "expected_new_citations": round(velocity * combined_factor, 1),
                "method": "linear_extrapolation",
            },
            "3_year": {
                "predicted_citations": max(pred_3y, pred_1y),
                "expected_new_citations": round(year1 + year2 + year3, 1),
                "method": "exponential_decay",
            },
            "5_year": {
                "predicted_citations": max(pred_5y, pred_3y),
                "expected_new_citations": round(year1 + year2 + year3 + year4 + year5, 1),
                "method": "logarithmic_saturation",
            },
            "saturation_estimate": saturation_estimate,
            "growth_trajectory": self._growth_trajectory(life_stage, velocity, combined_factor),
        }

    def _growth_trajectory(self, life_stage: str, velocity: float, combined_factor: float) -> str:
        """判断增长轨迹类型。"""
        adjusted_velocity = velocity * combined_factor

        if adjusted_velocity > 50:
            return "explosive"  # 爆发式增长
        elif adjusted_velocity > 20:
            return "rapid"      # 快速增长
        elif adjusted_velocity > 5:
            return "steady"     # 稳定增长
        elif adjusted_velocity > 1:
            return "moderate"   # 温和增长
        else:
            return "slow"       # 缓慢增长

    def _high_impact_probability(
        self,
        cited_count: int,
        velocity: float,
        field_percentile: float,
        venue_factor: float,
        age: int,
    ) -> dict[str, Any]:
        """计算高影响概率。

        定义"高影响"为：5年内引用量 > 100（普通领域）或 > 50（小众领域）。
        """
        # 基础概率（基于当前状态）
        base_prob = min(1.0, cited_count / 200 + velocity / 30)

        # 领域百分位调整
        percentile_boost = (field_percentile - 50) / 100  # -0.5 到 +0.5

        # 期刊等级调整
        venue_boost = (venue_factor - 1.0) * 0.5

        # 年龄调整（太新的论文不确定性高，太老的论文已经定型）
        if age <= 1:
            age_penalty = 0.3
        elif age <= 3:
            age_penalty = 0.1
        elif age <= 7:
            age_penalty = 0.0
        else:
            age_penalty = 0.2

        # 综合概率
        final_prob = max(0.0, min(1.0, base_prob + percentile_boost + venue_boost - age_penalty))

        # 概率区间解释
        if final_prob >= 0.7:
            interpretation = "high"      # 高概率
        elif final_prob >= 0.4:
            interpretation = "moderate"  # 中等概率
        elif final_prob >= 0.2:
            interpretation = "low"       # 低概率
        else:
            interpretation = "very_low"  # 极低概率

        # 5年内达到不同引用阈值的概率
        thresholds = [50, 100, 200, 500]
        threshold_probs = {}
        for t in thresholds:
            # 简化的概率计算：基于当前速度和饱和估计
            if cited_count >= t:
                threshold_probs[f"{t}+"] = 1.0
            else:
                # 使用对数几率模型
                gap = t - cited_count
                odds = math.exp(-gap / max(velocity * 2, 1))
                threshold_probs[f"{t}+"] = round(1 / (1 + odds), 3)

        return {
            "probability": round(final_prob, 3),
            "interpretation": interpretation,
            "threshold_probabilities": threshold_probs,
            "contributing_factors": {
                "base_signal": round(base_prob, 3),
                "field_percentile_boost": round(percentile_boost, 3),
                "venue_boost": round(venue_boost, 3),
                "age_penalty": round(age_penalty, 3),
            },
        }

    def _estimate_uncertainty(
        self,
        age: int,
        cited_count: int,
        field_percentile: float,
    ) -> dict[str, Any]:
        """估计预测的不确定性。

        不确定性来源：
        1. 数据稀疏性（引用太少）
        2. 论文太新（生命周期阶段不确定）
        3. 领域特殊性（小众领域引用数天然少）
        """
        # 数据稀疏性不确定性
        if cited_count < 5:
            data_uncertainty = "high"
        elif cited_count < 20:
            data_uncertainty = "medium"
        else:
            data_uncertainty = "low"

        # 年龄不确定性
        if age <= 1:
            age_uncertainty = "very_high"
        elif age <= 3:
            age_uncertainty = "high"
        elif age <= 7:
            age_uncertainty = "medium"
        else:
            age_uncertainty = "low"

        # 领域不确定性（小众领域引用数方差大）
        if field_percentile < 10 or field_percentile > 90:
            field_uncertainty = "medium"  # 极端百分位的不确定性
        else:
            field_uncertainty = "low"

        # 综合不确定性等级
        levels = {"very_high": 4, "high": 3, "medium": 2, "low": 1}
        total = levels.get(data_uncertainty, 2) + levels.get(age_uncertainty, 2) + levels.get(field_uncertainty, 2)
        if total >= 10:
            overall = "very_high"
        elif total >= 7:
            overall = "high"
        elif total >= 5:
            overall = "medium"
        else:
            overall = "low"

        # 预测区间（95%置信区间，简化估算）
        uncertainty_factor = {
            "very_high": 3.0,
            "high": 2.0,
            "medium": 1.5,
            "low": 1.2,
        }.get(overall, 1.5)

        return {
            "overall_level": overall,
            "breakdown": {
                "data_sparsity": data_uncertainty,
                "paper_age": age_uncertainty,
                "field_specificity": field_uncertainty,
            },
            "prediction_interval_factor": uncertainty_factor,
            "interpretation": self._uncertainty_interpretation(overall),
        }

    def _uncertainty_interpretation(self, level: str) -> str:
        """不确定性等级解释。"""
        interpretations = {
            "very_high": "预测可靠性极低，当前数据不足以做出有意义的预测。建议等待论文发表至少2年后重新评估。",
            "high": "预测可靠性较低，存在较大不确定性。预测结果仅供参考，实际引用量可能大幅偏离。",
            "medium": "预测可靠性中等，基本趋势可信但具体数值可能存在±50%的偏差。",
            "low": "预测可靠性较高，基于充足的历史数据，预测结果具有较好的参考价值。",
        }
        return interpretations.get(level, "不确定性未知")

    def _confidence_level(self, age: int, cited_count: int) -> str:
        """计算整体置信度等级。"""
        if age >= 3 and cited_count >= 20:
            return "high"
        elif age >= 1 and cited_count >= 5:
            return "medium"
        else:
            return "low"


def predict_early_impact(
    cited_count: int,
    publication_year: int,
    citation_velocity: float,
    field_percentile: float = 50.0,
    venue_tier: str = "",
    age_years: int | None = None,
) -> dict[str, Any]:
    """便捷函数：预测论文早期影响力。

    Args:
        cited_count: 当前引用数
        publication_year: 发表年份
        citation_velocity: 年引用速度
        field_percentile: 领域引用百分位（默认50）
        venue_tier: 期刊/会议等级
        age_years: 论文年龄（可选，自动计算）

    Returns:
        预测结果字典。
    """
    predictor = EarlyImpactPredictor()
    return predictor.predict(
        cited_count=cited_count,
        publication_year=publication_year,
        citation_velocity=citation_velocity,
        field_percentile=field_percentile,
        venue_tier=venue_tier,
        age_years=age_years,
    )
