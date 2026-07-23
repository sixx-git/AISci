"""迭代质量模式：draft（宽松）/ strict（严格）。"""
from __future__ import annotations

from typing import Any, Optional


PASSABLE_DRAFT = frozenset({"needs_adjustment", "promising", "success"})
PASSABLE_STRICT = frozenset({"success", "promising"})
BLOCKING = frozenset({"significant_issue"})


def normalize_quality_mode(mode: Optional[str]) -> str:
    m = (mode or "draft").strip().lower()
    if m in {"strict", "rigorous", "hard"}:
        return "strict"
    return "draft"


def round_has_charts(result: Any) -> bool:
    """从 IterationResult / dict 判断是否产出图表。"""
    if result is None:
        return False
    raw = getattr(result, "raw_output", None)
    if raw is None and isinstance(result, dict):
        raw = result.get("raw_output") or result
    if isinstance(raw, dict):
        charts = raw.get("chart_paths") or raw.get("charts") or []
        if charts:
            return True
    charts2 = getattr(result, "charts", None)
    if charts2 is None and isinstance(result, dict):
        charts2 = result.get("charts")
    return bool(charts2)


def is_round_acceptable(
    *,
    quality_mode: str,
    execution_status: str,
    overall_assessment: str,
    has_charts: bool,
) -> bool:
    """
    草稿模式：执行成功 + 有图 + 评估非 significant_issue → 予以通过（含 needs_adjustment）。
    严格模式：执行成功 + 有图 + 评估为 success/promising。
    """
    mode = normalize_quality_mode(quality_mode)
    status = (execution_status or "").lower()
    assessment = (overall_assessment or "").strip().lower()
    if status not in {"success", "ok", "completed"}:
        return False
    if not has_charts:
        return False
    if assessment in BLOCKING or assessment == "":
        # 空评估在草稿下若有图可视为 needs_adjustment 级通过
        if mode == "draft" and not assessment and has_charts:
            return True
        if assessment in BLOCKING:
            return False
    if mode == "draft":
        return assessment in PASSABLE_DRAFT or (not assessment and has_charts)
    return assessment in PASSABLE_STRICT


def apply_quality_mode_to_decision(
    *,
    quality_mode: str,
    analysis: Any,
    decision: Any,
    result: Any,
) -> Any:
    """按质量模式改写 IterationDecision（是否继续迭代）。"""
    mode = normalize_quality_mode(quality_mode)
    assessment = str(getattr(analysis, "overall_assessment", "") or "").strip().lower()
    status = str(getattr(result, "status", "") or "").lower()
    has_charts = round_has_charts(result)
    acceptable = is_round_acceptable(
        quality_mode=mode,
        execution_status=status,
        overall_assessment=assessment,
        has_charts=has_charts,
    )

    # 显著问题：必须继续迭代
    if assessment in BLOCKING or (status == "success" and not has_charts):
        decision.should_continue = True
        if not has_charts and status == "success":
            notes = list(getattr(decision, "next_plan_adjustments", None) or [])
            notes.append("本轮未产出图表，草稿/严格模式均要求至少 1 张图，需继续迭代。")
            decision.next_plan_adjustments = notes
        return decision

    if mode == "draft" and acceptable:
        # 需调整也予以通过：可停止，报告侧阐明优劣
        decision.should_continue = False
        notes = list(getattr(decision, "next_plan_adjustments", None) or [])
        if assessment == "needs_adjustment":
            notes.append(
                "草稿模式：本轮结果「需调整」已予以通过；报告中应写明优点与局限，无需仅为完美度继续空转。"
            )
        decision.next_plan_adjustments = notes
        return decision

    if mode == "strict" and not acceptable and status == "success":
        # 严格：needs_adjustment 也要继续
        decision.should_continue = True
        notes = list(getattr(decision, "next_plan_adjustments", None) or [])
        notes.append("严格模式：当前评估未达 promising/success，需继续迭代优化。")
        decision.next_plan_adjustments = notes
    return decision
