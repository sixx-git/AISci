"""结果自校正 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.modeling._utils import PILOT_VALIDATION_ROW_THRESHOLD


class SelfCorrectionSkill(BaseSkill):
    name = "SelfCorrection"
    description = "根据数据与模型评估结果生成改进建议"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        profile = input_data.get("profile", {})
        evaluation = input_data.get("evaluation", {})
        task_type = input_data.get("task_type", "unknown")
        target_column = input_data.get("target_column", "")

        suggestions: List[Dict[str, str]] = []
        n_rows = int(profile.get("n_rows", 0))
        missing_rate = float(profile.get("missing_rate", 0) or 0)
        models = evaluation.get("models", [])
        best_name = evaluation.get("best_model", "")

        best_metrics = {}
        for m in models:
            if m.get("model_name") == best_name:
                best_metrics = m.get("metrics", {})
                break

        if n_rows < PILOT_VALIDATION_ROW_THRESHOLD:
            suggestions.append(
                {
                    "reason": f"样本量仅 {n_rows} 行，低于 {PILOT_VALIDATION_ROW_THRESHOLD} 行",
                    "suggestion": "当前结果应视为 pilot validation，不宜外推为最终结论",
                    "next_action": "补充更多真实样本或进行分层/bootstrap 验证",
                }
            )

        if missing_rate > 0.1:
            suggestions.append(
                {
                    "reason": f"整体缺失率 {missing_rate:.1%} 偏高",
                    "suggestion": "优先做缺失机制分析与字段级清洗",
                    "next_action": "对高缺失列删除或引入更合适的插补策略",
                }
            )

        if task_type == "classification":
            for col, dist in (profile.get("categorical_distribution") or {}).items():
                if col == target_column:
                    top_values = dist.get("top_values", {})
                    if top_values:
                        counts = list(top_values.values())
                        if counts and max(counts) / max(sum(counts), 1) > 0.85:
                            suggestions.append(
                                {
                                    "reason": f"目标列 `{target_column}` 存在明显类别不平衡",
                                    "suggestion": "考虑 class_weight、重采样或分层评估",
                                    "next_action": "重新训练并报告 macro-F1 / per-class recall",
                                }
                            )
                            break

            f1 = best_metrics.get("f1")
            if f1 is not None and f1 < 0.6:
                suggestions.append(
                    {
                        "reason": f"最佳模型 F1={f1:.3f} 偏低",
                        "suggestion": "当前特征对目标预测能力有限或任务定义需调整",
                        "next_action": "增加领域特征、检查 target 定义或尝试更复杂模型",
                    }
                )
        elif task_type == "regression":
            r2 = best_metrics.get("r2")
            if r2 is not None and r2 < 0.3:
                suggestions.append(
                    {
                        "reason": f"最佳模型 R²={r2:.3f} 偏低",
                        "suggestion": "特征与目标线性/非线性关系可能较弱",
                        "next_action": "检查异常值、特征工程或引入非线性模型",
                    }
                )

        correlations_weak = profile.get("outlier_hints") or []
        if len(correlations_weak) >= 2:
            suggestions.append(
                {
                    "reason": "多个字段存在异常值提示",
                    "suggestion": "异常值可能干扰基线模型并造成过拟合风险",
                    "next_action": "做 Winsorize/robust scaling 并比较清洗前后指标",
                }
            )

        if len(models) >= 2:
            train_gap = self._estimate_overfit_risk(models, task_type)
            if train_gap:
                suggestions.append(train_gap)

        if not suggestions:
            suggestions.append(
                {
                    "reason": "未发现显著风险项",
                    "suggestion": "基线建模流程已完成，可进入假设验证或扩大样本",
                    "next_action": "记录当前 best_model 指标并在报告中标注 pilot validation",
                }
            )

        result.data = {
            "self_correction_suggestions": suggestions,
            "is_pilot_validation": n_rows < PILOT_VALIDATION_ROW_THRESHOLD,
        }
        return result

    @staticmethod
    def _estimate_overfit_risk(models: List[Dict[str, Any]], task_type: str) -> Dict[str, str] | None:
        if task_type == "classification":
            scores = [m.get("metrics", {}).get("accuracy") for m in models]
            metric_name = "accuracy"
        else:
            scores = [m.get("metrics", {}).get("r2") for m in models]
            metric_name = "R²"
        scores = [s for s in scores if s is not None]
        if len(scores) < 2:
            return None
        if max(scores) - min(scores) > 0.25:
            return {
                "reason": f"不同基线模型 {metric_name} 差异较大（{min(scores):.3f} ~ {max(scores):.3f}）",
                "suggestion": "可能存在过拟合或模型对特征尺度敏感",
                "next_action": "使用交叉验证并固定特征预处理流水线",
            }
        return None
