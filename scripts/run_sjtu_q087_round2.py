"""sjtu_q_087 Round 2: fork rerun from literature_mining with real qwen3.6-plus."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(r"D:\Workplace\AISci")
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

CHINA = timezone(timedelta(hours=8))
PID = "93db5222-b1ee-48fc-8e16-7d4fed89ef2a"
PARENT_RUN = "c6e7fbfb-645a-461e-8e57-5ceb515bd86a"
CASE_DIR = ROOT / "output" / "提交" / "模板" / "代表性案例" / "sjtu_q_087人工智能能否取代医生"
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


def export_round2(run_id: str) -> None:
    import sqlite3

    db = BACKEND / "data" / "aiscientist.db"

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
        return {k: parse(row[k]) if k in {
            "input_data", "output_data", "extra_metadata", "config",
            "supporting_fact_ids", "model_parameters", "prompt_versions_used",
        } else row[k] for k in row.keys()}

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
            "note": "Fork rerun from literature_mining. Round 1 directory must stay untouched.",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    ROUND2_DIR.mkdir(parents=True, exist_ok=True)
    from app.core import database as _db
    from app.core.llm_runtime import (
        get_effective_model,
        get_effective_use_mock_llm,
        update_runtime,
    )
    from app.services.pipeline_service import get_pipeline_service

    update_runtime(model="qwen3.6-plus", use_mock_llm=False, use_env_api_key=True)
    model = get_effective_model()
    mock = get_effective_use_mock_llm()
    print(f"LLM model={model} mock={mock}", flush=True)
    if model != "qwen3.6-plus":
        raise SystemExit(f"expected qwen3.6-plus, got {model}")
    if mock:
        raise SystemExit("refusing to run with USE_MOCK_LLM=true")

    _db.init_db()
    db = _db.SessionLocal()
    try:
        from app.services.vector_store import search_vector_store, sync_project_index

        print("Rebuilding vector index for sjtu_q_087 ...", flush=True)
        indexed = sync_project_index(PID, db=db)
        print(f"INDEX_REBUILT chunks={indexed}", flush=True)
        probe = search_vector_store(PID, "人工智能 辅助诊断 医学影像", top_k=3, db=db)
        print(f"INDEX_PROBE hits={len(probe)}", flush=True)
        if not probe:
            raise SystemExit("vector index rebuild produced no search hits")

        svc = get_pipeline_service(db)
        new_run_id = svc.start_rerun_from_stage(
            project_id=PID,
            parent_run_id=PARENT_RUN,
            from_stage="literature_mining",
            use_human_modified_output=True,
            rerun_mode="from_stage_onward",
            human_feedback=HUMAN_FEEDBACK,
            run_options=RUN_OPTIONS,
        )
        db.commit()
        print(f"ROUND2_RUN_ID={new_run_id}", flush=True)
        write_status(
            phase="created",
            run_id=new_run_id,
            parent_run_id=PARENT_RUN,
            model=model,
            mock=mock,
            from_stage="literature_mining",
            rerun_mode="from_stage_onward",
        )
    except Exception:
        traceback.print_exc()
        write_status(phase="failed_create", error=traceback.format_exc())
        db.close()
        return 1

    try:
        write_status(phase="running")
        result = svc.execute_pipeline_run(new_run_id)
        status = getattr(result, "status", None)
        status_val = status.value if hasattr(status, "value") else str(status)
        if status is None:
            from app.models.pipeline import PipelineRun as _PR

            row = db.query(_PR).filter(_PR.run_id == new_run_id).first()
            if row is not None:
                db.refresh(row)
                st = row.status
                status_val = st.value if hasattr(st, "value") else str(st)
        print(f"ROUND2_STATUS={status_val}", flush=True)
        write_status(phase="finished", pipeline_status=status_val)
        export_round2(new_run_id)
        write_status(phase="exported")
        if str(status_val).upper() in {"FAILED", "NONE"}:
            print("ROUND2_FAILED", flush=True)
            return 2
        print("ROUND2_DONE", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        write_status(phase="failed_execute", error=traceback.format_exc())
        try:
            export_round2(new_run_id)
        except Exception:
            traceback.print_exc()
        print("ROUND2_FAILED", flush=True)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
