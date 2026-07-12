"""Discovery 主环决策逻辑（从 pipeline_service 抽离）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.core.iteration_control import evaluate_discovery_continuation
from app.core.iterative_science import evaluate_discovery_federated_acceptance
from app.core.pipeline_modes import ENSEMBLE_ACCEPT_SCORE
from app.core.project_modes import ProjectMode


def check_discovery_stagnation(
    quality_trend: Optional[List[Dict[str, Any]]],
    *,
    round_num: int,
    min_improvement_delta: float = 0.0,
    stagnant_rounds: int = 2,
) -> Dict[str, Any]:
    return evaluate_discovery_continuation(
        quality_trend,
        round_num=round_num,
        min_improvement_delta=min_improvement_delta,
        stagnant_rounds=stagnant_rounds,
    )


def check_discovery_acceptance(
    hypothesis_review: Dict[str, Any],
    small_validation: Dict[str, Any],
    *,
    project_mode: str,
) -> Tuple[bool, Dict[str, Any]]:
    """返回 (是否应停止 Discovery 环, 附加元数据)。"""
    hr = hypothesis_review or {}
    ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
    decision = ensemble.get("decision") or hr.get("ensemble_decision")
    overall = ensemble.get("overall") or hr.get("ensemble_overall")

    fed_accept = evaluate_discovery_federated_acceptance(hr, small_validation or {})

    if project_mode == ProjectMode.FEDERATED_LEARNING.value:
        if fed_accept.get("accepted"):
            return True, {
                "status": "accepted",
                "overall": overall,
                "federated_acceptance": fed_accept,
            }
        return False, {"federated_acceptance": fed_accept, "decision": decision, "overall": overall}

    if decision == "Accept" or (
        overall is not None and float(overall) >= ENSEMBLE_ACCEPT_SCORE
    ):
        return True, {"status": "accepted", "overall": overall, "decision": decision}

    return False, {"decision": decision, "overall": overall, "federated_acceptance": fed_accept}
