"""Discovery 迭代停止策略 — 基于 CQS 改善幅度"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_MIN_IMPROVEMENT_DELTA = 3.0
DEFAULT_STAGNANT_ROUNDS = 2


def extract_cqs_scores(quality_trend: Optional[List[Dict[str, Any]]] = None) -> List[float]:
    scores: List[float] = []
    for entry in quality_trend or []:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("cqs", entry.get("score"))
        if raw is None:
            continue
        try:
            scores.append(float(raw))
        except (TypeError, ValueError):
            continue
    return scores


def evaluate_discovery_continuation(
    quality_trend: Optional[List[Dict[str, Any]]] = None,
    *,
    round_num: int = 2,
    min_improvement_delta: float = DEFAULT_MIN_IMPROVEMENT_DELTA,
    stagnant_rounds: int = DEFAULT_STAGNANT_ROUNDS,
) -> Dict[str, Any]:
    """判断 Discovery 是否应继续迭代。"""
    scores = extract_cqs_scores(quality_trend)
    if len(scores) < 2:
        return {
            "action": "continue",
            "reason": "CQS 样本不足，允许继续探索",
            "cqs_delta": None,
            "stagnant_rounds_detected": 0,
        }

    cqs_delta = round(scores[-1] - scores[-2], 2)
    stagnant_count = 0
    for i in range(len(scores) - 1, 0, -1):
        if scores[i] - scores[i - 1] < min_improvement_delta:
            stagnant_count += 1
        else:
            break

    if stagnant_count >= stagnant_rounds and round_num > 2:
        return {
            "action": "stop_stagnant",
            "reason": (
                f"连续 {stagnant_count} 轮 CQS 提升 < {min_improvement_delta}，"
                "判定为停滞，建议人工介入"
            ),
            "cqs_delta": cqs_delta,
            "stagnant_rounds_detected": stagnant_count,
            "verdict": "stagnant",
        }

    if cqs_delta < min_improvement_delta and round_num > 2:
        return {
            "action": "continue_with_warning",
            "reason": f"本轮 CQS 仅变化 {cqs_delta:+.1f}，低于阈值 {min_improvement_delta}",
            "cqs_delta": cqs_delta,
            "stagnant_rounds_detected": stagnant_count,
        }

    return {
        "action": "continue",
        "reason": f"CQS 改善 {cqs_delta:+.1f}，继续迭代",
        "cqs_delta": cqs_delta,
        "stagnant_rounds_detected": stagnant_count,
    }
