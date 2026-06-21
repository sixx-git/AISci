"""数据集概览 Skill"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.modeling._utils import (
    infer_target_candidates,
    is_categorical_series,
    is_numeric_series,
    load_dataframe,
)

logger = logging.getLogger(__name__)


class DatasetProfilingSkill(BaseSkill):
    name = "DatasetProfiling"
    description = "分析 CSV 数据集字段类型、缺失率、统计量、类别分布与目标变量候选"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        dataset_id = input_data.get("dataset_id", "")
        csv_path = input_data.get("csv_path") or input_data.get("file_path", "")

        try:
            df = load_dataframe(csv_path)
        except Exception as exc:
            result.add_error(str(exc))
            return result

        import pandas as pd

        columns = list(df.columns)
        dtypes = {col: str(dt) for col, dt in df.dtypes.to_dict().items()}
        total_cells = int(len(df) * max(len(columns), 1))
        missing_count = int(df.isnull().sum().sum())
        missing_rate = round(missing_count / total_cells, 4) if total_cells else 0.0

        numeric_stats: Dict[str, Any] = {}
        categorical_distribution: Dict[str, Any] = {}
        outlier_hints: List[str] = []

        for col in columns:
            series = df[col]
            missing_col = int(series.isnull().sum())
            if is_numeric_series(series):
                clean = series.dropna()
                if len(clean) == 0:
                    continue
                q1 = float(clean.quantile(0.25))
                q3 = float(clean.quantile(0.75))
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = int(((clean < lower) | (clean > upper)).sum())
                numeric_stats[col] = {
                    "mean": round(float(clean.mean()), 4),
                    "std": round(float(clean.std()), 4) if len(clean) > 1 else 0.0,
                    "min": float(clean.min()),
                    "max": float(clean.max()),
                    "missing": missing_col,
                    "missing_rate": round(missing_col / max(len(df), 1), 4),
                }
                if outliers > 0:
                    outlier_hints.append(
                        f"列 `{col}` 检测到约 {outliers} 个 IQR 异常值"
                    )
            elif is_categorical_series(series):
                top_vals = series.value_counts().head(10).to_dict()
                categorical_distribution[col] = {
                    "unique": int(series.nunique(dropna=True)),
                    "missing": missing_col,
                    "missing_rate": round(missing_col / max(len(df), 1), 4),
                    "top_values": {str(k): int(v) for k, v in top_vals.items()},
                }

        target_candidates = infer_target_candidates(columns)
        if not target_candidates and len(columns) == 1:
            target_candidates = columns[:1]

        result.data = {
            "dataset_id": dataset_id,
            "csv_path": csv_path,
            "n_rows": int(len(df)),
            "n_columns": int(len(columns)),
            "columns": columns,
            "dtypes": dtypes,
            "missing_count": missing_count,
            "missing_rate": missing_rate,
            "numeric_statistics": numeric_stats,
            "categorical_distribution": categorical_distribution,
            "outlier_hints": outlier_hints,
            "target_candidates": target_candidates,
        }
        return result
