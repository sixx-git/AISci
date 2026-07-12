"""从实验设计 / 小样验证 / 沙箱产出生成论文级实验图表（非原始数据描述统计）。
报告 regenerate 时强制刷新，不保留 FITS/CSV 均值直方图类描述图。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_public_charts_dir() -> Path:
    """Web 可访问的图表目录 backend/storage/charts（对应 URL /storage/charts/）。"""
    root = Path(__file__).resolve().parents[2] / "storage" / "charts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sync_plot_to_public_dir(plot: Dict[str, Any]) -> Dict[str, Any]:
    """将图表文件复制到公共 charts 目录，并填充 url / base64。"""
    enriched = dict(plot)
    plot_id = str(enriched.get("plot_id") or "").strip()
    src = enriched.get("path") or enriched.get("file_path") or ""
    if not src:
        return enriched

    src_path = Path(str(src))
    if not src_path.exists():
        return enriched

    target_name = f"{plot_id}.png" if plot_id else src_path.name
    target = get_public_charts_dir() / target_name
    try:
        if src_path.resolve() != target.resolve():
            shutil.copy2(src_path, target)
        enriched["path"] = str(target)
        enriched["file_path"] = str(target)
        enriched["url"] = f"/storage/charts/{target.name}"
        enriched["base64"] = base64.b64encode(target.read_bytes()).decode("ascii")
    except OSError as exc:
        logger.warning("同步图表到公共目录失败: %s", exc)
    return enriched

_METRIC_KEYWORDS = (
    "accuracy", "f1", "precision", "recall", "rmse", "mae", "r2", "auc",
    "latency", "memory", "loss", "error", "score", "lyapunov", "stability",
    "准确率", "精确率", "召回率", "误差", "延迟", "内存",
)
_HIGHER_IS_BETTER = frozenset({
    "accuracy", "f1", "precision", "recall", "r2", "auc", "score",
    "准确率", "精确率", "召回率",
})
_LOWER_IS_BETTER = frozenset({
    "rmse", "mae", "loss", "error", "latency", "memory", "lyapunov",
    "误差", "延迟", "内存",
})


def _metric_direction(name: str) -> str:
    key = name.lower()
    if any(k in key for k in _LOWER_IS_BETTER):
        return "lower_is_better"
    if any(k in key for k in _HIGHER_IS_BETTER):
        return "higher_is_better"
    return "context_dependent"


def _direction_label(direction: str) -> str:
    if direction == "lower_is_better":
        return "越低越好"
    if direction == "higher_is_better":
        return "越高越好"
    return "方向依指标定义"


def build_figure_caption(
    *,
    experiment_condition: str = "",
    metric: str = "",
    metric_direction: str = "context_dependent",
    baseline_comparison: str = "",
    dataset: str = "",
    axis_note: str = "",
) -> str:
    """构建符合论文图注要求的多句 caption。"""
    parts: List[str] = []
    if experiment_condition:
        parts.append(f"实验条件：{experiment_condition}")
    if metric:
        parts.append(f"评估指标：{metric}（{_direction_label(metric_direction)}）")
    if baseline_comparison:
        parts.append(f"对比结论：{baseline_comparison}")
    if dataset:
        parts.append(f"数据集：{dataset}")
    if axis_note:
        parts.append(axis_note)
    if not parts:
        return ""
    return "。".join(parts) + "。"


def _split_text_items(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    if ";" in text:
        return [p.strip() for p in text.split(";") if p.strip()]
    if "；" in text:
        return [p.strip() for p in text.split("；") if p.strip()]
    if "\n" in text:
        return [p.strip() for p in text.splitlines() if p.strip()]
    return [text]


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


def _looks_like_metric_key(key: str) -> bool:
    k = key.lower()
    if k.endswith("_std") or k.endswith("_err") or k.endswith("_se"):
        return False
    return any(m in k for m in _METRIC_KEYWORDS)


def _parse_std_key(base_key: str, metrics: Dict[str, Any]) -> Optional[float]:
    for suffix in ("_std", "_err", "_se", "_stderr"):
        v = metrics.get(f"{base_key}{suffix}")
        if v is None:
            v = metrics.get(f"{base_key}{suffix.upper()}")
        if _is_numeric(v):
            return float(v)
    return None


def _collect_metrics_dict(small_validation: Dict[str, Any]) -> Dict[str, Any]:
    sv = small_validation or {}
    candidates: List[Dict[str, Any]] = []
    sb = sv.get("sandbox_execution") or {}
    if isinstance(sb.get("metrics"), dict):
        candidates.append(sb["metrics"])
    artifacts = sv.get("artifacts") or {}
    if isinstance(artifacts.get("metrics"), dict):
        candidates.append(artifacts["metrics"])
    actual = (sv.get("results") or {}).get("actual_results") or {}
    if isinstance(actual.get("sandbox_metrics"), dict):
        candidates.append(actual["sandbox_metrics"])
    modeling = actual.get("modeling_result") or {}
    if isinstance(modeling.get("metrics"), dict):
        candidates.append(modeling["metrics"])
    for mr in actual.get("modeling_results") or []:
        if isinstance(mr, dict) and isinstance(mr.get("metrics"), dict):
            candidates.append(mr["metrics"])
    merged: Dict[str, Any] = {}
    for block in candidates:
        merged.update(block)
    return merged


def _extract_method_metric_comparisons(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 metrics 字典解析「方法 × 指标」对比组。"""
    if not metrics:
        return []

    comparisons: List[Dict[str, Any]] = []

    # 嵌套：{"baseline": {"accuracy": 0.8}, "ours": {"accuracy": 0.9}}
    nested_methods = {
        k: v for k, v in metrics.items()
        if isinstance(v, dict) and any(_is_numeric(x) for x in v.values())
    }
    if len(nested_methods) >= 2:
        metric_names = sorted({
            mk for mv in nested_methods.values()
            for mk, val in mv.items()
            if _is_numeric(val) and _looks_like_metric_key(str(mk))
        })
        for metric_name in metric_names[:4]:
            series = []
            for method_name, method_vals in nested_methods.items():
                if metric_name not in method_vals:
                    continue
                err = _parse_std_key(str(metric_name), method_vals)
                series.append({
                    "name": str(method_name),
                    "values": [{"x": str(metric_name), "y": float(method_vals[metric_name]), "err": err}],
                })
            if len(series) >= 2:
                comparisons.append({"metric": str(metric_name), "series": series})
        if comparisons:
            return comparisons

    # 扁平：baseline_accuracy / proposed_accuracy
    flat: Dict[str, Dict[str, float]] = {}
    flat_err: Dict[str, Dict[str, Optional[float]]] = {}
    for key, val in metrics.items():
        if not _is_numeric(val):
            continue
        key_str = str(key)
        if not _looks_like_metric_key(key_str):
            continue
        parts = re.split(r"[_\-/]", key_str.lower())
        method_hint = ""
        metric_hint = key_str
        for prefix in ("baseline", "base", "ours", "proposed", "method", "ablation"):
            if prefix in parts:
                method_hint = prefix
                break
        if not method_hint:
            for token in parts:
                if token in ("baseline", "base", "ours", "proposed", "ablation", "control"):
                    method_hint = token
                    break
        if not method_hint:
            method_hint = "result"
        flat.setdefault(metric_hint, {})[method_hint] = float(val)
        flat_err.setdefault(metric_hint, {})[method_hint] = _parse_std_key(key_str, metrics)

    for metric_name, method_map in flat.items():
        if len(method_map) < 2:
            continue
        series = [
            {
                "name": method,
                "values": [{"x": metric_name, "y": y, "err": flat_err.get(metric_name, {}).get(method)}],
            }
            for method, y in method_map.items()
        ]
        comparisons.append({"metric": metric_name, "series": series})

    # 列表：[{"method": "...", "metric": "...", "value": ..., "std": ...}]
    if isinstance(metrics.get("comparisons"), list):
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in metrics["comparisons"]:
            if not isinstance(row, dict):
                continue
            m_name = str(row.get("metric") or row.get("metric_name") or "metric")
            grouped.setdefault(m_name, []).append(row)
        for metric_name, rows in grouped.items():
            series = []
            for row in rows:
                val = row.get("value", row.get("y"))
                if not _is_numeric(val):
                    continue
                err = row.get("std", row.get("err", row.get("se")))
                series.append({
                    "name": str(row.get("method") or row.get("name") or "method"),
                    "values": [{"x": metric_name, "y": float(val), "err": float(err) if _is_numeric(err) else None}],
                })
            if len(series) >= 2:
                comparisons.append({"metric": metric_name, "series": series})

    return comparisons


