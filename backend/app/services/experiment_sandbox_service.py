"""实验沙箱 — 执行 LLM 生成的 analysis_script，产出可绑定的 run artifacts（追 AI Scientist v1）"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHINA_TZ = timezone(timedelta(hours=8))
SANDBOX_TIMEOUT_SEC = 120
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_ROOT = BACKEND_ROOT / "storage" / "runs"


def get_run_experiment_dir(run_id: str, experiment_id: Optional[str] = None) -> Path:
    exp_id = experiment_id or str(uuid.uuid4())
    path = RUNS_ROOT / run_id / "experiments" / exp_id
    path.mkdir(parents=True, exist_ok=True)
    return path


class ExperimentSandboxService:
    """在隔离子进程中执行分析脚本，收集 metrics / plots / logs。"""

    def execute_analysis_script(
        self,
        run_id: str,
        analysis_script: str,
        *,
        csv_data_path: Optional[str] = None,
        experiment_id: Optional[str] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        exp_dir = get_run_experiment_dir(run_id, experiment_id)
        plots_dir = exp_dir / "plots"
        plots_dir.mkdir(exist_ok=True)
        data_dir = exp_dir / "data"
        data_dir.mkdir(exist_ok=True)

        script_path = exp_dir / "analysis.py"
        script_path.write_text(analysis_script or "", encoding="utf-8")

        linked_data: Optional[str] = None
        if csv_data_path and os.path.exists(csv_data_path):
            linked_data = str(data_dir / "input.csv")
            try:
                if not Path(linked_data).exists():
                    import shutil
                    shutil.copy2(csv_data_path, linked_data)
            except Exception as exc:
                logger.warning(f"复制数据到沙箱失败: {exc}")
                linked_data = csv_data_path

        wrapper_path = exp_dir / "_sandbox_runner.py"
        wrapper_path.write_text(self._build_wrapper(str(script_path), str(plots_dir)), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["MPLBACKEND"] = "Agg"
        env["AISCI_RUN_DIR"] = str(exp_dir)
        env["AISCI_PLOTS_DIR"] = str(plots_dir)
        if linked_data:
            env["AISCI_DATA_PATH"] = linked_data
            env["CSV_DATA_PATH"] = linked_data
        if extra_env:
            env.update(extra_env)

        started = datetime.now(CHINA_TZ)
        proc = subprocess.run(
            [sys.executable, str(wrapper_path)],
            cwd=str(exp_dir),
            capture_output=True,
            text=True,
            timeout=SANDBOX_TIMEOUT_SEC,
            env=env,
        )
        finished = datetime.now(CHINA_TZ)
        duration_ms = int((finished - started).total_seconds() * 1000)

        stdout_path = exp_dir / "stdout.txt"
        stderr_path = exp_dir / "stderr.txt"
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")

        metrics = self._load_metrics(exp_dir, proc.stdout or "")
        plots = self._collect_plots(plots_dir, exp_dir)

        success = proc.returncode == 0
        manifest = {
            "experiment_id": exp_dir.name,
            "run_id": run_id,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_ms": duration_ms,
            "return_code": proc.returncode,
            "success": success,
            "data_path": linked_data,
            "script_path": str(script_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "metrics": metrics,
            "plots": plots,
        }
        manifest_path = exp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "experiment_id": exp_dir.name,
            "artifact_dir": str(exp_dir),
            "manifest_path": str(manifest_path),
            "success": success,
            "return_code": proc.returncode,
            "duration_ms": duration_ms,
            "stdout": (proc.stdout or "")[:8000],
            "stderr": (proc.stderr or "")[:4000],
            "metrics": metrics,
            "plots": plots,
            "data_source": "sandbox_execution" if success else "sandbox_failed",
            "provenance": "experiment_sandbox",
        }

    @staticmethod
    def _build_wrapper(script_path: str, plots_dir: str) -> str:
        return f'''import json, os, runpy, sys
from pathlib import Path

run_dir = Path(os.environ.get("AISCI_RUN_DIR", "."))
plots_dir = Path(r"{plots_dir}")
plots_dir.mkdir(exist_ok=True)

# 注入常用路径变量，供 LLM 脚本使用
DATA_PATH = os.environ.get("AISCI_DATA_PATH") or os.environ.get("CSV_DATA_PATH") or ""
PLOTS_DIR = str(plots_dir)
OUT_DIR = str(run_dir)

metrics = {{}}
try:
    runpy.run_path(r"{script_path}", run_name="__main__")
    metrics_path = run_dir / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
except Exception as e:
    print(json.dumps({{"sandbox_error": str(e)}}))
    sys.exit(1)
finally:
    out = run_dir / "metrics.json"
    if not out.exists():
        with open(out, "w", encoding="utf-8") as f:
            json.dump(metrics if metrics else {{"note": "no metrics emitted"}}, f, ensure_ascii=False)
'''

    @staticmethod
    def _load_metrics(exp_dir: Path, stdout: str) -> Dict[str, Any]:
        metrics_path = exp_dir / "metrics.json"
        if metrics_path.exists():
            try:
                return json.loads(metrics_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        parsed = ExperimentSandboxService._parse_json_from_stdout(stdout)
        if parsed:
            return parsed
        return {"stdout_preview": stdout[:500] if stdout else ""}

    @staticmethod
    def _parse_json_from_stdout(stdout: str) -> Dict[str, Any]:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    continue
        match = re.search(r"\{[^{}]*\}", stdout)
        if match:
            try:
                obj = json.loads(match.group())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def _collect_plots(plots_dir: Path, exp_dir: Path) -> List[Dict[str, Any]]:
        plots: List[Dict[str, Any]] = []
        search_dirs = [plots_dir, exp_dir]
        seen = set()
        for d in search_dirs:
            if not d.exists():
                continue
            for p in d.glob("*.png"):
                if p.name in seen:
                    continue
                seen.add(p.name)
                plots.append({
                    "plot_id": p.stem,
                    "type": "sandbox_plot",
                    "title": p.stem.replace("_", " "),
                    "path": str(p),
                    "file_path": str(p),
                    "source": "sandbox_execution",
                    "is_generated_from_real_data": True,
                })
        return plots


def get_experiment_sandbox_service() -> ExperimentSandboxService:
    return ExperimentSandboxService()
