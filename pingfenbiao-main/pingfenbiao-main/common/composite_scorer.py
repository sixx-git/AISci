"""
组合评分模块 — 将内容质量评分与影响力评估合并为综合评级。

评分体系（百分制）：
  - 内容质量分（50%）：三种评分表中最高一项的百分比
  - 影响力评估分（50%）：影响力评估百分比（impact_score / 30 × 100）

评级标准（百分制）：
  S (90%+): 领域顶尖
  A (75-89%): 高水平研究
  A- (65-74%): 优良研究
  B (55-64%): 合格研究，有亮点
  C (45-54%): 基础水平
  D (<45%): 需要大幅改进
"""

from __future__ import annotations

from typing import Any

# 评级阈值（基于百分比）
RATING_THRESHOLDS = [
    (90, "S", "领域顶尖"),
    (75, "A", "高水平研究"),
    (65, "A-", "优良研究"),
    (55, "B", "合格研究，有亮点"),
    (45, "C", "基础水平"),
    (0, "D", "需要大幅改进"),
]


def calculate_composite_rating(
    content_details: list[dict] | None = None,
    impact_score: int | None = None,
    impact_max: int = 30,
) -> dict[str, Any]:
    """计算组合评分和最终评级（百分制）。

    公式：最高一项百分比 × 50 + 影响力百分比 × 50 = 百分制总分

    Args:
        content_details: 三种评分表的打分结果列表，每项含 score_percentage。
                         例如 [{"task_type": "literature_review", "score_percentage": 30.0, ...}, ...]
        impact_score: 影响力评估总分（0-30），来自 LLM 影响力评估。
        impact_max: 影响力满分（默认 30）。

    Returns:
        组合评分结果字典。
    """
    # 内容质量分：取三种评分表中最高一项的百分比
    best_content_pct = 0.0
    best_detail = None
    if content_details:
        for d in content_details:
            pct = d.get("score_percentage", 0)
            if pct > best_content_pct:
                best_content_pct = pct
                best_detail = d

    # 影响力百分比
    impact_pct = (impact_score / impact_max * 100) if (impact_score is not None and impact_max > 0) else 0.0

    # 百分制总分
    composite = best_content_pct * 0.5 + impact_pct * 0.5

    # 评级
    rating, rating_label = _get_rating(composite)

    # 可用维度
    has_content = best_content_pct > 0
    has_impact = impact_score is not None
    if has_content and has_impact:
        available_dims = "both"
    elif has_content:
        available_dims = "content_only"
    elif has_impact:
        available_dims = "impact_only"
    else:
        available_dims = "none"

    return {
        "best_content_pct": round(best_content_pct, 2),
        "best_content_detail": best_detail,
        "impact_score": impact_score,
        "impact_max": impact_max,
        "impact_pct": round(impact_pct, 2),
        "composite_score": round(composite, 2),
        "total_max": 100,
        "score_scale": "percent",
        "rating": rating,
        "rating_label": rating_label,
        "available_dimensions": available_dims,
    }


def _get_rating(score: float) -> tuple[str, str]:
    """根据百分比分数返回评级和标签。"""
    for threshold, grade, label in RATING_THRESHOLDS:
        if score >= threshold:
            return grade, label
    return "D", "需要大幅改进"


def resolve_display_composite_score(
    rating: dict[str, Any] | None = None,
    total_score: float | int | None = None,
) -> float | None:
    """解析用于展示的百分制综合分（0–100）。

    优先级（新格式优先，兼容旧格式）：
      1. rating.composite_score —— 新旧格式均为百分制展示分
      2. rating.composite_score_raw / total_max —— 旧 200 分制原始分换算
      3. 顶层 total_score —— 若 total_max==200 且数值>100，按 200 分制归一化
    """
    rating = rating or {}
    cs = rating.get("composite_score")
    if cs is not None:
        try:
            return round(float(cs), 2)
        except (TypeError, ValueError):
            pass

    total_max = rating.get("total_max") or 100
    try:
        total_max = float(total_max)
    except (TypeError, ValueError):
        total_max = 100.0

    raw = rating.get("composite_score_raw")
    if raw is not None and total_max > 0:
        try:
            return round(float(raw) / total_max * 100.0, 2)
        except (TypeError, ValueError):
            pass

    if total_score is not None:
        try:
            ts = float(total_score)
        except (TypeError, ValueError):
            return None
        # 旧格式 total_max=200：顶层 total_score 为 0–200 加权原始分
        if total_max == 200:
            return round(ts / 200.0 * 100.0, 2)
        return round(ts, 2)

    return None


def resolve_impact_score(
    impact: dict[str, Any] | None = None,
    rating: dict[str, Any] | None = None,
) -> tuple[float | int | None, int]:
    """解析影响力得分与满分。

    优先级：calibrated_total.score（新）→ impact.total_score（旧）→ rating.impact_score
    """
    impact = impact or {}
    rating = rating or {}
    impact_max = 30

    cal = impact.get("calibrated_total")
    if isinstance(cal, dict) and cal.get("score") is not None:
        try:
            mx = int(cal.get("max") or impact_max)
            return cal.get("score"), mx
        except (TypeError, ValueError):
            return cal.get("score"), impact_max

    if impact.get("total_score") is not None and not isinstance(impact.get("total_score"), dict):
        try:
            mx = int(impact.get("max_score") or impact.get("total_max") or impact_max)
            return impact.get("total_score"), mx
        except (TypeError, ValueError):
            return impact.get("total_score"), impact_max

    if rating.get("impact_score") is not None:
        try:
            mx = int(rating.get("impact_max") or impact_max)
            return rating.get("impact_score"), mx
        except (TypeError, ValueError):
            return rating.get("impact_score"), impact_max

    return None, impact_max
