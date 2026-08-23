"""Trigger sjtu_q_087 Round 2 via the live FastAPI server (shares Zvec with uvicorn)."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
PID = "93db5222-b1ee-48fc-8e16-7d4fed89ef2a"
PARENT_RUN = "c6e7fbfb-645a-461e-8e57-5ceb515bd86a"
CHINA = timezone(timedelta(hours=8))
CASE_DIR = Path(r"D:\Workplace\AISci\output\提交\模板\代表性案例\sjtu_q_087人工智能能否取代医生")
ROUND2_DIR = CASE_DIR / "round2"
STATUS_PATH = ROUND2_DIR / "RUN_STATUS.json"

HUMAN_FEEDBACK = """第二轮人工反馈（对应第一轮真实问题，不是低证据自动门禁）：
1. 入选假设的验证依赖万例前瞻交互日志，评审已指出数据难、统计效力不足；请补充可在已有医学影像公开数据上落地的可验证细节与对照设计。
2. 请加强反对证据、伦理约束与法律责任边界，避免三条假设过度同质化。
3. 验证场景收窄为辅助诊断（影像/病理），不得把「完全取代医生」写成可立即临床部署的结论。
4. 引用只能使用白名单 fact_id，核心事实必须可溯源。"""

RUN_OPTIONS = {
    "enable_gap_search": True,
    "literature_max_papers": 16,
    "evidence_reasoning_max_rounds": 2,
    "pause_after_hypothesis_review": True,
    "enable_hitl_gate": False,
    "iteration_mode": "human",
    "pipeline_mode": "teaching",
}


def api(method: str, path: str, body=None, timeout: int = 60):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {err_body[:2000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接后端 {BASE}: {exc}") from exc


def write_status(**kwargs) -> None:
    ROUND2_DIR.mkdir(parents=True, exist_ok=True)
    payload = {}
    if STATUS_PATH.exists():
        try:
            payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    payload.update(kwargs)
    payload["updated_at"] = datetime.now(CHINA).isoformat()
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def unwrap(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def export_round2(run_id: str) -> None:
    import sqlite3

    db = Path(r"D:\Workplace\AISci\backend\data\aiscientist.db")

    def parse(v):
        if isinstance(v, (dict, list)) or v is None:
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    def rowd(row):
        keys = row.keys()
        return {
            k: parse(row[k]) if k in {
                "input_data", "output_data", "extra_metadata", "config",
                "supporting_fact_ids", "model_parameters", "prompt_versions_used",
            } else row[k]
            for k in keys
        }

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    run = con.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise RuntimeError(f"round2 run not found: {run_id}")
    run_d = rowd(run)
    stages = [
        rowd(r) for r in con.execute(
            "SELECT * FROM pipeline_stage_executions WHERE pipeline_run_id=? ORDER BY stage_order",
            (run_d["id"],),
        ).fetchall()
    ]
    hyps = [rowd(r) for r in con.execute("SELECT * FROM hypotheses WHERE project_id=?", (PID,)).fetchall()]
    (ROUND2_DIR / "02_stages").mkdir(exist_ok=True)
    (ROUND2_DIR / "01_pipeline_run.json").write_text(
        json.dumps(run_d, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    index = []
    for st in stages:
        key = str(st.get("stage") or "unknown").lower()
        slim = {
            "stage": st.get("stage"),
            "status": st.get("status"),
            "duration_ms": st.get("duration_ms"),
            "model_used": st.get("model_used"),
            "token_count": st.get("token_count"),
            "output_data": st.get("output_data"),
            "error_message": st.get("error_message"),
        }
        fname = f"{st.get('stage_order', 0):02d}_{key}.json"
        (ROUND2_DIR / "02_stages" / fname).write_text(
            json.dumps(slim, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        index.append({
            "stage": slim["stage"], "status": slim["status"],
            "model_used": slim["model_used"], "token_count": slim["token_count"],
            "duration_ms": slim["duration_ms"],
        })
    (ROUND2_DIR / "02_stages" / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROUND2_DIR / "03_hypotheses.json").write_text(
        json.dumps(hyps, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    meta = run_d.get("extra_metadata") if isinstance(run_d.get("extra_metadata"), dict) else {}
    (ROUND2_DIR / "07_run_extra_metadata.json").write_text(
        json.dumps({
            "run_id": run_id,
            "parent_run_id": meta.get("parent_run_id"),
            "closed_loop_events": meta.get("closed_loop_events"),
            "quality_trend": meta.get("quality_trend"),
            "science_iteration_rounds": meta.get("science_iteration_rounds"),
            "hitl_gate": meta.get("hitl_gate"),
            "quality_acceptance": meta.get("quality_acceptance"),
            "run_options": meta.get("run_options"),
            "feedback_constraints": meta.get("feedback_constraints"),
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (ROUND2_DIR / "MANIFEST.json").write_text(
        json.dumps({
            "case_id": "sjtu_q_087",
            "round": 2,
            "model": "qwen3.6-plus",
            "use_mock_llm": False,
            "run_id": run_id,
            "parent_run_id": PARENT_RUN,
            "status": run_d.get("status"),
            "frozen_at": datetime.now(CHINA).isoformat(),
            "note": "Fork rerun from literature_mining via live API. Round 1 directory must stay untouched.",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    ROUND2_DIR.mkdir(parents=True, exist_ok=True)
    health = api("GET", "/health")
    print(f"HEALTH={health}", flush=True)
    llm_health = api("GET", "/health/llm")
    print(f"LLM_HEALTH={json.dumps(unwrap(llm_health), ensure_ascii=False)[:500]}", flush=True)

    cfg = unwrap(api("PUT", "/api/v1/llm/config", {
        "model": "qwen3.6-plus",
        "use_mock_llm": False,
        "use_env_api_key": True,
    }))
    print(
        f"LLM_CONFIG model={cfg.get('model')} mock={cfg.get('use_mock_llm')} key={cfg.get('api_key_masked')}",
        flush=True,
    )
    if cfg.get("model") != "qwen3.6-plus":
        raise SystemExit(f"expected qwen3.6-plus, got {cfg.get('model')}")
    if cfg.get("use_mock_llm"):
        raise SystemExit("refusing to run with USE_MOCK_LLM=true")

    test = unwrap(api("POST", "/api/v1/llm/test", timeout=90))
    print(f"LLM_TEST={json.dumps(test, ensure_ascii=False)[:400]}", flush=True)
    if not test.get("ok"):
        raise SystemExit(f"qwen3.6-plus 连接测试失败: {test}")

    search = unwrap(api(
        "POST",
        f"/api/v1/vector-search/search?project_id={PID}",
        {"query": "人工智能 辅助诊断 医学影像", "top_k": 3},
    ))
    hits = (search or {}).get("total") if isinstance(search, dict) else None
    print(f"INDEX_PROBE total={hits} raw_keys={list(search)[:8] if isinstance(search, dict) else type(search)}", flush=True)
    if not hits:
        raise SystemExit("live server vector search returned no hits; abort before rerun")

    payload = {
        "project_id": PID,
        "run_id": PARENT_RUN,
        "stage": "literature_mining",
        "use_human_modified_output": True,
        "rerun_mode": "from_stage_onward",
        "human_feedback": HUMAN_FEEDBACK,
        "run_options": RUN_OPTIONS,
    }
    started = unwrap(api("POST", "/api/v1/human-loop/rerun-from-stage", payload, timeout=120))
    run_id = started.get("run_id")
    print(f"ROUND2_RUN_ID={run_id}", flush=True)
    write_status(
        phase="running",
        run_id=run_id,
        parent_run_id=PARENT_RUN,
        model="qwen3.6-plus",
        mock=False,
        via="live_api",
        from_stage="literature_mining",
        rerun_mode="from_stage_onward",
    )

    terminal = {"COMPLETED", "FAILED", "HUMAN_REVIEW_REQUIRED", "CANCELLED"}
    last = ""
    for i in range(180):
        time.sleep(10)
        detail = unwrap(api("GET", f"/api/v1/pipeline/run/{run_id}", timeout=30))
        status = str(detail.get("status") or "")
        current = detail.get("current_stage") or ""
        msg = f"poll#{i+1} status={status} current={current}"
        if msg != last:
            print(msg, flush=True)
            last = msg
            write_status(phase="running", pipeline_status=status, current_stage=current)
        if status.upper() in terminal:
            write_status(phase="finished", pipeline_status=status, current_stage=current)
            export_round2(run_id)
            write_status(phase="exported")
            print(f"ROUND2_STATUS={status}", flush=True)
            if status.upper() == "FAILED":
                print("ROUND2_FAILED", flush=True)
                return 2
            print("ROUND2_DONE", flush=True)
            return 0
    print("ROUND2_TIMEOUT", flush=True)
    write_status(phase="timeout")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
