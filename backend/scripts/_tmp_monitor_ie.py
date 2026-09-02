# -*- coding: utf-8 -*-
"""One-shot status check for PEFT IE redesign/run monitoring."""
import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path

pid = "867f76de-f558-4a6e-9cec-9f95b4260044"
eid = "e3e08129-aa9d-40c6-835a-c820d27514d0"
root = Path(r"d:/Workplace/AISci")
print("CHECK", datetime.now().isoformat(timespec="seconds"))

try:
    r = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)
    print("backend_ok", r.status)
except Exception as e:
    print("backend_down", e)

# active job
job = None
try:
    raw = urllib.request.urlopen(
        f"http://127.0.0.1:8000/api/v1/projects/{pid}/iterative-experiments/{eid}/active-job",
        timeout=12,
    ).read()
    job = (json.loads(raw).get("data") or {}).get("job")
except Exception as e:
    print("active_job_err", e)

if job:
    print(
        "JOB",
        job.get("kind"),
        job.get("status"),
        job.get("message"),
        "err=",
        job.get("error"),
        "created=",
        job.get("created_at"),
        "updated=",
        job.get("updated_at"),
        "id=",
        job.get("job_id") or job.get("id"),
    )
else:
    print("JOB none")

# AISci + shaxiang
p = root / "backend/storage/iterative_experiments" / f"{pid}.json"
d = json.loads(p.read_text(encoding="utf-8"))
e = next((x for x in (d.get("experiments") or []) if x.get("id") == eid), None)
if e:
    print(
        "AISCI",
        e.get("status"),
        e.get("phase"),
        f"iter={e.get('current_iteration')}/{e.get('max_iterations')}",
        f"n={len(e.get('iterations') or [])}",
        "upd=",
        e.get("updated_at"),
    )

sx = sqlite3.connect(str(root / "shaxiang-main/shaxiang-main/data/experiments.db"))
sx.row_factory = sqlite3.Row
row = sx.execute(
    "SELECT status, phase, current_iteration, updated_at FROM experiments WHERE id=?",
    (eid,),
).fetchone()
print("SX", dict(row) if row else None)
n = sx.execute(
    "SELECT COUNT(*) FROM iterations WHERE experiment_id=?", (eid,)
).fetchone()[0]
print("SX_ITERS", n)

plan_raw = sx.execute("SELECT initial_plan FROM experiments WHERE id=?", (eid,)).fetchone()
if plan_raw and plan_raw[0]:
    plan = json.loads(plan_raw[0])
    script = plan.get("analysis_script") or ""
    print("SCRIPT_LEN", len(script))
    print(
        "SCRIPT_FLAGS",
        "distilbert=",
        ("distilbert" in script.lower() or "DistilBERT" in script),
        "lora=",
        ("lora" in script.lower() or "peft" in script.lower()),
        "tfidf=",
        ("Tfidf" in script or "tfidf" in script.lower()),
        "lr=",
        ("LogisticRegression" in script),
    )
    print("CRITERIA", plan.get("success_criteria"))

# latest iter assessment if any new
last = sx.execute(
    "SELECT iteration_number, status, duration_seconds, created_at, analysis_json, metrics_json FROM iterations WHERE experiment_id=? ORDER BY iteration_number DESC LIMIT 1",
    (eid,),
).fetchone()
if last:
    print(
        "LAST_ITER",
        last["iteration_number"],
        last["status"],
        "dur=",
        last["duration_seconds"],
        "at=",
        last["created_at"],
    )
    if last["analysis_json"]:
        a = json.loads(last["analysis_json"])
        print("ASSESS", a.get("overall_assessment"), "|", str(a.get("summary") or "")[:160])
    if last["metrics_json"]:
        m = json.loads(last["metrics_json"])
        print(
            "METRICS",
            {
                k: m.get(k)
                for k in (
                    "accuracy_improvement",
                    "f1_improvement",
                    "dynamic_accuracy",
                    "fixed_accuracy",
                    "overall_score",
                )
                if k in m
            },
        )
