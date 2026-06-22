"""实验计划可执行性 Gate — 对照可用数据列与实验设计"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def collect_available_columns(
    data_context: Optional[Dict[str, Any]] = None,
    data_finder_results: Optional[Dict[str, Any]] = None,
) -> Set[str]:
    cols: Set[str] = set()
    ctx = data_context or {}
    df = data_finder_results or ctx.get("data_finder_results") or {}
    merged = df.get("merged") or {}
    for c in merged.get("columns") or []:
        cols.add(_normalize(str(c)))

    for ds in ctx.get("datasets") or []:
        for c in ds.get("columns") or ds.get("column_names") or []:
            cols.add(_normalize(str(c)))
        preview = ds.get("preview") or []
        if preview and isinstance(preview[0], dict):
            for k in preview[0].keys():
                if not str(k).startswith("_"):
                    cols.add(_normalize(str(k)))

    fl_ctx = ctx.get("fl_context") or {}
    for c in fl_ctx.get("detected_fields") or []:
        cols.add(_normalize(str(c)))

    return {c for c in cols if c}


def extract_required_signals(experiment_design: Dict[str, Any]) -> List[str]:
    signals: List[str] = []
    vspec = experiment_design.get("verifiable_hypothesis") or {}
    metric = vspec.get("primary_metric")
    if metric:
        signals.append(str(metric))

    for field in ("datasets", "metrics", "methods", "experimental_steps", "target_data"):
        text = experiment_design.get(field) or ""
        if isinstance(text, str) and text.strip():
            signals.append(text)

    for gap in experiment_design.get("data_gap") or []:
        if gap:
            signals.append(str(gap))

    sc = ((experiment_design.get("skill_outputs") or {}).get("experiment_sanity_check") or {}).get("data") or {}
    for item in (sc.get("missing_items") or sc.get("recommendations") or [])[:5]:
        signals.append(str(item))

    return signals


def infer_required_columns(signals: List[str]) -> List[str]:
    required: List[str] = []
    blob = " ".join(signals).lower()
    patterns = [
        r"\b([a-z][a-z0-9_]{2,})\b",
        r"([a-z_]+(?:_id|_score|_rate|_accuracy|_cost))",
    ]
    stop = {
        "the", "and", "for", "with", "using", "data", "dataset", "model", "train",
        "test", "step", "method", "metric", "result", "analysis", "experiment",
    }
    for pat in patterns:
        for m in re.findall(pat, blob):
            token = _normalize(m)
            if len(token) >= 3 and token not in stop:
                required.append(token)
    return list(dict.fromkeys(required))[:12]


def assess_plan_executability(
    experiment_design: Optional[Dict[str, Any]],
    data_context: Optional[Dict[str, Any]] = None,
    data_finder_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ed = experiment_design or {}
    ctx = data_context or {}
    df = data_finder_results or ctx.get("data_finder_results") or {}

    available = collect_available_columns(ctx, df)
    signals = extract_required_signals(ed)
    inferred = infer_required_columns(signals)

    missing: List[str] = []
    matched: List[str] = []
    for col in inferred:
        if col in available:
            matched.append(col)
        else:
            fuzzy = any(col in a or a in col for a in available)
            if fuzzy:
                matched.append(col)
            else:
                missing.append(col)

    sc = ((ed.get("skill_outputs") or {}).get("experiment_sanity_check") or {}).get("data") or {}
    sanity_executable = sc.get("executable")
    blockers: List[str] = []
    warnings: List[str] = []

    if not available:
        blockers.append("未检测到可用 CSV 列（请上传数据集或运行 Data Finder 合并）")
    if missing:
        warnings.append(f"推断所需列未命中: {', '.join(missing[:5])}")
    if sanity_executable is False:
        for rec in (sc.get("recommendations") or sc.get("missing_items") or [])[:3]:
            blockers.append(f"SanityCheck: {rec}")

    has_data = bool(available) or bool(ctx.get("datasets"))
    has_steps = bool((ed.get("experimental_steps") or "").strip())
    has_metrics = bool((ed.get("metrics") or "").strip()) or bool(
        (ed.get("verifiable_hypothesis") or {}).get("primary_metric")
    )

    score = 40.0
    if has_data:
        score += 25.0
    if has_steps:
        score += 15.0
    if has_metrics:
        score += 10.0
    if matched:
        score += min(10.0, len(matched) * 2.0)
    if blockers:
        score -= min(30.0, len(blockers) * 10.0)
    score = max(0.0, min(100.0, round(score, 1)))

    passed = score >= 60.0 and not blockers and has_steps and has_metrics

    return {
        "passed": passed,
        "score": score,
        "blockers": blockers,
        "warnings": warnings,
        "missing_columns": missing,
        "matched_columns": matched[:8],
        "available_columns_sample": sorted(available)[:12],
        "has_dataset": has_data,
        "sanity_executable": sanity_executable,
    }
