"""Discovery 迭代停止策略 — 基于布尔 Gate 停滞检测"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.quality_scoring import summarize_gate_trend

DEFAULT_STAGNANT_ROUNDS = 2


def extract_gate_results(quality_trend: Optional[List[Dict[str, Any]]] = None) -> List[bool]:
    results: List[bool] = []
    for entry in quality_trend or []:
        if not isinstance(entry, dict):
            continue
        if "passed" in entry:
            results.append(bool(entry["passed"]))
            continue
        s = entry.get("score")
        if s is None:
            continue
        try:
            results.append(float(s) >= 50.0)
        except (TypeError, ValueError):
            continue
    return results


def extract_cqs_scores(quality_trend: Optional[List[Dict[str, Any]]] = None) -> List[float]:
    """兼容旧调用：返回 100/0 伪分。"""
    return [100.0 if p else 0.0 for p in extract_gate_results(quality_trend)]


def evaluate_discovery_continuation(
    quality_trend: Optional[List[Dict[str, Any]]] = None,
    *,
    round_num: int = 2,
    min_improvement_delta: float = 0.0,
    stagnant_rounds: int = DEFAULT_STAGNANT_ROUNDS,
) -> Dict[str, Any]:
    """判断 Discovery 是否应继续迭代（基于 Gate 连续未通过）。"""
    del min_improvement_delta  # 已废弃 CQS delta 阈值
    summary = summarize_gate_trend(quality_trend)
    passes = extract_gate_results(quality_trend)

    if len(passes) < 2:
        return {
            "action": "continue",
            "reason": "Gate 样本不足，允许继续探索",
            "gate_delta": None,
            "stagnant_rounds_detected": 0,
            "latest_gate_passed": summary.get("latest_passed"),
        }

    consecutive_failures = int(summary.get("consecutive_failures") or 0)
    latest_passed = bool(passes[-1])
    prev_passed = bool(passes[-2])
    gate_improved = latest_passed and not prev_passed

    if consecutive_failures >= stagnant_rounds and round_num > 2:
        return {
            "action": "stop_stagnant",
            "reason": (
                f"连续 {consecutive_failures} 轮质量 Gate 未通过，"
                "判定为停滞，建议人工介入"
            ),
            "gate_delta": "fail→fail" if not latest_passed and not prev_passed else "unchanged",
            "stagnant_rounds_detected": consecutive_failures,
            "verdict": "stagnant",
            "latest_gate_passed": latest_passed,
        }

    if not latest_passed and round_num > 2 and not gate_improved:
        return {
            "action": "continue_with_warning",
            "reason": "本轮质量 Gate 未通过，继续探索但建议审阅",
            "gate_delta": "fail" if not latest_passed else "pass",
            "stagnant_rounds_detected": consecutive_failures,
            "latest_gate_passed": latest_passed,
        }

    return {
        "action": "continue",
        "reason": "质量 Gate 通过或较上轮改善，继续迭代" if latest_passed or gate_improved else "继续探索",
        "gate_delta": "pass" if latest_passed else ("improved" if gate_improved else "fail"),
        "stagnant_rounds_detected": consecutive_failures,
        "latest_gate_passed": latest_passed,
    }
