"""可选调用 vendored shaxiang-main。失败时由上层回退 mock。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _ensure_shaxiang_path() -> Path:
    # AISci/shaxiang-main/shaxiang-main
    root = Path(__file__).resolve().parents[4] / "shaxiang-main" / "shaxiang-main"
    if not root.is_dir():
        raise FileNotFoundError(f"shaxiang root not found: {root}")
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    return root


def try_recommend_datasets(
    experiment: Dict[str, Any], human_feedback: Optional[str] = None
) -> Optional[List[Dict[str, Any]]]:
    """当前优先走服务层 mock；shaxiang advisor 接口不稳定时直接返回 None。"""
    try:
        _ensure_shaxiang_path()
        # 显式保留钩子，后续可接 DatasetAdvisor
        return None
    except Exception as exc:
        logger.info("try_recommend_datasets skip: %s", exc)
        return None


def try_design_script(
    experiment: Dict[str, Any],
    data_config: Dict[str, Any],
    feedback: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        _ensure_shaxiang_path()
        from services.experiment_service import ExperimentService

        svc = ExperimentService.get_instance()
        sx_id = experiment.get("shaxiang_experiment_id")
        if not sx_id:
            created = svc.create_experiment(
                title=(experiment.get("title") or experiment.get("hypothesis") or "exp")[:30],
                research_goal=experiment.get("research_goal") or experiment.get("hypothesis") or "",
                constraints=list(experiment.get("constraints") or []),
                executor_type=experiment.get("executor_type") or "sandbox",
                max_iterations=int(experiment.get("max_iterations") or 10),
            )
            created.hypothesis = experiment.get("hypothesis") or ""
            from storage.sqlite_store import SQLiteRepository

            SQLiteRepository(svc.config.storage.db_path).update_experiment(created)
            sx_id = created.id
            experiment["shaxiang_experiment_id"] = sx_id

        plan = svc.design_script(sx_id, data_config, human_feedback=feedback)
        if hasattr(plan, "model_dump"):
            return plan.model_dump()
        if isinstance(plan, dict):
            return plan
        return {
            "title": getattr(plan, "title", "script"),
            "description": getattr(plan, "description", ""),
            "methodology": getattr(plan, "methodology", ""),
            "analysis_script": getattr(plan, "analysis_script", ""),
            "script_params": getattr(plan, "script_params", {}) or {},
            "success_criteria": getattr(plan, "success_criteria", []) or [],
        }
    except Exception as exc:
        logger.info("try_design_script skip: %s", exc)
        return None


def try_run_iteration(experiment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        _ensure_shaxiang_path()
        from services.experiment_service import ExperimentService

        svc = ExperimentService.get_instance()
        sx_id = experiment.get("shaxiang_experiment_id")
        if not sx_id:
            return None
        record = svc.run_iteration(sx_id)
        metrics = getattr(record, "metrics", None) or {}
        return {
            "iteration_number": getattr(
                record, "iteration_number", int(experiment.get("current_iteration") or 0) + 1
            ),
            "status": getattr(record, "status", "success") or "success",
            "plan": getattr(record, "plan", None) or {"title": "shaxiang iteration"},
            "result": getattr(record, "result", None) or {"metrics": metrics},
            "analysis": getattr(record, "analysis", None) or {},
            "decision": getattr(record, "decision", None) or {"continue": True},
            "metrics": metrics if isinstance(metrics, dict) else {},
            "duration_seconds": float(getattr(record, "duration_seconds", 0) or 0),
            "error_message": getattr(record, "error_message", None),
            "created_at": str(getattr(record, "created_at", "") or ""),
        }
    except Exception as exc:
        logger.info("try_run_iteration skip: %s", exc)
        return None