def _sv_has_experiment_output(sv: Dict[str, Any]) -> bool:
    if not sv:
        return False
    sb = sv.get("sandbox_execution") or {}
    if sb.get("success"):
        return True
    arts = sv.get("artifacts") or {}
    if arts.get("plots") or arts.get("metrics"):
        return True
    actual = (sv.get("results") or {}).get("actual_results") or {}
    return bool(actual.get("sandbox_plots") or actual.get("sandbox_metrics"))


def _load_small_validation_from_disk(project_id: str, db: Any) -> Dict[str, Any]:
    """DB 阶段输出被截断时，从 validations / runs 磁盘产物回填沙箱结果。"""
    from pathlib import Path

    from app.models.pipeline import PipelineRun

    backend_root = Path(__file__).resolve().parent.parent.parent
    runs_root = backend_root / "storage" / "runs"
    val_root = backend_root / "storage" / "validations"

    run_ids = [
        r.run_id
        for r in db.query(PipelineRun)
        .filter(PipelineRun.project_id == project_id)
        .order_by(PipelineRun.created_at.desc())
        .limit(20)
        .all()
        if r.run_id
    ]

    candidates: List[tuple[float, Dict[str, Any]]] = []

    def _score(sv: Dict[str, Any]) -> float:
        sb = sv.get("sandbox_execution") or {}
        if not sb.get("success"):
            return 0.0
        plots = len(sb.get("plots") or []) + len((sv.get("artifacts") or {}).get("plots") or [])
        metrics = 1.0 if isinstance(sb.get("metrics"), dict) and sb.get("metrics") else 0.0
        return plots * 10 + metrics + (2.0 if sb.get("output_complete") else 0.0)

    for run_id in run_ids:
        link_path = runs_root / run_id / "latest_validation.json"
        if not link_path.is_file():
            continue
        try:
            with open(link_path, encoding="utf-8") as f:
                link = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        vid = link.get("validation_id")
        val_path = val_root / vid / "result.json" if vid else None
        if not val_path or not val_path.is_file():
            continue
        try:
            with open(val_path, encoding="utf-8") as f:
                sv = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(sv, dict) and _sv_has_experiment_output(sv):
            candidates.append((val_path.stat().st_mtime, sv))

    if not candidates:
        if val_root.is_dir():
            for child in val_root.iterdir():
                result_path = child / "result.json"
                if not result_path.is_file():
                    continue
                try:
                    with open(result_path, encoding="utf-8") as f:
                        sv = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(sv, dict) or not _sv_has_experiment_output(sv):
                    continue
                blob = json.dumps(sv, ensure_ascii=False)
                if project_id not in blob and "HEPAR" not in blob:
                    continue
                candidates.append((result_path.stat().st_mtime, sv))

    if not candidates:
        return {}

    candidates.sort(key=lambda x: (_score(x[1]), x[0]), reverse=True)
    return candidates[0][1]


