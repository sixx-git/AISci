"""Flower 单机仿真后端：优先 flwr，未安装时用兼容 numpy 入口并标注。"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.services.fl_simulation.base import SimulationBackend
from app.services.fl_simulation.schemas import FlSimulationSpec, empty_run_result

logger = logging.getLogger(__name__)


def _flwr_installed() -> bool:
    try:
        import flwr  # noqa: F401

        return True
    except Exception:
        return False


def _entry_script() -> Path:
    from app.services.fl_pack_service import fl_pack_root

    return fl_pack_root() / "scripts" / "flower_hfl_sim_entry.py"


class FlowerBackend(SimulationBackend):
    backend_id = "flower"

    def capabilities(self) -> Dict[str, Any]:
        settings = get_settings()
        feature_on = bool(getattr(settings, "AISCI_FL_FLOWER_ENABLED", True))
        installed = _flwr_installed()
        return {
            "id": self.backend_id,
            "label": "Flower 单机仿真",
            "enabled": feature_on,
            "installed": installed,
            "strategies": ["FedAvg", "FedProx"],
            "partitions": ["dirichlet", "iid", "pathological"],
            "note": "单机进程内仿真（Simulation Engine / 兼容入口），非多机部署",
            "install_hint": None if installed else "pip install 'flwr>=1.8.0'",
            "fallback": "numpy_compat" if not installed else None,
        }

    def run(self, spec: FlSimulationSpec, *, work_dir: Path) -> Dict[str, Any]:
        self.validate_spec(spec)
        settings = get_settings()
        if not getattr(settings, "AISCI_FL_FLOWER_ENABLED", True):
            return empty_run_result(
                execution_mode="flower",
                framework="flower",
                spec=spec,
                success=False,
                error="AISCI_FL_FLOWER_ENABLED=false",
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        script = _entry_script()
        if not script.is_file():
            return empty_run_result(
                execution_mode="flower",
                framework="flower",
                spec=spec,
                success=False,
                error=f"flower entry missing: {script}",
            )

        metrics_path = work_dir / "metrics.json"
        log_path = work_dir / "run.log"
        use_flwr = _flwr_installed()
        cmd = [
            sys.executable,
            str(script),
            "--clients",
            str(spec.num_clients),
            "--rounds",
            str(spec.rounds),
            "--strategy",
            spec.strategy,
            "--partition",
            spec.partition,
            "--alpha",
            str(spec.dirichlet_alpha),
            "--out",
            str(metrics_path),
        ]
        if not use_flwr:
            cmd.append("--numpy-fallback")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=spec.timeout_sec,
                cwd=str(script.parent),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return empty_run_result(
                execution_mode="flower",
                framework="flower" if use_flwr else "flower_numpy_compat",
                spec=spec,
                success=False,
                error=f"Flower simulation timed out after {spec.timeout_sec}s",
                artifacts={"work_dir": str(work_dir)},
            )
        except Exception as exc:
            logger.warning("[FL Sim] Flower run failed: %s", exc)
            return empty_run_result(
                execution_mode="flower",
                framework="flower" if use_flwr else "flower_numpy_compat",
                spec=spec,
                success=False,
                error=str(exc),
            )

        log_path.write_text(
            (proc.stdout or "") + "\n" + (proc.stderr or ""),
            encoding="utf-8",
        )
        metrics = _load_metrics(metrics_path, proc.stdout)
        success = bool(metrics) and proc.returncode == 0
        notes = [
            "单机进程内仿真，非多机真实联邦部署",
            "backend=flower",
        ]
        framework = "flower"
        if not use_flwr:
            framework = "flower_numpy_compat"
            notes.append("flwr 未安装，已使用兼容 numpy 仿真；安装 flwr 可启用官方 Simulation Engine")
        return empty_run_result(
            execution_mode="flower",
            framework=framework,
            spec=spec,
            success=success,
            error=None if success else (proc.stderr or proc.stdout or "flower simulation failed")[:800],
            metrics=metrics,
            artifacts={
                "metrics_path": str(metrics_path),
                "log_path": str(log_path),
                "returncode": proc.returncode,
            },
            notes=notes,
        )


def _load_metrics(path: Path, stdout: Optional[str]) -> Dict[str, Any]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    raw = (stdout or "").strip()
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return {}
