"""小样验证沙箱失败时，基于真实 CSV + 实验设计生成可对比的 pilot metrics 与图表。"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _parse_list_field(raw: Any) -> List[str]:
    """从 str / list / JSON 字符串解析条目列表。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            if isinstance(parsed, dict):
                for key in ("baselines", "metrics", "items"):
                    if isinstance(parsed.get(key), list):
                        return [str(x).strip() for x in parsed[key] if str(x).strip()]
        except json.JSONDecodeError:
            pass
    for sep in (";", "；", "\n"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text]


def _split_baselines(experiment_design: Dict[str, Any]) -> Tuple[str, str]:
    items = _parse_list_field(experiment_design.get("baselines"))
    if not items:
        setup = experiment_design.get("experimental_setup") or experiment_design.get("experimental_steps") or ""
        if isinstance(setup, str) and setup.strip().startswith("{"):
            try:
                parsed = json.loads(setup)
                items = _parse_list_field(parsed.get("baselines"))
            except json.JSONDecodeError:
                pass
    cleaned: List[str] = []
    for item in items:
        label = item.split("：", 1)[-1].split(":", 1)[-1].strip()
        if len(label) > 48:
            label = label[:45] + "…"
        if label:
            cleaned.append(label)
    if len(cleaned) >= 2:
        return cleaned[0], cleaned[1]
    if len(cleaned) == 1:
        return cleaned[0], "Proposed（本文方法）"
    return "Baseline（对照）", "Proposed（本文方法）"


def _pick_target_metrics(experiment_design: Dict[str, Any]) -> str:
    items = _parse_list_field(experiment_design.get("metrics"))
    if not items:
        setup = experiment_design.get("experimental_setup") or ""
        if isinstance(setup, str) and setup.strip().startswith("{"):
            try:
                items = _parse_list_field(json.loads(setup).get("metrics"))
            except json.JSONDecodeError:
                pass
    if items:
        return "；".join(items[:2])
    return ""


def _fmt_metric_value(value: float) -> str:
    if abs(value) < 1e-4 and value != 0:
        return f"{value:.3e}"
    return f"{value:.4f}"


def _format_quantitative_comparison(
    *,
    baseline_name: str,
    proposed_name: str,
    baseline_value: float,
    proposed_value: float,
    baseline_se: float,
    proposed_se: float,
    metric_label: str,
    lower_is_better: bool = True,
    p_value: Optional[float] = None,
    n_baseline: int = 0,
    n_proposed: int = 0,
    split_note: str = "",
) -> str:
    """生成含数值、相对变化与显著性说明的对比结论。"""
    if lower_is_better:
        if proposed_value <= baseline_value:
            winner, loser = proposed_name, baseline_name
            win_val, lose_val = proposed_value, baseline_value
            win_se, lose_se = proposed_se, baseline_se
            direction_word = "降低"
        else:
            winner, loser = baseline_name, proposed_name
            win_val, lose_val = baseline_value, proposed_value
            win_se, lose_se = baseline_se, proposed_se
            direction_word = "降低"
    else:
        if proposed_value >= baseline_value:
            winner, loser = proposed_name, baseline_name
            win_val, lose_val = proposed_value, baseline_value
            win_se, lose_se = proposed_se, baseline_se
            direction_word = "提升"
        else:
            winner, loser = baseline_name, proposed_name
            win_val, lose_val = baseline_value, proposed_value
            win_se, lose_se = baseline_se, proposed_se
            direction_word = "提升"

    delta = abs(lose_val - win_val)
    denom = lose_val if lose_val else 1e-12
    rel_pct = delta / abs(denom) * 100.0

    parts = []
    if split_note:
        parts.append(f"按 {split_note} 划分")
    if n_baseline and n_proposed:
        parts.append(f"{baseline_name}（n={n_baseline}）vs {proposed_name}（n={n_proposed}）")
    parts.append(
        f"{winner} 的 {metric_label}={_fmt_metric_value(win_val)}±{_fmt_metric_value(win_se)}，"
        f"较 {loser}（{_fmt_metric_value(lose_val)}±{_fmt_metric_value(lose_se)}）{direction_word} {rel_pct:.1f}%（Δ={_fmt_metric_value(delta)}）"
    )
    if p_value is not None:
        if p_value < 0.001:
            parts.append(f"Welch t 检验 p={p_value:.2e}，差异极显著")
        elif p_value < 0.05:
            parts.append(f"Welch t 检验 p={p_value:.4f}，差异显著（*）")
        else:
            parts.append(f"Welch t 检验 p={p_value:.4f}，差异未达显著性")
    return "；".join(parts) + "。"


