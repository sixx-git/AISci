"""联邦学习仿真后端（仅 federated_learning 模式；与通用沙箱隔离）。"""
from app.services.fl_simulation.runner import FlSimulationRunner, get_fl_simulation_runner
from app.services.fl_simulation.schemas import FlSimulationSpec, normalize_spec

__all__ = [
    "FlSimulationRunner",
    "FlSimulationSpec",
    "get_fl_simulation_runner",
    "normalize_spec",
]
