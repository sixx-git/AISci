"""联邦真实运行时 Skill — Flower / FATE 兼容 / sklearn 本地联邦"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment._federated_runtime import run_federated_runtime_pilot


class FederatedRuntimeExecutorSkill(BaseSkill):
    name = "FederatedRuntimeExecutor"
    description = "在 CSV 上运行 sklearn/Flower/FATE 兼容联邦 pilot"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        datasets: List[Dict[str, Any]] = input_data.get("datasets") or []
        fl_context = input_data.get("fl_context") or {}
        plan = input_data.get("experiment_plan") or {}

        tabular = [d for d in datasets if d.get("data_type") == "tabular" and d.get("file_path")]
        if not tabular:
            result.data = {"available": False, "reason": "no_tabular_dataset"}
            return result

        pilot = run_federated_runtime_pilot(tabular[0]["file_path"], fl_context, plan)
        if not pilot:
            result.data = {"available": False, "reason": "runtime_execution_failed"}
            result.add_warning("联邦 runtime 未产出结果，将回退 CSV 聚合或 simulation")
            return result

        result.data = {"available": True, "pilot": pilot}
        return result
