"""联邦仿真统一入口：门闩 + 落盘 + 调用 backend。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.core.project_modes import (
    empty_fl_simulation_config,
    is_federated_learning_mode,
    normalize_fl_sim_backend,
)
from app.services.fl_simulation.registry import list_backend_capabilities, resolve_backend
from app.services.fl_simulation.schemas import FlSimulationSpec, normalize_spec

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUNS_ROOT = BACKEND_ROOT / "storage" / "runs"

FL_MODE_REQUIRED = "FL_MODE_REQUIRED"


class FlSimulationError(PermissionError):
    """非联邦模式或功能关闭时抛出。"""

    def __init__(self, message: str, *, code: str = FL_MODE_REQUIRED):
        super().__init__(message)
        self.code = code


class FlSimulationRunner:
    def require_fl_mode(self, project_mode: str | None) -> None:
        if not is_federated_learning_mode(project_mode):
            raise FlSimulationError(
                "仅联邦学习（资源包）项目可使用仿真环境",
                code=FL_MODE_REQUIRED,
            )

    def require_sim_enabled(self) -> None:
        settings = get_settings()
        if not getattr(settings, "AISCI_FL_SIM_ENABLED", True):
            raise FlSimulationError(
                "联邦仿真已关闭（AISCI_FL_SIM_ENABLED=false）",
                code="FL_SIM_DISABLED",
            )

    def capabilities(self, *, project_mode: str | None) -> Dict[str, Any]:
        self.require_fl_mode(project_mode)
        settings = get_settings()
        return {
            "enabled": bool(getattr(settings, "AISCI_FL_SIM_ENABLED", True)),
            "default_backend": getattr(settings, "AISCI_FL_SIM_DEFAULT_BACKEND", "local_pack"),
            "backends": list_backend_capabilities(),
            "note": "单机进程内仿真，非多机真实联邦部署；与通用沙箱路径隔离",
        }

    def build_config_blob(
        self,
        *,
        backend: str | None = None,
        spec_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        settings = get_settings()
        default_backend = getattr(settings, "AISCI_FL_SIM_DEFAULT_BACKEND", "local_pack")
        bid = normalize_fl_sim_backend(backend, default_backend)
        merged = {"backend": bid, **(spec_overrides or {})}
        spec = normalize_spec(merged, default_backend=bid)
        cfg = empty_fl_simulation_config(
            backend=spec.backend,
            num_clients=spec.num_clients,
            rounds=spec.rounds,
            strategy=spec.strategy,
            partition=spec.partition,
        )
        cfg["enabled"] = bool(getattr(settings, "AISCI_FL_SIM_ENABLED", True))
        cfg["spec"]["timeout_sec"] = spec.timeout_sec
        cfg["spec"]["dirichlet_alpha"] = spec.dirichlet_alpha
        if spec.dataset_ref:
            cfg["spec"]["dataset_ref"] = spec.dataset_ref
        return cfg

    def run(
        self,
        *,
        project_mode: str | None,
        project_id: str,
        experiment_id: str,
        spec_raw: Optional[Dict[str, Any]] = None,
        project_sim_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.require_fl_mode(project_mode)
        self.require_sim_enabled()

        base: Dict[str, Any] = {}
        if isinstance(project_sim_config, dict):
            base.update(project_sim_config.get("spec") or {})
            if project_sim_config.get("backend"):
                base["backend"] = project_sim_config["backend"]
        if isinstance(spec_raw, dict):
            base.update({k: v for k, v in spec_raw.items() if v is not None})

        settings = get_settings()
        default_backend = getattr(settings, "AISCI_FL_SIM_DEFAULT_BACKEND", "local_pack")
        spec = normalize_spec(base, default_backend=default_backend)
        backend = resolve_backend(spec.backend)

        run_id = str(uuid.uuid4())
        work_dir = RUNS_ROOT / project_id / "fl_sim" / experiment_id / run_id
        work_dir.mkdir(parents=True, exist_ok=True)

        result = backend.run(spec, work_dir=work_dir)
        result["run_id"] = run_id
        result["project_id"] = project_id
        result["experiment_id"] = experiment_id
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        result_path = work_dir / "result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        arts = dict(result.get("artifacts") or {})
        arts["result_path"] = str(result_path)
        arts["work_dir"] = str(work_dir)
        result["artifacts"] = arts
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


_runner: Optional[FlSimulationRunner] = None


def get_fl_simulation_runner() -> FlSimulationRunner:
    global _runner
    if _runner is None:
        _runner = FlSimulationRunner()
    return _runner
