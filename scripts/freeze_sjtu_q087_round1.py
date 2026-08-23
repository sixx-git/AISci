"""Freeze sjtu_q_087 / project 93db5222 round-1 artifacts for P13–P17."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(r"D:\Workplace\AISci")
DB = ROOT / "backend" / "data" / "aiscientist.db"
PID_PREFIX = "93db5222"
OUT = ROOT / "output" / "提交" / "模板" / "代表性案例" / "sjtu_q_087人工智能能否取代医生"
CHINA = timezone(timedelta(hours=8))


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def parse_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def row_to_dict(row: sqlite3.Row) -> dict:
    out = {}
    for key in row.keys():
        val = row[key]
        if key in {
            "input_data", "output_data", "extra_metadata", "config",
            "attachments", "supporting_fact_ids", "model_parameters",
            "model_versions", "tags", "prompt_versions_used",
        }:
            out[key] = parse_json(val)
        else:
            out[key] = val
    return out


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        path.write_text(dumps(data), encoding="utf-8")
    else:
        path.write_text(str(data), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frozen_at = datetime.now(CHINA).isoformat()
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row

    proj = con.execute("SELECT * FROM projects WHERE id LIKE ?", (f"{PID_PREFIX}%",)).fetchone()
    if not proj:
        raise SystemExit(f"project not found: {PID_PREFIX}")
    project = row_to_dict(proj)
    pid = project["id"]

    run_row = con.execute(
        "SELECT * FROM pipeline_runs WHERE project_id=? ORDER BY started_at DESC",
        (pid,),
    ).fetchone()
    run = row_to_dict(run_row)
    run_pk = run["id"]

    stages = [
        row_to_dict(r)
        for r in con.execute(
            "SELECT * FROM pipeline_stage_executions WHERE pipeline_run_id=? ORDER BY stage_order",
            (run_pk,),
        ).fetchall()
    ]
    hyps = [
        row_to_dict(r)
        for r in con.execute("SELECT * FROM hypotheses WHERE project_id=?", (pid,)).fetchall()
    ]
    evidences = [
        row_to_dict(r)
        for r in con.execute("SELECT * FROM evidences WHERE project_id=?", (pid,)).fetchall()
    ]
    docs = [
        row_to_dict(r)
        for r in con.execute("SELECT * FROM documents WHERE project_id=?", (pid,)).fetchall()
    ]
    for d in docs:
        d.pop("file_path", None)
    advice = [
        row_to_dict(r)
        for r in con.execute(
            "SELECT * FROM coordinator_advice WHERE project_id=? ORDER BY created_at",
            (pid,),
        ).fetchall()
    ]
    report = con.execute("SELECT * FROM reports WHERE project_id=?", (pid,)).fetchone()
    report_d = row_to_dict(report) if report else None

    write(OUT / "00_project.json", project)
    write(
        OUT / "01_pipeline_run.json",
        {
            k: run[k]
            for k in run
            if k not in {"error_stacktrace"}
        },
    )

    stage_dir = OUT / "02_stages"
    stage_dir.mkdir(exist_ok=True)
    stage_index = []
    for st in stages:
        key = str(st.get("stage") or "unknown").lower()
        slim = {
            "stage": st.get("stage"),
            "status": st.get("status"),
            "stage_order": st.get("stage_order"),
            "started_at": st.get("started_at"),
            "completed_at": st.get("completed_at"),
            "duration_ms": st.get("duration_ms"),
            "model_used": st.get("model_used"),
            "token_count": st.get("token_count"),
            "prompt_used": st.get("prompt_used") if "prompt_used" in st else None,
            "error_message": st.get("error_message"),
            "output_data": st.get("output_data"),
            "extra_metadata": st.get("extra_metadata"),
        }
        write(stage_dir / f"{st.get('stage_order', 0):02d}_{key}.json", slim)
        stage_index.append(
            {
                "stage": slim["stage"],
                "status": slim["status"],
                "duration_ms": slim["duration_ms"],
                "model_used": slim["model_used"],
                "token_count": slim["token_count"],
                "has_output": bool(slim["output_data"]),
            }
        )
    write(stage_dir / "_index.json", stage_index)

    write(OUT / "03_hypotheses.json", hyps)
    write(OUT / "04_evidences.json", evidences)
    write(OUT / "05_documents.json", docs)
    write(OUT / "06_coordinator_advice.json", advice)

    meta = run.get("extra_metadata") if isinstance(run.get("extra_metadata"), dict) else {}
    write(
        OUT / "07_run_extra_metadata.json",
        {
            "run_id": run.get("run_id"),
            "closed_loop_events": meta.get("closed_loop_events"),
            "quality_trend": meta.get("quality_trend"),
            "science_iteration_rounds": meta.get("science_iteration_rounds"),
            "hitl_gate": meta.get("hitl_gate"),
            "quality_acceptance": meta.get("quality_acceptance"),
            "run_options": meta.get("run_options"),
            "last_in_place_rerun": meta.get("last_in_place_rerun"),
            "version_snapshots": meta.get("version_snapshots"),
        },
    )

    if report_d:
        report_slim = dict(report_d)
        md = report_slim.pop("markdown_content", None)
        write(OUT / "08_report_meta.json", report_slim)
        if md:
            (OUT / "08_report.md").write_text(str(md), encoding="utf-8")
        pdf_path = report_slim.get("pdf_path")
        if pdf_path:
            src = Path(pdf_path)
            if not src.is_absolute():
                src = ROOT / src
            if src.exists():
                shutil.copy2(src, OUT / src.name)

    exp_src = ROOT / "backend" / "storage" / "iterative_experiments" / f"{pid}.json"
    if exp_src.exists():
        shutil.copy2(exp_src, OUT / "09_iterative_experiments.json")

    # Human-readable round-1 card for P14–P15
    pu = next((s.get("output_data") or {} for s in stages if str(s.get("stage")).endswith("PROBLEM_UNDERSTANDING") or str(s.get("stage")) == "PROBLEM_UNDERSTANDING"), {})
    kg = next((s.get("output_data") or {} for s in stages if "KNOWLEDGE_GAP" in str(s.get("stage"))), {})
    lm = next((s.get("output_data") or {} for s in stages if "LITERATURE_MINING" in str(s.get("stage"))), {})
    hg = next((s.get("output_data") or {} for s in stages if "HYPOTHESIS_GENERATION" in str(s.get("stage"))), {})
    hr = next((s.get("output_data") or {} for s in stages if "HYPOTHESIS_REVIEW" in str(s.get("stage"))), {})
    if not isinstance(pu, dict):
        pu = {}
    if not isinstance(kg, dict):
        kg = {}
    if not isinstance(lm, dict):
        lm = {}
    if not isinstance(hg, dict):
        hg = {}
    if not isinstance(hr, dict):
        hr = {}

    lines = [
        "# sjtu_q_087 第一轮冻结快照",
        "",
        f"- 冻结时间：{frozen_at}",
        f"- 官方题目：sjtu_q_087 人工智能能否取代医生 / Can AI replace a doctor?",
        f"- 项目 ID：`{pid}`",
        f"- 项目名：{project.get('name')}",
        f"- 研究问题（项目内）：{project.get('research_question')}",
        f"- Pipeline run_id：`{run.get('run_id')}`",
        f"- 运行状态：{run.get('status')}，耗时 {run.get('total_duration_ms')} ms",
        f"- 模型：阶段记录为 qwen3.7-max（经阿里云百炼）",
        "",
        "## 不要覆盖本目录",
        "本目录是 **Round 1（重跑证据链之前）** 的冻结件。第二轮请另开 `round2/`，禁止原地覆盖这些 JSON。",
        "",
        "## P14 可用要点",
        f"- 科学问题原文（125 题）：人工智能能否取代医生？",
        f"- 本项目展开题：{project.get('research_question')}",
        f"- 研究对象：{((pu.get('research_object') or {}) if isinstance(pu.get('research_object'), dict) else {})}",
        f"- 主要矛盾：{pu.get('main_contradiction')}",
        f"- 知识缺口数：{len(kg.get('knowledge_gaps') or [])}",
        f"- 事实白名单：{len(lm.get('facts') or [])} 条；证据原文 {len(lm.get('evidence') or [])}；来源论文 {len(lm.get('source_papers') or [])}",
        f"- 约束：{project.get('constraints')}",
        "",
        "## P15 第一轮假设",
    ]
    for i, h in enumerate(hyps, 1):
        lines.append(f"### H-{i:02d} status={h.get('status')} evidence_level={h.get('evidence_level')}")
        lines.append(f"- 陈述：{h.get('hypothesis')}")
        lines.append(f"- 依据 fact_ids：{h.get('supporting_fact_ids')}")
        lines.append(f"- 可检验性：{h.get('testability')}")
        lines.append(f"- 风险：{h.get('risk')}")
        lines.append("")
    ens = (hr.get("skill_outputs") or {}).get("ensemble_review") if isinstance(hr.get("skill_outputs"), dict) else {}
    lines += [
        "## 第一轮评审",
        f"- ensemble_decision：{hr.get('ensemble_decision')} overall={hr.get('ensemble_overall')} primary_index={hr.get('primary_index')}",
        f"- weaknesses：{(ens or {}).get('weaknesses') if isinstance(ens, dict) else None}",
        "",
        "## 第一轮真实问题（供 P16，尚未做第二轮）",
        "1. 入选假设验证需要万例级前瞻交互日志，评审写明数据难、统计效力不足。",
        "2. HITL 后转到迭代实验页；Pipeline 的 ITERATIVE_EXPERIMENT 阶段仍为 PENDING，计划在实验子项目中。",
        "3. 评审弱点：需补充更多可验证细节。",
        "4. 三条假设均围绕不确定性 / 责任 / 伦理，区分度有限。",
        "5. 本轮不是低证据触发：三条假设 evidence_level=high，不能写成系统因证据弱自动迭代。",
        "",
        "## 文件清单",
        "- `00_project.json` 项目主数据",
        "- `01_pipeline_run.json` 运行记录",
        "- `02_stages/` 七阶段输出",
        "- `03_hypotheses.json` 三条假设",
        "- `04_evidences.json` 证据表",
        "- `05_documents.json` 入库文献",
        "- `06_coordinator_advice.json` 大家长提示",
        "- `07_run_extra_metadata.json` 闭环事件 / 门禁 / HITL",
        "- `08_report_meta.json` / `08_report.md` 报告",
        "- `09_iterative_experiments.json` 迭代实验（1 组 1 轮）",
    ]
    (OUT / "ROUND1_SNAPSHOT.md").write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "case_id": "sjtu_q_087",
        "title": "人工智能能否取代医生",
        "round": 1,
        "frozen_at": frozen_at,
        "project_id": pid,
        "run_id": run.get("run_id"),
        "pipeline_run_pk": run_pk,
        "hypothesis_count": len(hyps),
        "evidence_count": len(evidences),
        "document_count": len(docs),
        "stage_count": len(stages),
        "note": "Round 1 freeze before evidence-chain rerun. Do not overwrite.",
    }
    write(OUT / "MANIFEST.json", manifest)
    print(dumps(manifest))
    print("OUT", OUT)


if __name__ == "__main__":
    main()
