"""迭代实验长任务后台执行（对齐 Pipeline：立即返回 job_id，轮询取结果）。"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))

KIND_DESIGN_SCRIPT = "design_script"
KIND_RUN_TO_COMPLETION = "run_to_completion"


def _now() -> str:
    return datetime.now(CHINA_TZ).isoformat()


@dataclass
class IterativeExperimentJob:
    id: str
    project_id: str
    experiment_id: str
    kind: str
    status: str = "queued"  # queued | running | succeeded | failed
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.id,
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "message": self.message,
            "result": self.result,
        }


class IterativeExperimentJobStore:
    """进程内 job 表；单 worker uvicorn 足够。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, IterativeExperimentJob] = {}
        # experiment_id -> active job_id
        self._active: Dict[str, str] = {}

    def get(self, job_id: str) -> Optional[IterativeExperimentJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_active_for_experiment(self, experiment_id: str) -> Optional[IterativeExperimentJob]:
        with self._lock:
            jid = self._active.get(experiment_id)
            return self._jobs.get(jid) if jid else None

    def list_for_experiment(self, experiment_id: str, limit: int = 10) -> List[IterativeExperimentJob]:
        with self._lock:
            items = [j for j in self._jobs.values() if j.experiment_id == experiment_id]
        items.sort(key=lambda j: j.created_at, reverse=True)
        return items[:limit]

    def start(
        self,
        *,
        project_id: str,
        experiment_id: str,
        kind: str,
        runner: Callable[[], Dict[str, Any]],
        message: str = "",
    ) -> IterativeExperimentJob:
        with self._lock:
            existing_id = self._active.get(experiment_id)
            if existing_id:
                existing = self._jobs.get(existing_id)
                if existing and existing.status in {"queued", "running"}:
                    raise ValueError(
                        f"该实验已有进行中的任务（{existing.kind}，job_id={existing.id}），请等待完成后再试"
                    )
            job = IterativeExperimentJob(
                id=str(uuid.uuid4()),
                project_id=project_id,
                experiment_id=experiment_id,
                kind=kind,
                status="queued",
                message=message or f"{kind} 已排队",
            )
            self._jobs[job.id] = job
            self._active[experiment_id] = job.id

        thread = threading.Thread(
            target=self._execute,
            args=(job.id, runner),
            name=f"ie-job-{kind}-{job.id[:8]}",
            daemon=True,
        )
        thread.start()
        logger.info(
            "迭代实验后台任务已启动 kind=%s job_id=%s experiment_id=%s",
            kind,
            job.id,
            experiment_id,
        )
        return job

    def _execute(self, job_id: str, runner: Callable[[], Dict[str, Any]]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = "running"
            job.updated_at = _now()
            job.message = f"{job.kind} 执行中…"

        try:
            result = runner()
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job.status = "succeeded"
                job.result = result if isinstance(result, dict) else {"value": result}
                job.error = None
                job.updated_at = _now()
                job.message = f"{job.kind} 已完成"
                if self._active.get(job.experiment_id) == job_id:
                    self._active.pop(job.experiment_id, None)
            logger.info("迭代实验后台任务成功 job_id=%s", job_id)
        except Exception as exc:
            logger.exception("迭代实验后台任务失败 job_id=%s: %s", job_id, exc)
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job.status = "failed"
                job.error = str(exc) or exc.__class__.__name__
                job.updated_at = _now()
                job.message = f"{job.kind} 失败"
                if self._active.get(job.experiment_id) == job_id:
                    self._active.pop(job.experiment_id, None)


_store: Optional[IterativeExperimentJobStore] = None
_store_lock = threading.Lock()


def get_ie_job_store() -> IterativeExperimentJobStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = IterativeExperimentJobStore()
        return _store