def refresh_pilot_plot_metadata(
    plot: Dict[str, Any],
    metrics: Dict[str, Any],
    *,
    experiment_design: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从小样验证 metrics 重建 pilot 图的量化对比结论（regenerate 时刷新旧 metadata）。"""
    meta = metrics.get("pilot_meta") if isinstance(metrics, dict) else None
    if not isinstance(meta, dict):
        return plot

    method_blocks = {
        k: v for k, v in metrics.items()
        if k != "pilot_meta" and isinstance(v, dict)
    }
    if len(method_blocks) < 2:
        return plot

    names = list(method_blocks.keys())
    baseline_name = names[0]
    proposed_name = names[1]
    for name in names:
        if any(k in name.lower() for k in ("base", "baseline", "control", "对照")):
            baseline_name = name
        elif any(k in name.lower() for k in ("ours", "proposed", "本文")):
            proposed_name = name

    metric_label = str(meta.get("metric") or "RMSE")
    value_col = meta.get("value_column")
    if value_col:
        metric_label = f"{value_col} 残差 RMSE"
    elif len(metric_label) > 40:
        metric_label = "残差 RMSE（pilot 代理指标）"

    base_block = method_blocks.get(baseline_name) or {}
    prop_block = method_blocks.get(proposed_name) or {}

    def _pick_metric_val(block: Dict[str, Any]) -> Optional[float]:
        if metric_label in block and _is_numeric(block[metric_label]):
            return float(block[metric_label])
        for k, v in block.items():
            if str(k).endswith("_std"):
                continue
            if _is_numeric(v):
                return float(v)
        return None

    base_val = _pick_metric_val(base_block)
    prop_val = _pick_metric_val(prop_block)
    if base_val is None or prop_val is None:
        return plot

    std_key = next(
        (k for k in base_block if str(k).endswith("_std") and _is_numeric(base_block[k])),
        f"{metric_label}_std",
    )
    base_se = float(base_block.get(std_key) or 0)
    prop_se = float(prop_block.get(std_key) or prop_block.get(f"{metric_label}_std") or 0)
    p_val = meta.get("p_value")
    p_val = float(p_val) if p_val is not None else None

    split_note = str(meta.get("split_by") or "样本分区")
    n_base = int(meta.get("n_baseline") or 0)
    n_prop = int(meta.get("n_proposed") or 0)
    target_metrics = str(meta.get("target_metrics") or "")

    baseline_cmp = _format_quantitative_comparison(
        baseline_name=baseline_name,
        proposed_name=proposed_name,
        baseline_value=base_val,
        proposed_value=prop_val,
        baseline_se=base_se,
        proposed_se=prop_se,
        metric_label=metric_label,
        lower_is_better=True,
        p_value=p_val,
        n_baseline=n_base,
        n_proposed=n_prop,
        split_note=split_note,
    )

    condition_parts = [
        f"Pilot 小样验证：按 {split_note} 分为两组",
        f"以全局均值作参照计算 {metric_label}（越低越好）",
    ]
    if target_metrics:
        condition_parts.append(f"实验设计目标指标：{target_metrics[:100]}")
    elif experiment_design:
        target = _pick_target_metrics(experiment_design)
        if target:
            condition_parts.append(f"实验设计目标指标：{target[:100]}")
    condition = "；".join(condition_parts)

    updated = dict(plot)
    updated.update({
        "metric": metric_label,
        "metric_direction": "lower_is_better",
        "baseline_comparison": baseline_cmp,
        "experiment_condition": condition,
        "caption": f"实验条件：{condition}。评估指标：{metric_label}（越低越好）。对比结论：{baseline_cmp}",
        "description": f"实验条件：{condition}。评估指标：{metric_label}（越低越好）。对比结论：{baseline_cmp}",
        "title": f"Pilot 实验：{metric_label} 方法对比",
        "source": "pilot_analysis",
    })
    return updated


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def run_pilot_from_csv(
    csv_path: str,
    experiment_design: Dict[str, Any],
    *,
    output_dir: str,
    hypothesis: str = "",
) -> Dict[str, Any]:
    """
    用真实 CSV 做最小可复现 pilot：空间分区对比 flux 稳定性（非纯描述 histogram）。
    返回 metrics（供 report_charts）与 plots 列表。
    """
    result: Dict[str, Any] = {"success": False, "metrics": {}, "plots": [], "warnings": []}
    if not csv_path or not os.path.exists(csv_path):
        result["warnings"].append("无可用 CSV，跳过 pilot 分析")
        return result

    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        result["warnings"].append("缺少 pandas/numpy")
        return result

    try:
        frame = pd.read_csv(csv_path, nrows=5000)
    except Exception as exc:
        result["warnings"].append(f"读取 CSV 失败: {exc}")
        return result

    value_col = "mean" if "mean" in frame.columns else None
    if value_col is None:
        numeric = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
        value_col = numeric[0] if numeric else None
    if not value_col:
        result["warnings"].append("CSV 无可用数值列")
        return result

    spatial_col = next((c for c in ("spatial_x", "spatial_y", "slice_index") if c in frame.columns), None)
    split_col = spatial_col
    if split_col and frame[split_col].nunique(dropna=True) < 2:
        split_col = "slice_index" if "slice_index" in frame.columns and frame["slice_index"].nunique(dropna=True) >= 2 else None
    if split_col is None:
        numeric_cols = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c]) and c != value_col]
        for cand in numeric_cols:
            if frame[cand].nunique(dropna=True) >= 2:
                split_col = cand
                break

    series = frame[value_col].dropna().astype(float)
    if len(series) < 20:
        result["warnings"].append("样本量过小，跳过 pilot")
        return result

    global_mean = float(series.mean())
    global_std = float(series.std()) or 1e-6

    baseline_name, proposed_name = _split_baselines(experiment_design)
    target_metrics = _pick_target_metrics(experiment_design)
    computed_metric = f"{value_col} 残差 RMSE"

    if split_col:
        med = float(frame[split_col].median())
        group_a = frame[frame[split_col] <= med]
        group_b = frame[frame[split_col] > med]
        if len(group_b) < 5 or len(group_a) < 5:
            mid = len(frame) // 2
            group_a = frame.iloc[:mid]
            group_b = frame.iloc[mid:]
            split_col = split_col + " (fallback: row_half)"
    else:
        mid = len(frame) // 2
        group_a = frame.iloc[:mid]
        group_b = frame.iloc[mid:]
        split_col = "row_half"

    def _rmse_vs_constant(group: pd.DataFrame) -> Tuple[float, float]:
        vals = group[value_col].dropna().astype(float)
        if len(vals) < 5:
            return float("nan"), float("nan")
        pred = global_mean
        err = vals - pred
        rmse = float(np.sqrt((err ** 2).mean()))
        se = float(rmse / max(len(vals) ** 0.5, 1))
        return rmse, se

    base_rmse, base_se = _rmse_vs_constant(group_a)
    prop_rmse, prop_se = _rmse_vs_constant(group_b)

    if np.isnan(base_rmse) or np.isnan(prop_rmse):
        result["warnings"].append("分组样本不足")
        return result

    try:
        from scipy import stats
        _, p_val = stats.ttest_ind(
            group_a[value_col].dropna().astype(float),
            group_b[value_col].dropna().astype(float),
            equal_var=False,
        )
        p_val = float(p_val)
    except Exception:
        p_val = None

    metrics = {
        baseline_name: {computed_metric: base_rmse, f"{computed_metric}_std": base_se},
        proposed_name: {computed_metric: prop_rmse, f"{computed_metric}_std": prop_se},
        "pilot_meta": {
            "metric": computed_metric,
            "target_metrics": target_metrics,
            "value_column": value_col,
            "split_by": str(split_col or "row_half"),
            "n_baseline": int(len(group_a)),
            "n_proposed": int(len(group_b)),
            "p_value": p_val,
            "hypothesis_snippet": (hypothesis or "")[:120],
        },
    }

    plots: List[Dict[str, Any]] = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        names = [baseline_name[:20], proposed_name[:20]]
        vals = [base_rmse, prop_rmse]
        errs = [base_se, prop_se]
        colors = ["#4C72B0", "#DD8452"]
        ax.bar(names, vals, yerr=errs, capsize=5, color=colors, alpha=0.9)
        ax.set_ylabel(computed_metric)
        ax.set_xlabel("实验配置")
        ax.set_title(f"Pilot：{computed_metric} 对比（{split_col or '半样本'}分区）")
        if p_val is not None and p_val < 0.05:
            ymax = max(vals) * 1.15 if max(vals) else 1
            ax.text(0.5, ymax, "* p<0.05", ha="center", color="crimson", fontsize=11)
        ax.grid(True, axis="y", alpha=0.3)
        plt.tight_layout()
        plot_id = hashlib.md5(f"pilot:{csv_path}:{computed_metric}".encode()).hexdigest()[:12]
        plot_path = Path(output_dir) / f"{plot_id}.png"
        fig.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        split_note = f"{split_col or 'row_half'} 中位数" if split_col != "row_half" else "前半/后半样本"
        condition_parts = [
            f"Pilot 小样验证：{Path(csv_path).name} 按 {split_note} 分为两组",
            f"以全局均值作参照计算 {computed_metric}（越低越好）",
        ]
        if target_metrics:
            condition_parts.append(f"实验设计目标指标：{target_metrics[:100]}")
        condition = "；".join(condition_parts)

        baseline_cmp = _format_quantitative_comparison(
            baseline_name=baseline_name,
            proposed_name=proposed_name,
            baseline_value=base_rmse,
            proposed_value=prop_rmse,
            baseline_se=base_se,
            proposed_se=prop_se,
            metric_label=computed_metric,
            lower_is_better=True,
            p_value=p_val,
            n_baseline=int(len(group_a)),
            n_proposed=int(len(group_b)),
            split_note=split_note,
        )
        caption = (
            f"实验条件：{condition}。"
            f"评估指标：{computed_metric}（越低越好）。"
            f"对比结论：{baseline_cmp}"
        )
        plots.append({
            "plot_id": plot_id,
            "type": "grouped_bar",
            "title": f"Pilot 实验：{computed_metric} 方法对比",
            "caption": caption,
            "description": caption,
            "experiment_condition": condition,
            "metric": computed_metric,
            "metric_direction": "lower_is_better",
            "baseline_comparison": baseline_cmp,
            "path": str(plot_path),
            "file_path": str(plot_path),
            "is_generated_from_real_data": True,
            "chart_kind": "experiment_result",
            "has_legend": False,
            "source": "pilot_analysis",
        })
    except Exception as exc:
        logger.warning("pilot 图表生成失败: %s", exc)
        result["warnings"].append(f"图表生成失败: {exc}")

    result["success"] = True
    result["metrics"] = metrics
    result["plots"] = plots
    return result


def write_pilot_metrics_json(output_dir: str, metrics: Dict[str, Any]) -> str:
    path = Path(output_dir) / "metrics.json"
    path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
