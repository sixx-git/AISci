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


def format_rating_report(rating_result: dict[str, Any], metadata: dict | None = None) -> str:
    """生成人类可读的评级报告。"""
    lines = []
    lines.append("=" * 50)
    lines.append("综合学术质量评估报告")
    lines.append("=" * 50)

    pct = rating_result.get("composite_score", 0)

    lines.append(f"\n综合评级: {rating_result['rating']} ({rating_result['rating_label']})")
    lines.append(f"总分: {pct}%")

    # 内容质量分（最高一项）
    best_pct = rating_result.get("best_content_pct", 0)
    best_detail = rating_result.get("best_content_detail")
    lines.append(f"\n内容质量（最高项）: {best_pct}%")
    if best_detail:
        lines.append(f"  来源: {best_detail.get('label', '?')}")
        lines.append(f"  得分: {best_detail.get('raw_score', '?')}/{best_detail.get('total_score', '?')}")

    # 影响力分
    impact_pct = rating_result.get("impact_pct", 0)
    impact_score = rating_result.get("impact_score")
    impact_max = rating_result.get("impact_max", 30)
    if impact_score is not None:
        lines.append(f"\n影响力评估: {impact_score}/{impact_max} ({impact_pct}%)")

    lines.append("")
    return "\n".join(lines)
