"""从项目 data_finder 合并 CSV / 数据集生成报告图表。"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _resolve_csv_path(merged: Dict[str, Any]) -> Optional[Path]:
    raw = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
    if not raw:
        return None
    path = Path(str(raw))
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path if path.exists() else None


def load_merged_csv_rows(
    project_id: str,
    db: Any,
    *,
    row_limit: int = 400,
) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """加载 data_finder 合并 CSV 样本行与数值列名。"""
    from app.services.data_finder_service import get_data_finder_service

    df_results = get_data_finder_service(db).load_results(project_id) or {}
    merged = df_results.get("merged") if isinstance(df_results.get("merged"), dict) else {}
    csv_path = _resolve_csv_path(merged)
    if not csv_path:
        return [], [], ""

    try:
        import pandas as pd

        frame = pd.read_csv(csv_path, nrows=row_limit)
    except Exception as exc:
        logger.warning("读取合并 CSV 失败: %s", exc)
        return [], [], ""

    numeric_cols = [
        c for c in frame.columns
        if c in (merged.get("columns") or frame.columns)
        and str(c).startswith("_") is False
        and pd.api.types.is_numeric_dtype(frame[c])
    ]
    if not numeric_cols:
        numeric_cols = [
            c for c in frame.columns
            if pd.api.types.is_numeric_dtype(frame[c]) and not str(c).startswith("_")
        ]

    rows = frame.where(frame.notna(), None).to_dict(orient="records")
    dataset_label = csv_path.name
    return rows, numeric_cols, dataset_label


def build_plot_specs(
    numeric_cols: List[str],
    *,
    dataset_id: str,
    dataset_label: str,
) -> List[Dict[str, Any]]:
    """基于数值列构建真实数据图表规格。"""
    plots: List[Dict[str, Any]] = []
    if not numeric_cols:
        return plots

    ds_id = dataset_id or "merged_csv"

    if "slice_index" in numeric_cols and "mean" in numeric_cols:
        plots.append({
            "plot_id": hashlib.md5(f"line:{ds_id}:slice_mean".encode()).hexdigest()[:12],
            "type": "line",
            "title": "FITS 光谱切片均值（slice_index → mean）",
            "description": f"基于上传 FITS 解析合并表 {dataset_label} 的切片统计",
            "data_source": "slice_index,mean",
            "x_key": "slice_index",
            "y_key": "mean",
            "x_label": "slice_index",
            "y_label": "mean",
            "source_dataset_id": ds_id,
            "is_generated_from_real_data": True,
        })

    for col in numeric_cols[:4]:
        if col in ("slice_index",):
            continue
        plots.append({
            "plot_id": hashlib.md5(f"hist:{ds_id}:{col}".encode()).hexdigest()[:12],
            "type": "histogram",
            "title": f"{col} 分布直方图",
            "description": f"合并数据集 {dataset_label} 字段 {col}",
            "data_source": col,
            "x_key": col,
            "y_key": col,
            "x_label": col,
            "y_label": "频次",
            "source_dataset_id": ds_id,
            "is_generated_from_real_data": True,
        })

    if len(numeric_cols) >= 2:
        c1, c2 = numeric_cols[0], numeric_cols[1]
        if c1 != c2:
            plots.append({
                "plot_id": hashlib.md5(f"scatter:{ds_id}:{c1}:{c2}".encode()).hexdigest()[:12],
                "type": "scatter",
                "title": f"{c1} vs {c2} 散点图",
                "description": f"合并数据集 {dataset_label}",
                "data_source": f"{c1},{c2}",
                "x_key": c1,
                "y_key": c2,
                "x_label": c1,
                "y_label": c2,
                "source_dataset_id": ds_id,
                "is_generated_from_real_data": True,
            })

    return plots


def generate_report_plots_from_project(
    project_id: str,
    db: Any,
    output_dir: str,
    *,
    row_limit: int = 400,
) -> List[Dict[str, Any]]:
    """从项目合并 CSV 生成报告图表（无数据时返回空列表）。"""
    rows, numeric_cols, label = load_merged_csv_rows(project_id, db, row_limit=row_limit)
    if not rows or not numeric_cols:
        return []

    plot_specs = build_plot_specs(
        numeric_cols,
        dataset_id=f"project_{project_id[:8]}",
        dataset_label=label,
    )
    if not plot_specs:
        return []

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    async def _run() -> List[Dict[str, Any]]:
        from app.skills.report.report_chart_generation_skill import ReportChartGenerationSkill

        skill = ReportChartGenerationSkill()
        result = await skill.run(
            input_data={
                "plot_specs": plot_specs,
                "data": rows,
                "output_dir": output_dir,
                "format": "both",
                "dpi": 150,
                "figure_size": (10, 6),
            },
            context={"stage": "report_regenerate"},
        )
        return list(result.data.get("charts") or [])

    try:
        charts = asyncio.run(_run())
        logger.info("项目 %s 生成报告图表 %d 张", project_id, len(charts))
        return charts
    except Exception as exc:
        logger.warning("报告图表生成失败: %s", exc)
        return []
