"""联邦仿真 Spec 与统一输出契约。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.core.project_modes import FL_SIM_PARTITIONS, FL_SIM_STRATEGIES, normalize_fl_sim_backend


@dataclass
class FlSimulationSpec:
    backend: str = "local_pack"
    num_clients: int = 5
    rounds: int = 10
    strategy: str = "FedAvg"
    partition: str = "dirichlet"
    dataset_ref: Optional[str] = None
    timeout_sec: int = 120
    dirichlet_alpha: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_spec(raw: Optional[Dict[str, Any]] = None, *, default_backend: str = "local_pack") -> FlSimulationSpec:
    data = dict(raw or {})
    backend = normalize_fl_sim_backend(data.get("backend") or default_backend, default_backend)
    strategy = str(data.get("strategy") or "FedAvg")
    if strategy not in FL_SIM_STRATEGIES:
        strategy = "FedAvg"
    partition = str(data.get("partition") or "dirichlet")
    if partition not in FL_SIM_PARTITIONS:
        partition = "dirichlet"
    try:
        num_clients = int(data.get("num_clients") or 5)
    except (TypeError, ValueError):
        num_clients = 5
    try:
        rounds = int(data.get("rounds") or 10)
    except (TypeError, ValueError):
        rounds = 10
    try:
        timeout_sec = int(data.get("timeout_sec") or 120)
    except (TypeError, ValueError):
        timeout_sec = 120
    try:
        alpha = float(data.get("dirichlet_alpha") or 0.1)
    except (TypeError, ValueError):
        alpha = 0.1
    return FlSimulationSpec(
        backend=backend,
        num_clients=max(2, min(num_clients, 50)),
        rounds=max(1, min(rounds, 200)),
        strategy=strategy,
        partition=partition,
        dataset_ref=str(data["dataset_ref"]) if data.get("dataset_ref") else None,
        timeout_sec=max(30, min(timeout_sec, 600)),
        dirichlet_alpha=max(0.01, min(alpha, 10.0)),
    )


def empty_run_result(
    *,
    execution_mode: str,
    framework: str,
    spec: FlSimulationSpec,
    success: bool = False,
    error: Optional[str] = None,
    metrics: Optional[Dict[str, Any]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "execution_mode": execution_mode,
        "framework": framework,
        "spec": spec.to_dict(),
        "metrics": metrics or {},
        "artifacts": artifacts or {},
        "success": success,
        "error": error,
        "notes": notes or [
            "单机进程内仿真，非多机真实联邦部署",
        ],
    }