def load_experiment_context(db: Any, project_id: str) -> Dict[str, Any]:
    """加载 Pipeline 实验设计、小样验证与假设上下文。"""
    from app.models.pipeline import PipelineRun, PipelineStage, PipelineStageExecution, PipelineStatus
    from app.services._utils.pipeline_queries import get_stage_output
    from app.services.report_compliance_service import experiment_design_record_to_dict

    ctx: Dict[str, Any] = {
        "experiment_design": {},
        "small_validation": {},
        "hypothesis": "",
        "methods": "",
        "datasets": "",
        "baselines": [],
        "metrics": [],
    }

    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.project_id == project_id)
        .order_by(PipelineRun.created_at.desc())
        .limit(12)
        .all()
    )

    best_sv: Dict[str, Any] = {}
    ed_data: Dict[str, Any] = {}
    hg_data: Dict[str, Any] = {}

    for run in runs:
        if not ed_data:
            ed = get_stage_output(db, run.id, PipelineStage.EXPERIMENT_DESIGN)
            if isinstance(ed, dict) and ed:
                ed_data = experiment_design_record_to_dict(ed)
        if not hg_data:
            hg = get_stage_output(db, run.id, PipelineStage.HYPOTHESIS_GENERATION)
            if isinstance(hg, dict) and hg:
                hg_data = hg
        if not best_sv or not _sv_has_experiment_output(best_sv):
            sv = get_stage_output(db, run.id, PipelineStage.SMALL_VALIDATION)
            if isinstance(sv, dict) and _sv_has_experiment_output(sv):
                best_sv = sv
            elif isinstance(sv, dict) and sv.get("analysis_script") and not best_sv:
                best_sv = sv

        stage_row = (
            db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == run.id,
                PipelineStageExecution.stage == PipelineStage.SMALL_VALIDATION,
                PipelineStageExecution.status == PipelineStatus.COMPLETED,
            )
            .first()
        )
        if stage_row and isinstance(stage_row.output_data, dict):
            od = stage_row.output_data
            if od.get("_truncated") and not _sv_has_experiment_output(od):
                continue
            if _sv_has_experiment_output(od):
                best_sv = od
                break

    if not _sv_has_experiment_output(best_sv):
        disk_sv = _load_small_validation_from_disk(project_id, db)
        if disk_sv:
            best_sv = disk_sv

    ctx["experiment_design"] = ed_data
    ctx["small_validation"] = best_sv
    if hg_data:
        reviews = hg_data.get("reviews") or []
        if reviews and isinstance(reviews[0], dict):
            ctx["hypothesis"] = str(reviews[0].get("hypothesis") or reviews[0].get("content") or "")

    ed = ctx["experiment_design"]
    ctx["methods"] = str(ed.get("methods") or "")
    ctx["datasets"] = str(ed.get("datasets") or ed.get("source_data") or "")
    ctx["baselines"] = _split_text_items(ed.get("baselines"))
    ctx["metrics"] = _split_text_items(ed.get("metrics"))
    return ctx


