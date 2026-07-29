"""SimulationBackend 协议。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from app.services.fl_simulation.schemas import FlSimulationSpec


class SimulationBackend(ABC):
    backend_id: str = "base"

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """返回可用性、依赖状态、支持的策略等。"""

    def validate_spec(self, spec: FlSimulationSpec) -> None:
        """非法参数抛 ValueError。默认仅检查基础范围。"""
        if spec.num_clients < 2:
            raise ValueError("num_clients 至少为 2")
        if spec.rounds < 1:
            raise ValueError("rounds 至少为 1")

    @abstractmethod
    def run(self, spec: FlSimulationSpec, *, work_dir: Path) -> Dict[str, Any]:
        """执行仿真，返回统一契约 dict（含 execution_mode / metrics / success）。"""
