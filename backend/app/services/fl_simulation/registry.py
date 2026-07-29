"""按 backend_id 解析仿真后端；非 FL 模式由 runner 拒绝。"""
from __future__ import annotations

from typing import Dict, List

from app.core.config import get_settings
from app.core.project_modes import normalize_fl_sim_backend
from app.services.fl_simulation.base import SimulationBackend
from app.services.fl_simulation.fedml_backend import FedMLBackend
from app.services.fl_simulation.flower_backend import FlowerBackend
from app.services.fl_simulation.local_pack_backend import LocalPackBackend


def _backends() -> Dict[str, SimulationBackend]:
    return {
        "local_pack": LocalPackBackend(),
        "flower": FlowerBackend(),
        "fedml": FedMLBackend(),
    }


def list_backend_capabilities() -> List[dict]:
    settings = get_settings()
    sim_on = bool(getattr(settings, "AISCI_FL_SIM_ENABLED", True))
    items = []
    for b in _backends().values():
        caps = b.capabilities()
        caps["feature_enabled"] = sim_on and bool(caps.get("enabled", True))
        items.append(caps)
    return items


def resolve_backend(backend_id: str | None) -> SimulationBackend:
    settings = get_settings()
    default = getattr(settings, "AISCI_FL_SIM_DEFAULT_BACKEND", "local_pack") or "local_pack"
    bid = normalize_fl_sim_backend(backend_id, default)
    backends = _backends()
    if bid not in backends:
        raise ValueError(f"未知仿真后端: {backend_id}")
    return backends[bid]