def _default_experiment_condition(ctx: Dict[str, Any]) -> str:
    parts = []
    if ctx.get("methods"):
        parts.append(ctx["methods"][:120])
    baselines = ctx.get("baselines") or []
    if baselines:
        parts.append("基线：" + "；".join(baselines[:3]))
    datasets = ctx.get("datasets") or ""
    if datasets:
        parts.append(f"数据：{datasets[:80]}")
    return "；".join(parts) if parts else "小样验证 / 沙箱实验"


def _infer_baseline_comparison(series: List[Dict[str, Any]], metric: str) -> str:
    if len(series) < 2:
        return ""
    direction = _metric_direction(metric)
    lower_is_better = direction == "lower_is_better"

    entries: List[Dict[str, Any]] = []
    for s in series:
        name = str(s.get("name", ""))
        vals = s.get("values") or []
        if not vals:
            continue
        y = float(vals[0].get("y", 0))
        err_raw = vals[0].get("err")
        err = float(err_raw) if err_raw is not None else 0.0
        entries.append({"name": name, "y": y, "err": err})

    if len(entries) < 2:
        return ""

    baseline_entry = next(
        (e for e in entries if any(k in e["name"].lower() for k in ("base", "baseline", "control", "对照"))),
        entries[0],
    )
    proposed_entry = next(
        (e for e in entries if e is not baseline_entry and any(
            k in e["name"].lower() for k in ("ours", "proposed", "method", "本文")
        )),
        entries[1] if entries[1] is not baseline_entry else entries[0],
    )

    base_val, prop_val = baseline_entry["y"], proposed_entry["y"]
    base_err, prop_err = baseline_entry["err"], proposed_entry["err"]
    base_name, prop_name = baseline_entry["name"], proposed_entry["name"]

    if lower_is_better:
        if prop_val <= base_val:
            winner, loser = prop_name, base_name
            win_val, lose_val = prop_val, base_val
            win_err, lose_err = prop_err, base_err
            direction_word = "降低"
        else:
            winner, loser = base_name, prop_name
            win_val, lose_val = base_val, prop_val
            win_err, lose_err = base_err, prop_err
            direction_word = "降低"
    else:
        if prop_val >= base_val:
            winner, loser = prop_name, base_name
            win_val, lose_val = prop_val, base_val
            win_err, lose_err = prop_err, base_err
            direction_word = "提升"
        else:
            winner, loser = base_name, prop_name
            win_val, lose_val = base_val, prop_val
            win_err, lose_err = base_err, prop_err
            direction_word = "提升"

    delta = abs(lose_val - win_val)
    denom = lose_val if lose_val else 1e-12
    rel_pct = delta / abs(denom) * 100.0
    return (
        f"{winner} 的 {metric}={win_val:.4f}±{win_err:.4f}，"
        f"较 {loser}（{lose_val:.4f}±{lose_err:.4f}）{direction_word} {rel_pct:.1f}%（Δ={delta:.4f}）。"
    )


