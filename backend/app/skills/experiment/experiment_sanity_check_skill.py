"""
实验设计真实性审查 Skill
参考能力：AI Scientist evaluation — 对实验设计中可能的失败问题反思
——检查实验设计是否具备数据集 / baseline / metrics / 统计检验 / 可执行步骤。
"""
import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

REQUIRED_COMPONENTS = {
    "datasets": "数据集定义",
    "baselines": "基线方法",
    "metrics": "评估指标",
    "statistical_test": "统计检验方法",
    "executable_steps": "可执行实验步骤",
}

RECOMMENDATION_HINTS = {
    "datasets": "建议明确数据集名称、规模、来源，避免仅描述为'公开数据集'",
    "baselines": "建议列出具体基线方法名称及引用来源",
    "metrics": "建议指定至少 2 个量化评估指标及计算公式",
    "statistical_test": "建议明确统计检验方法（t-test / bootstrap / permutation test）",
    "executable_steps": "建议以序号形式列出可逐条执行的实验步骤，每步包含预期输入/输出",
}


class ExperimentSanityCheckSkill(BaseSkill):
    """实验设计真实性审查 Skill

    输入:
      - experiment_design: dict   实验设计各字段 (methods, datasets, baselines,
                                   metrics, experimental_steps, expected_results, limitations)

    输出 (SkillResult.data):
      - executable: bool                  整体可执行性判断
      - missing_items: List[str]          缺失组件
      - weak_points: List[str]            薄弱项
      - recommendations: List[str]        改进建议
      - component_checks: dict            逐项检查结果
    """

    name = "ExperimentSanityCheck"
    description = "检查实验设计是否包含必要的数据集/Baseline/指标/统计检验/可执行步骤"
    source_reference = "AI Scientist (arxiv:2408.06292) — evaluation & reflective review 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)

        design = input_data.get("experiment_design", {})
        if not isinstance(design, dict):
            design = {}

        component_checks: Dict[str, bool] = {}
        missing_items: List[str] = []
        weak_points: List[str] = []
        recommendations: List[str] = []

        datasets_val = self._get_field(design, "datasets", "source_data")
        if self._is_meaningful(datasets_val):
            component_checks["datasets"] = True
            if self._is_vague(datasets_val):
                weak_points.append("datasets — 描述较笼统")
                recommendations.append(RECOMMENDATION_HINTS["datasets"])
        else:
            component_checks["datasets"] = False
            missing_items.append("datasets")
            recommendations.append(RECOMMENDATION_HINTS["datasets"])

        baselines_val = self._get_field(design, "baselines")
        if self._is_meaningful(baselines_val):
            component_checks["baselines"] = True
            if self._is_vague(baselines_val):
                weak_points.append("baselines — 缺少具体方法名称或引用")
                recommendations.append(RECOMMENDATION_HINTS["baselines"])
        else:
            component_checks["baselines"] = False
            missing_items.append("baselines")
            recommendations.append(RECOMMENDATION_HINTS["baselines"])

        metrics_val = self._get_field(design, "metrics")
        if self._is_meaningful(metrics_val):
            component_checks["metrics"] = True
            if self._is_vague(metrics_val):
                weak_points.append("metrics — 缺少量化指标及计算方式")
                recommendations.append(RECOMMENDATION_HINTS["metrics"])
        else:
            component_checks["metrics"] = False
            missing_items.append("metrics")
            recommendations.append(RECOMMENDATION_HINTS["metrics"])

        steps_val = self._get_field(design, "experimental_steps")
        if self._is_meaningful(steps_val):
            component_checks["executable_steps"] = True
            if len(steps_val) < 100 or "\n" not in steps_val:
                weak_points.append("experimental_steps — 格式应为多步骤序号列表")
                recommendations.append(RECOMMENDATION_HINTS["executable_steps"])
        else:
            component_checks["executable_steps"] = False
            missing_items.append("executable_steps")
            recommendations.append(RECOMMENDATION_HINTS["executable_steps"])

        stat_val = self._get_field(design, "experimental_steps")
        has_stat = bool(stat_val and any(
            kw in stat_val.lower()
            for kw in ("t-test", "p-value", "bootstrap", "permutation",
                       "confidence interval", "wilcoxon", "chi-square",
                       "mann-whitney", "anova", "fisher", "t test")
        ))
        component_checks["statistical_test"] = has_stat
        if not has_stat:
            recommendations.append(RECOMMENDATION_HINTS["statistical_test"])

        executable = all(component_checks.values())

        if missing_items:
            result.add_warning(f"缺失组件: {', '.join(missing_items)}")
        if weak_points:
            result.add_warning(f"薄弱项: {', '.join(weak_points)}")

        result.data = {
            "executable": executable,
            "missing_items": missing_items,
            "weak_points": weak_points,
            "recommendations": recommendations,
            "component_checks": component_checks,
        }
        result.metadata = {
            "required_components": list(REQUIRED_COMPONENTS.keys()),
            "total_checks": len(REQUIRED_COMPONENTS),
            "passed_checks": sum(1 for v in component_checks.values() if v),
        }
        return result

    @staticmethod
    def _get_field(design: dict, *keys: str) -> str:
        for k in keys:
            val = design.get(k, "")
            if isinstance(val, str) and val.strip():
                return val.strip()
        return ""

    @staticmethod
    def _is_meaningful(val: str) -> bool:
        if not val:
            return False
        vague_fillers = {"待补充", "待补充datasets", "待补充baselines", "待补充metrics",
                         "待补充experimental_steps", "N/A", "n/a", "无", "none"}
        return val.strip() not in vague_fillers and len(val.strip()) >= 10

    @staticmethod
    def _is_vague(val: str) -> bool:
        vague_signals = [
            "公开数据集", "常见数据集", "标准数据集", "标注数据集",
            "标准方法", "基线方法", "经典方法", "常用方法",
            "常用指标", "准确率、召回率", "精确度", "适当的方法",
        ]
        val_lower = val.lower()
        return any(s in val for s in vague_signals) and len(val) < 120