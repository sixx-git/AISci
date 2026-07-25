"""迭代实验后台 job 存储与互斥。"""
from __future__ import annotations

import time

from app.services.iterative_experiment_jobs import (
    KIND_DESIGN_SCRIPT,
    IterativeExperimentJobStore,
)


def test_job_succeeds_and_clears_active():
    store = IterativeExperimentJobStore()

    def runner():
        time.sleep(0.05)
        return {"id": "exp-1", "phase": "script_designed"}

    job = store.start(
        project_id="p1",
        experiment_id="e1",
        kind=KIND_DESIGN_SCRIPT,
        runner=runner,
    )
    assert job.status in {"queued", "running"}
    deadline = time.time() + 2
    while time.time() < deadline:
        cur = store.get(job.id)
        assert cur is not None
        if cur.status in {"succeeded", "failed"}:
            break
        time.sleep(0.02)
    cur = store.get(job.id)
    assert cur is not None
    assert cur.status == "succeeded"
    assert cur.result and cur.result["id"] == "exp-1"
    assert store.get_active_for_experiment("e1") is None


def test_rejects_second_active_job():
    store = IterativeExperimentJobStore()
    gate = {"go": False}

    def slow():
        while not gate["go"]:
            time.sleep(0.01)
        return {"id": "exp-1"}

    first = store.start(
        project_id="p1",
        experiment_id="e1",
        kind=KIND_DESIGN_SCRIPT,
        runner=slow,
    )
    try:
        store.start(
            project_id="p1",
            experiment_id="e1",
            kind=KIND_DESIGN_SCRIPT,
            runner=lambda: {"id": "x"},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "进行中" in str(exc)
    finally:
        gate["go"] = True
    deadline = time.time() + 2
    while time.time() < deadline:
        if store.get(first.id).status == "succeeded":
            break
        time.sleep(0.02)
    assert store.get(first.id).status == "succeeded"
