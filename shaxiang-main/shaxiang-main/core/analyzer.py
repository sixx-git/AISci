import logging
import re
from pathlib import Path
from llm.client import LLMClient
from llm.prompts import ANALYZER_SYSTEM_PROMPT, ANALYZER_USER_TEMPLATE
from schemas.experiment import ExperimentPlan
from schemas.result import IterationResult
from schemas.analysis import AnalysisReport, VisualizationNote
from storage.repository import Repository

logger = logging.getLogger(__name__)

_CHART_HINTS = (
    (r"roc", "ROC / AUC 曲线"),
    (r"pr_?curve|precision.?recall", "Precision-Recall 曲线"),
    (r"confusion|cm_", "混淆矩阵"),
    (r"feature.?import|importance", "特征重要性"),
    (r"distrib|hist|class.?balanc|label", "分布 / 类别平衡"),
    (r"corr|heatmap", "相关性热力图"),
    (r"learning.?curve|loss", "学习曲线 / 损失"),
    (r"calib", "概率校准"),
)


def _chart_type_hint(name: str) -> str:
    lower = name.lower()
    for pattern, hint in _CHART_HINTS:
        if re.search(pattern, lower):
            return hint
    return ""


def _extract_chart_files(result: IterationResult) -> list[dict]:
    paths: list[str] = []
    raw = result.raw_output
    if isinstance(raw, dict):
        for p in raw.get("chart_paths") or []:
            if isinstance(p, str) and p.strip():
                paths.append(p.strip())
    for dp in result.data_points or []:
        if getattr(dp, "key", None) == "chart_path" and isinstance(dp.value, str):
            paths.append(dp.value.strip())

    seen = set()
    files = []
    for p in paths:
        name = Path(p).name
        if not name or name in seen:
            continue
        seen.add(name)
        files.append({"name": name, "path": p, "hint": _chart_type_hint(name)})
    return files


def _fallback_visualization_notes(chart_files: list[dict]) -> list[VisualizationNote]:
    notes = []
    for c in chart_files:
        hint = c.get("hint") or "实验可视化"
        notes.append(
            VisualizationNote(
                chart_name=c["name"],
                description=f"本轮产出「{hint}」图（{c['name']}），请结合对应指标解读曲线或矩阵中的主要模式。",
            )
        )
    return notes


class ResultAnalyzer:
    """AI 驱动的实验结果分析器"""

    def __init__(self, llm_client: LLMClient, repository: Repository):
        self.llm = llm_client
        self.repository = repository

    def analyze(
        self,
        result: IterationResult,
        plan: ExperimentPlan,
        experiment_id: str = None,
    ) -> AnalysisReport:
        """分析单轮实验结果"""
        # 构建对比数据
        previous_comparison = []
        previous_results = None
        if experiment_id:
            latest = self.repository.get_latest_iteration(experiment_id)
            if latest and latest.result:
                prev_metrics = latest.result.get("data_points", [])
                for pm in prev_metrics:
                    if isinstance(pm, dict):
                        for cm in result.data_points:
                            if isinstance(cm, dict) and cm.get("key") == pm.get("key"):
                                previous_comparison.append({
                                    "name": pm["key"],
                                    "old_value": pm.get("value"),
                                    "new_value": cm.get("value"),
                                })
                if previous_comparison:
                    previous_results = True

        # 构建 data_points 列表
        dp_list = [{"key": dp.key, "value": dp.value} for dp in result.data_points]
        chart_files = _extract_chart_files(result)

        prompt = ANALYZER_USER_TEMPLATE.render(
            plan_title=plan.title,
            plan_description=plan.description,
            plan_parameters=str(plan.parameters),
            success_criteria="; ".join(plan.success_criteria) if plan.success_criteria else "无明确标准",
            data_points=dp_list,
            result_summary=(result.summary or "").strip(),
            chart_files=chart_files or None,
            previous_comparison=previous_comparison if previous_comparison else None,
            previous_results=previous_results,
        )

        report = self.llm.generate_to_model(
            prompt=prompt,
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            model_class=AnalysisReport,
        )
        # 无论如何由结果轮次覆盖，避免模型漏填/乱填
        report.iteration_number = result.iteration_number

        if chart_files and not report.visualization_notes:
            report.visualization_notes = _fallback_visualization_notes(chart_files)
        else:
            # 补全缺失的 chart_name
            name_by_order = [c["name"] for c in chart_files]
            for i, note in enumerate(report.visualization_notes or []):
                if not (note.chart_name or "").strip() and i < len(name_by_order):
                    note.chart_name = name_by_order[i]

        logger.info(f"分析报告 (第{result.iteration_number}轮): {report.overall_assessment}")
        return report
