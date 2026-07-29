"""包装现有 FlPackService.run_local_fedavg_pilot（sklearn，无 Flower）。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from app.services.fl_simulation.base import SimulationBackend
from app.services.fl_simulation.schemas import FlSimulationSpec, empty_run_result

logger = logging.getLogger(__name__)


class LocalPackBackend(SimulationBackend):
    backend_id = "local_pack"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "id": self.backend_id,
            "label": "FL Pack 本地 pilot（sklearn）",
            "enabled": True,
            "installed": True,
            "strategies": ["FedAvg"],
            "partitions": ["dirichlet", "iid", "pathological"],
            "note": "调用 Starter Pack 脚本；非多机联邦",
        }

    def run(self, spec: FlSimulationSpec, *, work_dir: Path) -> Dict[str, Any]:
        self.validate_spec(spec)
        work_dir.mkdir(parents=True, exist_ok=True)
        from app.services.fl_pack_service import get_fl_pack_service

        pilot = get_fl_pack_service().run_local_fedavg_pilot(timeout_sec=spec.timeout_sec)
        metrics = pilot.get("metrics") if isinstance(pilot.get("metrics"), dict) else {}
        # 用请求参数覆盖可报告字段（pilot 脚本默认固定 clients/rounds）
        if metrics:
            metrics = {
                **metrics,
                "num_clients": metrics.get("num_clients") or spec.num_clients,
                "communication_rounds": metrics.get("communication_rounds") or spec.rounds,
                "method": metrics.get("method") or spec.strategy,
                "partition": spec.partition,
            }
        metrics_path = work_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        log_path = work_dir / "run.log"
        log_path.write_text(
            str(pilot.get("stdout_preview") or pilot.get("error") or ""),
            encoding="utf-8",
        )
        success = bool(pilot.get("success"))
        return empty_run_result(
            execution_mode="local_pack",
            framework="sklearn_pack",
            spec=spec,
            success=success,
            error=None if success else str(pilot.get("error") or "local_pack pilot failed"),
            metrics=metrics,
            artifacts={
                "metrics_path": str(metrics_path),
                "log_path": str(log_path),
            },
            notes=[
                "单机进程内仿真，非多机真实联邦部署",
                "backend=local_pack（FL Starter Pack sklearn pilot）",
            ],
        )
