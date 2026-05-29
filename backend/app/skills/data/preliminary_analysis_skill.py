"""
初步分析 Skill
根据 MultimodalDataset + Hypothesis/ExperimentDesign 做初步分析，
输出统计摘要、特征向量、图表数据和初步结果。
"""
import logging
import hashlib
import math
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class PreliminaryAnalysisSkill(BaseSkill):
    """初步分析 Skill

    输入:
      - multimodal_datasets: List[dict]      多模态数据集
      - hypothesis: str                      假设内容
      - experiment_design: dict              实验设计
      - methods: str                         研究方法
      - metrics: str                         评估指标

    输出 (SkillResult.data):
      - summary_statistics: dict             统计摘要（均值、方差、分布等）
      - feature_vectors: List[dict]          特征向量
      - plots: List[dict]                    图表数据规格（供 ReportChartGeneration 使用）
      - preliminary_result: dict             初步分析结论
      - correlations: List[dict]             相关性分析
      - anomalies: List[dict]                异常值检测
    """

    name = "PreliminaryAnalysis"
    description = "根据多模态数据集和假设/实验设计进行统计摘要、特征向量提取和图表数据生成"
    source_reference = "AI Scientist (arxiv:2408.06292) — automated data analysis & visualization 参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        multimodal_datasets = input_data.get("multimodal_datasets", [])
        hypothesis = input_data.get("hypothesis", "")
        experiment_design = input_data.get("experiment_design", {})
        methods = input_data.get("methods", "")
        metrics = input_data.get("metrics", "")

        summary_stats: Dict[str, Any] = {}
        feature_vectors: List[dict] = []
        plots: List[dict] = []
        correlations: List[dict] = []
        anomalies: List[dict] = []

        for ds in multimodal_datasets:
            ds_id = ds.get("file_id", hashlib.md5(str(ds).encode()).hexdigest()[:8])
            ds_rows = ds.get("sample_data", [])
            ds_columns = ds.get("columns", [])
            ds_stats = ds.get("statistics", {})

            if ds_columns:
                numeric_cols = [
                    c for c, t in ds.get("dtypes", {}).items() if t in ("integer", "float", "numeric")
                ]

                if numeric_cols:
                    feature_vectors.append({
                        "dataset_id": ds_id,
                        "features": numeric_cols,
                        "n_samples": ds.get("n_rows", 0),
                        "feature_stats": {c: ds_stats.get(c, {}) for c in numeric_cols if c in ds_stats},
                    })

                    if len(numeric_cols) >= 2:
                        for i, c1 in enumerate(numeric_cols):
                            for c2 in numeric_cols[i + 1:]:
                                corr = self._compute_pearson_correlation(
                                    [r.get(c1) for r in ds_rows if c1 in r and c2 in r],
                                    [r.get(c2) for r in ds_rows if c1 in r and c2 in r],
                                )
                                correlations.append({
                                    "dataset_id": ds_id,
                                    "column_x": c1,
                                    "column_y": c2,
                                    "pearson_r": corr,
                                })

                if numeric_cols:
                    for col in numeric_cols[:6]:
                        vals = [r.get(col) for r in ds_rows if col in r and r.get(col) is not None]
                        if not vals:
                            continue
                        mean_val = sum(vals) / len(vals)
                        std_val = (sum((x - mean_val) ** 2 for x in vals) / len(vals)) ** 0.5
                        threshold = 2.5 * std_val
                        col_anomalies = [
                            {
                                "index": i,
                                "value": v,
                                "expected_range": [round(mean_val - threshold, 4), round(mean_val + threshold, 4)],
                                "reason": "outlier_by_std" if abs(v - mean_val) > threshold else "normal",
                            }
                            for i, v in enumerate(vals)
                            if abs(v - mean_val) > threshold
                        ]
                        anomalies.extend(col_anomalies[:10])

            ds_stats_summary = {}
            for col, stat in ds.get("statistics", {}).items():
                if stat:
                    ds_stats_summary[col] = stat
            if ds_stats_summary:
                summary_stats[ds.get("file_name", ds_id)] = ds_stats_summary

        if numeric_cols := self._collect_all_numeric_cols(multimodal_datasets):
            if len(numeric_cols) >= 2:
                plot_line = {
                    "plot_id": hashlib.md5(f"line:{numeric_cols[0]}:{numeric_cols[1]}".encode()).hexdigest()[:12],
                    "type": "line",
                    "title": f"{numeric_cols[0]} vs {numeric_cols[1]} 趋势",
                    "description": f"折线图展示 {numeric_cols[0]} 与 {numeric_cols[1]} 的变化趋势",
                    "data_source": numeric_cols[0],
                    "x_key": "index",
                    "y_key": numeric_cols[1],
                    "x_label": "样本序号",
                    "y_label": numeric_cols[1],
                }
                plots.append(plot_line)

            plot_bar = {
                "plot_id": hashlib.md5(f"bar:{numeric_cols[0]}".encode()).hexdigest()[:12],
                "type": "bar",
                "title": f"{numeric_cols[0]} 分布柱状图",
                "description": f"柱状图展示 {numeric_cols[0]} 的数值分布情况",
                "data_source": numeric_cols[0],
                "x_key": "bin",
                "y_key": "count",
                "x_label": numeric_cols[0],
                "y_label": "频次",
            }
            plots.append(plot_bar)

            if len(numeric_cols) >= 2:
                plot_scatter = {
                    "plot_id": hashlib.md5(f"scatter:{numeric_cols[0]}:{numeric_cols[1]}".encode()).hexdigest()[:12],
                    "type": "scatter",
                    "title": f"{numeric_cols[0]} vs {numeric_cols[1]} 散点图",
                    "description": f"散点图展示 {numeric_cols[0]} 与 {numeric_cols[1]} 的相关性",
                    "data_source": f"{numeric_cols[0]},{numeric_cols[1]}",
                    "x_key": numeric_cols[0],
                    "y_key": numeric_cols[1],
                    "x_label": numeric_cols[0],
                    "y_label": numeric_cols[1],
                }
                plots.append(plot_scatter)

        if len(numeric_cols) >= 3:
            plot_heatmap = {
                "plot_id": hashlib.md5(f"heatmap:{':'.join(numeric_cols[:3])}".encode()).hexdigest()[:12],
                "type": "heatmap",
                "title": "特征相关性热力图",
                "description": "热力图展示数值特征间的相关性矩阵",
                "data_source": "correlation_matrix",
                "x_key": "columns",
                "y_key": "columns",
                "x_label": "特征",
                "y_label": "特征",
            }
            plots.append(plot_heatmap)

        preliminary_result = self._build_preliminary_result(
            summary_stats, feature_vectors, correlations, anomalies, hypothesis
        )

        result.data = {
            "summary_statistics": summary_stats,
            "feature_vectors": feature_vectors,
            "plots": plots,
            "preliminary_result": preliminary_result,
            "correlations": correlations,
            "anomalies": anomalies,
        }
        result.metadata = {
            "datasets_analyzed": len(multimodal_datasets),
            "numeric_features": len(numeric_cols),
            "plots_generated": len(plots),
            "anomalies_detected": len(anomalies),
            "analyzed_at": datetime.now().isoformat(),
        }
        return result

    @staticmethod
    def _compute_pearson_correlation(x: list, y: list) -> Optional[float]:
        if not x or not y or len(x) != len(y) or len(x) < 2:
            return None
        clean_pairs = [(xv, yv) for xv, yv in zip(x, y) if xv is not None and yv is not None]
        if len(clean_pairs) < 2:
            return None
        xs, ys = zip(*clean_pairs)
        n = len(xs)
        xs = [float(v) for v in xs]
        ys = [float(v) for v in ys]
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, ys)) / n
        std_x = (sum((xi - mean_x) ** 2 for xi in xs) / n) ** 0.5
        std_y = (sum((yi - mean_y) ** 2 for yi in ys) / n) ** 0.5
        if std_x == 0 or std_y == 0:
            return 0.0
        return round(cov / (std_x * std_y), 4)

    @staticmethod
    def _collect_all_numeric_cols(datasets: List[dict]) -> List[str]:
        seen = set()
        cols = []
        for ds in datasets:
            for col, dtype in ds.get("dtypes", {}).items():
                if dtype in ("integer", "float", "numeric") and col not in seen:
                    seen.add(col)
                    cols.append(col)
        return cols

    def _build_preliminary_result(
        self,
        summary_stats: dict,
        feature_vectors: list,
        correlations: list,
        anomalies: list,
        hypothesis: str,
    ) -> Dict[str, Any]:
        result = {
            "is_analyzable": bool(summary_stats),
            "data_quality": "good" if len(anomalies) < 10 else "needs_attention",
            "recommendations": [],
        }

        if not summary_stats:
            result["recommendations"].append("数据集缺少可用于分析的结构化数据")
        else:
            result["recommendations"].append("已有足够数据进行初步统计分析")

        if feature_vectors:
            result["recommendations"].append(
                f"检测到 {len(feature_vectors)} 个数据集含 {sum(len(fv['features']) for fv in feature_vectors)} 个数值特征，可用于建模"
            )

        if correlations:
            high_corrs = [c for c in correlations if c.get("pearson_r") is not None and abs(c["pearson_r"]) > 0.7]
            if high_corrs:
                result["recommendations"].append(
                    f"发现 {len(high_corrs)} 对强相关特征，建议考虑降维或特征选择"
                )

        if anomalies:
            result["recommendations"].append(
                f"检测到 {len(anomalies)} 个异常数据点，建议在分析前进行数据清洗"
            )

        if hypothesis:
            result["hypothesis_feedback"] = f"初步分析已就绪，可针对假设「{hypothesis[:100]}」进行验证"

        return result