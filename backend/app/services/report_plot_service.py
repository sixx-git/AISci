"""报告实验图表：去重、公共目录同步、持久化瘦身与按需读取。"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PLACEHOLDER_METRIC_NOTES = frozenset({"no metrics emitted", "no metrics", ""})


def is_sandbox_metrics_placeholder(metrics: Any) -> bool:
    if not isinstance(metrics, dict) or not metrics:
        return True
    if len(metrics) == 1 and "stdout_preview" in metrics:
        return True
    substantive_keys = [k for k in metrics if k not in ("note", "stdout_preview")]
    if substantive_keys:
        return False
    note = str(metrics.get("note") or "").strip().lower()
    return note in _PLACEHOLDER_METRIC_NOTES or "note" in metrics


def is_sandbox_output_complete(metrics: Any, plots: Any) -> bool:
    if isinstance(plots, list) and plots:
        return True
    return not is_sandbox_metrics_placeholder(metrics)


def get_public_charts_dir() -> Path:
    root = Path(__file__).resolve().parents[2] / "storage" / "charts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _plot_dedupe_key(plot: Dict[str, Any]) -> str:
    pid = str(plot.get("plot_id") or "").strip()
    if pid:
        return f"id:{pid}"
    title = str(plot.get("title") or "").strip().lower()
    chart_type = str(plot.get("type") or plot.get("chart_type") or "").strip().lower()
    if title:
        return f"title:{title}|{chart_type}"
    return f"hash:{hashlib.md5(str(plot).encode()).hexdigest()[:12]}"


def dedupe_report_plots(plots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 plot_id / 标题去重，沙箱与 pilot 图优先于描述性统计图。"""
    if not plots:
        return []

    def _priority(p: Dict[str, Any]) -> int:
        source = str(p.get("source") or "").lower()
        kind = str(p.get("chart_kind") or "").lower()
        if source in ("sandbox_execution", "pilot_analysis") or p.get("type") == "sandbox_plot":
            return 0
        if kind == "experiment_result":
            return 1
        if kind == "descriptive_stat":
            return 3
        return 2

    ranked = sorted(
        [p for p in plots if isinstance(p, dict)],
        key=lambda p: (_priority(p), str(p.get("title") or "")),
    )
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for plot in ranked:
        key = _plot_dedupe_key(plot)
        if key in seen:
            continue
        seen.add(key)
        out.append(plot)
    return out


def sync_plot_to_public_storage(
    plot: Dict[str, Any],
    *,
    report_file_id: Optional[str] = None,
) -> Dict[str, Any]:
    """将图表文件复制到 storage/charts，并填充 url（保留 base64 可选）。"""
    enriched = dict(plot)
    plot_id = str(enriched.get("plot_id") or "").strip()
    if not plot_id:
        plot_id = hashlib.md5(str(plot.get("title") or "plot").encode()).hexdigest()[:12]
        enriched["plot_id"] = plot_id

    public_dir = get_public_charts_dir()
    target = public_dir / f"{plot_id}.png"

    src_candidates = [
        enriched.get("path"),
        enriched.get("file_path"),
        enriched.get("image_path"),
    ]
    # 迭代实验相对路径（如 smoke/xxx.png）相对 shaxiang data/charts
    try:
        from app.integrations.shaxiang.bridge import shaxiang_root

        charts_root = shaxiang_root() / "data" / "charts"
    except Exception:
        charts_root = None

    copied = False
    for src in src_candidates:
        if not src:
            continue
        candidates = [Path(str(src))]
        if charts_root is not None and not Path(str(src)).is_absolute():
            candidates.append((charts_root / str(src)).resolve())
            candidates.append((charts_root / Path(str(src)).name).resolve())
        for src_path in candidates:
            if not src_path.is_file():
                continue
            try:
                if src_path.resolve() != target.resolve():
                    shutil.copy2(src_path, target)
                copied = True
                break
            except OSError as exc:
                logger.warning("复制图表失败 %s -> %s: %s", src_path, target, exc)
        if copied:
            break

    if not copied and not target.is_file() and enriched.get("base64"):
        try:
            target.write_bytes(base64.b64decode(str(enriched["base64"])))
            copied = True
        except Exception as exc:
            logger.warning("从 base64 写入图表失败 plot_id=%s: %s", plot_id, exc)

    if target.is_file():
        enriched["file_path"] = str(target)
        enriched["path"] = str(target)
        enriched["url"] = f"/storage/charts/{target.name}"
        if report_file_id:
            enriched["report_file_id"] = report_file_id
        try:
            enriched["base64"] = base64.b64encode(target.read_bytes()).decode("ascii")
        except OSError:
            pass

    return enriched


def slim_plot_for_db(plot: Dict[str, Any]) -> Dict[str, Any]:
    """DB / API 列表用：去掉 base64，保留 url 与元数据。"""
    if not isinstance(plot, dict):
        return {}
    slim = {
        k: plot.get(k)
        for k in (
            "plot_id",
            "type",
            "chart_type",
            "title",
            "description",
            "caption",
            "experiment_condition",
            "metric",
            "metric_direction",
            "baseline_comparison",
            "x_label",
            "y_label",
            "has_legend",
            "chart_kind",
            "url",
            "file_path",
            "path",
            "source",
            "source_dataset_id",
            "is_generated_from_real_data",
        )
        if plot.get(k) is not None
    }
    if plot.get("base64") and not slim.get("url"):
        slim["has_image"] = True
    return slim


def prepare_plots_for_persistence(
    plots: List[Dict[str, Any]],
    *,
    report_file_id: Optional[str] = None,
    keep_base64: bool = False,
) -> List[Dict[str, Any]]:
    """同步公共目录并瘦身，供 Report.extra_metadata 存储。"""
    synced = [
        sync_plot_to_public_storage(p, report_file_id=report_file_id)
        for p in dedupe_report_plots(plots)
        if isinstance(p, dict)
    ]
    if keep_base64:
        return synced
    return [slim_plot_for_db(p) for p in synced]


def resolve_plot_image_path(
    extra_metadata: Dict[str, Any],
    plot_id: str,
    *,
    report_file_id: Optional[str] = None,
) -> Optional[Path]:
    plots = extra_metadata.get("plots") or []
    if not isinstance(plots, list):
        return None

    target_plot: Optional[Dict[str, Any]] = None
    for p in plots:
        if isinstance(p, dict) and str(p.get("plot_id") or "") == plot_id:
            target_plot = p
            break
    if not target_plot:
        return None

    for key in ("file_path", "path", "url"):
        raw = target_plot.get(key)
        if not raw:
            continue
        text = str(raw)
        if text.startswith("/storage/charts/"):
            candidate = get_public_charts_dir() / Path(text).name
            if candidate.is_file():
                return candidate
        candidate = Path(text)
        if candidate.is_file():
            return candidate

    fallback = get_public_charts_dir() / f"{plot_id}.png"
    if fallback.is_file():
        return fallback

    if report_file_id:
        report_chart = (
            Path(__file__).resolve().parents[2]
            / "storage"
            / "reports"
            / report_file_id
            / "charts"
            / f"{plot_id}.png"
        )
        if report_chart.is_file():
            return report_chart
    return None


def collect_sandbox_plots_from_validation(small_validation: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(small_validation, dict):
        return []
    plots = (small_validation.get("artifacts") or {}).get("plots") or []
    if not plots:
        actual = (small_validation.get("results") or {}).get("actual_results") or {}
        plots = actual.get("sandbox_plots") or []
    return [dict(p) for p in plots if isinstance(p, dict)]