def build_experiment_plot_specs(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """基于小样验证 metrics 构建方法对比图规格（非原始 CSV 描述统计）。"""
    sv = ctx.get("small_validation") or {}
    metrics = _collect_metrics_dict(sv)
    comparisons = _extract_method_metric_comparisons(metrics)
    if not comparisons:
        return []

    condition = _default_experiment_condition(ctx)
    dataset_label = ctx.get("datasets") or ""
    specs: List[Dict[str, Any]] = []

    for comp in comparisons[:4]:
        metric = str(comp.get("metric") or "metric")
        series = comp.get("series") or []
        if len(series) < 2:
            continue
        direction = _metric_direction(metric)
        baseline_cmp = _infer_baseline_comparison(series, metric)
        caption = build_figure_caption(
            experiment_condition=condition,
            metric=metric,
            metric_direction=direction,
            baseline_comparison=baseline_cmp,
            dataset=dataset_label,
            axis_note="误差棒表示标准差（若适用）；* 表示 p<0.05。",
        )
        plot_id = hashlib.md5(f"exp_bar:{metric}:{len(series)}".encode()).hexdigest()[:12]
        specs.append({
            "plot_id": plot_id,
            "type": "grouped_bar",
            "title": f"方法对比：{metric}",
            "description": caption,
            "caption": caption,
            "experiment_condition": condition,
            "metric": metric,
            "metric_direction": direction,
            "baseline_comparison": baseline_cmp,
            "x_label": "实验配置 / 方法",
            "y_label": metric,
            "series": series,
            "has_legend": True,
            "source_dataset_id": "experiment_metrics",
            "is_generated_from_real_data": True,
            "chart_kind": "experiment_result",
        })
    return specs


def _enrich_sandbox_plot(plot: Dict[str, Any], ctx: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    enriched = dict(plot)
    sv = ctx.get("small_validation") or {}
    metrics = _collect_metrics_dict(sv)

    from app.services.experiment_pilot_analysis_service import refresh_pilot_plot_metadata

    if metrics.get("pilot_meta") or enriched.get("source") == "pilot_analysis":
        enriched = refresh_pilot_plot_metadata(
            enriched,
            metrics,
            experiment_design=ctx.get("experiment_design") or {},
        )

    is_pilot = enriched.get("source") == "pilot_analysis"
    has_rich_comparison = bool(enriched.get("baseline_comparison")) and (
        "±" in str(enriched["baseline_comparison"])
        or "Δ=" in str(enriched["baseline_comparison"])
        or "p=" in str(enriched["baseline_comparison"])
    )

    if not is_pilot and not has_rich_comparison:
        condition = _default_experiment_condition(ctx)
        metrics_list = ctx.get("metrics") or []
        metric_text = "；".join(metrics_list[:3]) if metrics_list else "见坐标轴"
        caption = build_figure_caption(
            experiment_condition=condition,
            metric=metric_text,
            metric_direction="context_dependent",
            baseline_comparison="由沙箱分析脚本产出，详见图例与坐标轴",
            dataset=ctx.get("datasets") or "",
            axis_note="坐标轴含义与单位见图中标注；图例区分不同实验条件。",
        )
        enriched.setdefault("caption", caption)
        enriched.setdefault("description", caption)
        enriched.setdefault("experiment_condition", condition)
        enriched.setdefault("metric", metric_text)
        enriched.setdefault("chart_kind", "experiment_result")
        enriched.setdefault("is_generated_from_real_data", True)
        enriched.setdefault("source", "sandbox_execution")

    del output_dir  # 统一写入 get_public_charts_dir()
    return _sync_plot_to_public_dir(enriched)


def collect_sandbox_plots(ctx: Dict[str, Any], output_dir: str) -> List[Dict[str, Any]]:
    """收集并规范化沙箱产出图表。"""
    sv = ctx.get("small_validation") or {}
    plots: List[Dict[str, Any]] = []
    seen: set = set()

    def _add(raw: Dict[str, Any]) -> None:
        pid = raw.get("plot_id") or raw.get("title")
        if not pid or pid in seen:
            return
        seen.add(pid)
        plots.append(_enrich_sandbox_plot(raw, ctx, output_dir))

    for source in (
        (sv.get("artifacts") or {}).get("plots") or [],
        ((sv.get("results") or {}).get("actual_results") or {}).get("sandbox_plots") or [],
        sv.get("charts") or [],
    ):
        for p in source:
            if isinstance(p, dict):
                _add(p)
    return plots


def generate_report_plots_from_project(
    project_id: str,
    db: Any,
    output_dir: str,
    *,
    row_limit: int = 400,
) -> List[Dict[str, Any]]:
    """从实验上下文生成论文级实验图表；无实验产出时不生成描述性统计图。"""
    del row_limit  # 不再基于 merged CSV 做 slice/mean 描述图

    ctx = load_experiment_context(db, project_id)
    public_dir = get_public_charts_dir()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    charts: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for sandbox_plot in collect_sandbox_plots(ctx, str(public_dir)):
        pid = sandbox_plot.get("plot_id")
        if pid and pid not in seen_ids:
            charts.append(sandbox_plot)
            seen_ids.add(pid)

    plot_specs = build_experiment_plot_specs(ctx)
    if plot_specs:
        async def _run() -> List[Dict[str, Any]]:
            from app.skills.report.report_chart_generation_skill import ReportChartGenerationSkill

            skill = ReportChartGenerationSkill()
            result = await skill.run(
                input_data={
                    "plot_specs": plot_specs,
                    "data": [{"_placeholder": True}],
                    "output_dir": str(public_dir),
                    "format": "both",
                    "dpi": 150,
                    "figure_size": (10, 6),
                },
                context={"stage": "report_regenerate"},
            )
            return list(result.data.get("charts") or [])

        try:
            from app.core.async_utils import run_coroutine_sync
            generated = run_coroutine_sync(_run())
            for ch in generated:
                pid = ch.get("plot_id")
                if pid and pid not in seen_ids:
                    charts.append(_sync_plot_to_public_dir(ch))
                    seen_ids.add(pid)
        except Exception as exc:
            logger.warning("实验对比图生成失败: %s", exc)

    logger.info("项目 %s 生成实验图表 %d 张", project_id, len(charts))
    return charts
