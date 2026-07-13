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

from app.core.config import get_settings
from app.core.dataset_scale import (
    resolve_analysis_tier,
    tier_sample_rows,
    tier_sandbox_docker_memory,
    tier_sandbox_timeout_sec,
)
from app.services.analysis_script_utils import sanitize_analysis_script
from app.services.tabular_encoding_utils import (
    build_sandbox_encode_preamble,
    build_sandbox_load_data_preamble,
)

logger = logging.getLogger(__name__)

CHINA_TZ = timezone(timedelta(hours=8))
SANDBOX_TIMEOUT_SEC = 120
SANDBOX_DOCKER_IMAGE = os.environ.get("AISCI_SANDBOX_DOCKER_IMAGE", "python:3.11-slim")
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

        linked_data: Optional[str] = None
        data_link_mode = "none"
        external_data_mount: Optional[str] = None
        if csv_data_path and os.path.exists(csv_data_path):
            linked_data, data_link_mode, external_data_mount = self._resolve_data_link(
                csv_data_path, data_dir, extra_env
            )

        prepared_script = self._prepare_analysis_script(analysis_script or "", linked_data)
        script_path.write_text(prepared_script, encoding="utf-8")

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
            env.update({k: str(v) for k, v in extra_env.items() if v is not None})

        tier = env.get("AISCI_DATA_TIER") or resolve_analysis_tier(
            os.path.getsize(csv_data_path) if csv_data_path and os.path.exists(csv_data_path) else 0
        )
        env.setdefault("AISCI_DATA_TIER", tier)
        env.setdefault("AISCI_SAMPLE_ROWS", str(tier_sample_rows(tier) or 0))
        timeout_sec = int(env.get("AISCI_SANDBOX_TIMEOUT_SEC") or tier_sandbox_timeout_sec(tier))

        use_docker = self._should_use_docker(extra_env)
        started = datetime.now(CHINA_TZ)
        isolation_mode = "subprocess"
        proc = None
        docker_error = None

        if use_docker:
            proc, isolation_mode, docker_error = self._run_in_docker(
                exp_dir, wrapper_path, env, linked_data, external_data_mount, tier
            )
        if proc is None:
            proc = subprocess.run(
                [sys.executable, str(wrapper_path)],
                cwd=str(exp_dir),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=env,
            )
            if use_docker and docker_error:
                isolation_mode = "subprocess_fallback"
        finished = datetime.now(CHINA_TZ)
        duration_ms = int((finished - started).total_seconds() * 1000)

        stdout_path = exp_dir / "stdout.txt"
        stderr_path = exp_dir / "stderr.txt"
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")

        metrics = self._load_metrics(exp_dir, proc.stdout or "")
        plots = self._collect_plots(plots_dir, exp_dir)

        success = proc.returncode == 0
        output_complete = self._is_output_complete(metrics, plots)
        sandbox_incomplete = success and not output_complete
        if sandbox_incomplete:
            logger.warning(
                "沙箱进程成功但未产出有效 metrics/plots run_id=%s metrics_keys=%s plots=%d",
                run_id,
                list(metrics.keys()) if isinstance(metrics, dict) else type(metrics),
                len(plots),
            )

        manifest = {
            "experiment_id": exp_dir.name,
            "run_id": run_id,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_ms": duration_ms,
            "return_code": proc.returncode,
            "success": success,
            "data_path": linked_data,
            "data_link_mode": data_link_mode,
            "analysis_tier": tier,
            "sandbox_timeout_sec": timeout_sec,
            "script_path": str(script_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "metrics": metrics,
            "plots": plots,
            "output_complete": output_complete,
            "sandbox_incomplete": sandbox_incomplete,
            "isolation_mode": isolation_mode,
            "docker_error": docker_error,
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
            "output_complete": output_complete,
            "sandbox_incomplete": sandbox_incomplete,
            "data_source": "sandbox_execution" if success and output_complete else (
                "sandbox_incomplete" if success else "sandbox_failed"
            ),
            "provenance": "experiment_sandbox",
            "isolation_mode": isolation_mode,
            "docker_error": docker_error,
            "analysis_tier": tier,
            "data_link_mode": data_link_mode,
            "execution_mode": "sample" if tier in ("T1", "T2", "T3") else "full",
        }

    @staticmethod
    def _should_use_docker(extra_env: Optional[Dict[str, str]] = None) -> bool:
        flag = os.environ.get("AISCI_SANDBOX_USE_DOCKER", "").lower()
        if flag in ("1", "true", "yes"):
            return True
        if extra_env and extra_env.get("AISCI_SANDBOX_USE_DOCKER", "").lower() in ("1", "true", "yes"):
            return True
        return False

    @staticmethod
    def _docker_available() -> bool:
        try:
            r = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _resolve_data_link(
        csv_data_path: str,
        data_dir: Path,
        extra_env: Optional[Dict[str, str]],
    ) -> tuple[str, str, Optional[str]]:
        """大文件引用原路径，小文件复制到沙箱目录。"""
        import shutil

        settings = get_settings()
        abs_src = os.path.abspath(csv_data_path)
        size = os.path.getsize(abs_src)
        tier = (extra_env or {}).get("AISCI_DATA_TIER") or resolve_analysis_tier(size)
        no_copy = size > int(settings.LARGE_FILE_NO_COPY_BYTES) or tier in ("T1", "T2", "T3")

        sample_parquet = (extra_env or {}).get("AISCI_SAMPLE_PARQUET") or ""
        if sample_parquet and os.path.isfile(sample_parquet):
            dest = str(data_dir / "sample.parquet")
            if not Path(dest).exists():
                shutil.copy2(sample_parquet, dest)
            return dest, "sample_parquet", None

        if no_copy:
            return abs_src, "reference", str(Path(abs_src).parent)

        dest = str(data_dir / "input.csv")
        if not Path(dest).exists():
            shutil.copy2(abs_src, dest)
        return dest, "copy", None

    def _run_in_docker(
        self,
        exp_dir: Path,
        wrapper_path: Path,
        env: Dict[str, str],
        linked_data: Optional[str],
        external_data_mount: Optional[str],
        tier: str,
    ):
        """可选 Docker 隔离执行，失败时由调用方降级 subprocess。"""
        if not self._docker_available():
            return None, "subprocess", "docker unavailable"

        memory = env.get("AISCI_SANDBOX_DOCKER_MEMORY") or tier_sandbox_docker_memory(tier)
        timeout_sec = int(env.get("AISCI_SANDBOX_TIMEOUT_SEC") or tier_sandbox_timeout_sec(tier))
        work_mount = f"{exp_dir.resolve()}:/work"
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", memory,
            "--cpus", "1",
            "-v", work_mount,
            "-w", "/work",
            "-e", "PYTHONIOENCODING=utf-8",
            "-e", "MPLBACKEND=Agg",
            "-e", "AISCI_RUN_DIR=/work",
            "-e", "AISCI_PLOTS_DIR=/work/plots",
        ]
        if external_data_mount and linked_data:
            host_dir = Path(external_data_mount).resolve()
            cmd.extend(["-v", f"{host_dir}:/ext_data:ro"])
            container_path = f"/ext_data/{Path(linked_data).name}"
            cmd.extend(["-e", f"AISCI_DATA_PATH={container_path}", "-e", f"CSV_DATA_PATH={container_path}"])
        elif linked_data:
            cmd.extend(["-e", "AISCI_DATA_PATH=/work/data/input.csv", "-e", "CSV_DATA_PATH=/work/data/input.csv"])
        passthrough = (
            "AISCI_DATA_TIER", "AISCI_SAMPLE_ROWS", "AISCI_SAMPLE_PARQUET",
            "AISCI_SANDBOX_TIMEOUT_SEC", "AISCI_PROJECT_ID",
        )
        for key in passthrough:
            if env.get(key):
                cmd.extend(["-e", f"{key}={env[key]}"])
        cmd.extend([SANDBOX_DOCKER_IMAGE, "python", "_sandbox_runner.py"])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec + 30,
            )
            return proc, "docker", None
        except subprocess.TimeoutExpired as exc:
            return None, "subprocess", f"docker timeout: {exc}"
        except Exception as exc:
            return None, "subprocess", str(exc)

    @staticmethod
    def _prepare_analysis_script(script: str, data_path: Optional[str]) -> str:
        """将 LLM 脚本中的硬编码 CSV 路径替换为沙箱环境变量。"""
        import re

        header = (
            "# --- AISci sandbox preamble (auto-injected) ---\n"
            "import os\n"
            + build_sandbox_encode_preamble()
            + build_sandbox_load_data_preamble()
            + "_AISCI_DATA = os.environ.get('AISCI_DATA_PATH') or os.environ.get('CSV_DATA_PATH') or ''\n"
            "if not _AISCI_DATA:\n"
            "    raise FileNotFoundError('沙箱未注入 AISCI_DATA_PATH，请上传或合并 CSV 后重试')\n"
            "# --- end preamble ---\n\n"
        )
        body = script or ""
        body = sanitize_analysis_script(body) if body else body
        if data_path and "# --- AISci sandbox preamble" not in body:
            if "_aisci_encode_frame" not in body:
                body = (
                    "# --- AISci encode helpers (auto-injected) ---\n"
                    + build_sandbox_encode_preamble()
                    + body
                )
        elif "_aisci_encode_frame" not in body:
            body = (
                "# --- AISci encode helpers (auto-injected) ---\n"
                + build_sandbox_encode_preamble()
                + body
            )
        if data_path:
            body = re.sub(
                r"pd\.read_csv\s*\(\s*['\"][^'\"]+['\"][^)]*\)",
                "_aisci_load_data()",
                body,
            )
            body = re.sub(
                r"(?<![.\w])read_csv\s*\(\s*['\"][^'\"]+['\"][^)]*\)",
                "_aisci_load_data()",
                body,
            )
            body = re.sub(
                r"pd\.read_csv\s*\(\s*_AISCI_DATA[^)]*\)",
                "_aisci_load_data()",
                body,
            )
            if "# --- AISci sandbox preamble" not in body:
                body = header + body
        return body

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

    @staticmethod
    def _is_output_complete(metrics: Dict[str, Any], plots: List[Dict[str, Any]]) -> bool:
        from app.services.report_plot_service import is_sandbox_output_complete

        return is_sandbox_output_complete(metrics, plots)


def get_experiment_sandbox_service() -> ExperimentSandboxService:
    return ExperimentSandboxService()
