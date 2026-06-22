"""闭环决策记录与跨轮因果摘要"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

CHINA_TZ = timezone(timedelta(hours=8))


def append_closed_loop_decision(
    decisions: List[Dict[str, Any]],
    *,
    trigger: str,
    action: str,
    reason: str,
    actor: str = "auto",
    next_stage: Optional[str] = None,
    round_num: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "trigger": trigger,
        "action": action,
        "reason": reason,
        "actor": actor,
        "next_stage": next_stage,
        "round": round_num,
        "at": datetime.now(CHINA_TZ).isoformat(),
        "metadata": metadata or {},
    }
    decisions.append(entry)
    return entry


def build_iteration_causal_summary(
    snapshot_before: Optional[Dict[str, Any]],
    snapshot_after: Optional[Dict[str, Any]],
    *,
    rollback_meta: Optional[Dict[str, Any]] = None,
    data_finder_before: Optional[Dict[str, Any]] = None,
    data_finder_after: Optional[Dict[str, Any]] = None,
    refinement_notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    before = snapshot_before or {}
    after = snapshot_after or {}
    df_before = data_finder_before or {}
    df_after = data_finder_after or {}
    merged_before = df_before.get("merged") or {}
    merged_after = df_after.get("merged") or {}
    cov_before = df_before.get("coverage_report") or {}
    cov_after = df_after.get("coverage_report") or {}

    rows_before = merged_before.get("row_count") or 0
    rows_after = merged_after.get("row_count") or 0
    tables_before = len(df_before.get("extracted_tables") or [])
    tables_after = len(df_after.get("extracted_tables") or [])

    data_changes: List[str] = []
    if tables_after > tables_before:
        data_changes.append(f"新增 PDF 表格 {tables_after - tables_before} 个")
    if rows_after and rows_after != rows_before:
        data_changes.append(f"合并 CSV 行数 {rows_before}→{rows_after}")
    if cov_after.get("completeness_score") is not None:
        cb = cov_before.get("completeness_score")
        ca = cov_after.get("completeness_score")
        if cb is not None and ca != cb:
            data_changes.append(f"完备性 {cb}→{ca}/100")
        elif cb is None:
            data_changes.append(f"完备性得分 {ca}/100")
    ext_imported = (df_after.get("external_import") or {}).get("imported_count") or 0
    if ext_imported:
        data_changes.append(f"外部数据集入库 {ext_imported} 个")

    plan_changes: List[str] = []
    if before.get("experimental_steps_preview") != after.get("experimental_steps_preview"):
        plan_changes.append("实验步骤已调整")
    if before.get("methods_preview") != after.get("methods_preview"):
        plan_changes.append("研究方法已调整")
    if before.get("hypothesis") != after.get("hypothesis"):
        plan_changes.append("主假设文本已修订")
    fact_delta = (after.get("supporting_fact_count") or 0) - (before.get("supporting_fact_count") or 0)
    if fact_delta > 0:
        plan_changes.append(f"证据 fact +{fact_delta}")

    driven_by = infer_driven_by(rollback_meta, refinement_notes)

    return {
        "data_changes": data_changes,
        "plan_changes": plan_changes,
        "driven_by": driven_by,
        "summary": _format_causal_summary(data_changes, plan_changes, driven_by),
    }


def infer_driven_by(
    rollback_meta: Optional[Dict[str, Any]] = None,
    refinement_notes: Optional[List[str]] = None,
) -> str:
    meta = rollback_meta or {}
    lit = meta.get("literature_refresh") or {}
    if lit.get("data_finder_rerun"):
        if lit.get("new_facts"):
            return "validation_feedback+literature_refresh+data_finder"
        return "validation_feedback+data_finder"
    if lit.get("new_facts"):
        return "literature_refresh"
    notes = " ".join(refinement_notes or []).lower()
    if "human" in notes or "人工" in notes:
        return "human_feedback"
    if refinement_notes:
        return "validation_feedback"
    return "ensemble_review"


def _format_causal_summary(
    data_changes: List[str],
    plan_changes: List[str],
    driven_by: str,
) -> str:
    parts: List[str] = [f"驱动: {driven_by}"]
    if data_changes:
        parts.append("数据: " + "；".join(data_changes[:3]))
    if plan_changes:
        parts.append("计划: " + "；".join(plan_changes[:3]))
    return " · ".join(parts)
