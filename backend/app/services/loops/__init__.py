"""科研闭环 Loop 编排辅助模块（从 pipeline_service 逐步抽离）。"""
from app.services.loops.closed_loop_helpers import (
    build_data_gap_loop_payload,
    infer_quality_trend_entries,
    summarize_gap_loop,
)
from app.services.loops.discovery_runner import (
    check_discovery_acceptance,
    check_discovery_stagnation,
)
from app.services.loops.dry_run import simulate_loop_decisions

__all__ = [
    "build_data_gap_loop_payload",
    "infer_quality_trend_entries",
    "summarize_gap_loop",
    "check_discovery_acceptance",
    "check_discovery_stagnation",
    "simulate_loop_decisions",
]
