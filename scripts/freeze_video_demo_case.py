"""Freeze 联邦智慧康养 demo project into 视频-项目演示输入输出 (same layout as sjtu_q_087)."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(r"D:\Workplace\AISci")
DB = ROOT / "backend" / "data" / "aiscientist.db"
PID = "6dbf4b5a-034b-4a63-a8bd-2c601588f477"
# Prefer latest completed run; override with RUN_ID env if needed.
RUN_ID = "b2dd78ee-7492-4700-a41b-9ad5591f6df6"
OUT = ROOT / "output" / "提交" / "模板" / "代表性案例" / "视频-项目演示输入输出"
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
            "input_data",
            "output_data",
            "extra_metadata",
            "config",
            "attachments",
            "supporting_fact_ids",
            "model_parameters",
            "model_versions",
            "tags",
            "prompt_versions_used",
            "keywords",
            "constraints",
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

    proj = con.execute("SELECT * FROM projects WHERE id=?", (PID,)).fetchone()
    if not proj:
        raise SystemExit(f"project not found: {PID}")
    project = row_to_dict(proj)
    pid = project["id"]

    run_row = con.execute(
        "SELECT * FROM pipeline_runs WHERE project_id=? AND run_id=?",
        (pid, RUN_ID),
    ).fetchone()
    if not run_row:
        run_row = con.execute(
            "SELECT * FROM pipeline_runs WHERE project_id=? ORDER BY started_at DESC",
            (pid,),
        ).fetchone()
    run = row_to_dict(run_row)
    run_pk = run["id"]
    final_report_id = run.get("final_report_id")

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

    report = None
    if final_report_id:
        report = con.execute("SELECT * FROM reports WHERE id=?", (final_report_id,)).fetchone()
    if not report:
        report = con.execute(
            "SELECT * FROM reports WHERE project_id=? ORDER BY created_at DESC",
            (pid,),
        ).fetchone()
    report_d = row_to_dict(report) if report else None

    write(OUT / "00_project.json", project)
    write(
        OUT / "01_pipeline_run.json",
        {k: run[k] for k in run if k not in {"error_stacktrace"}},
    )

    stage_dir = OUT / "02_stages"
    if stage_dir.exists():
        for p in stage_dir.glob("*.json"):
            p.unlink()
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
        if md and str(md).strip():
            (OUT / "08_report.md").write_text(str(md), encoding="utf-8")
        else:
            # Structured report fields → readable markdown for demo I/O
            sections = [
                ("# " + (report_slim.get("paper_title") or report_slim.get("title") or "报告"),),
                ("",),
                ("## Abstract", report_slim.get("paper_abstract")),
                ("## Problem Statement", report_slim.get("problem_statement")),
                ("## Rationale", report_slim.get("rationale")),
                ("## Technical Details", report_slim.get("technical_details")),
                ("## Datasets", report_slim.get("datasets")),
                ("## Source", report_slim.get("source")),
                ("## Target", report_slim.get("target")),
                ("## Methods", report_slim.get("methods")),
                ("## Experiments", report_slim.get("experiments")),
                ("## Results", report_slim.get("results")),
                ("## References", report_slim.get("references")),
                ("## Summary", report_slim.get("summary")),
            ]
            md_lines: list[str] = []
            for sec in sections:
                if len(sec) == 1:
                    md_lines.append(sec[0])
                    continue
                title, body = sec
                if body is None or (isinstance(body, str) and not body.strip()):
                    continue
                md_lines.append("")
                md_lines.append(title)
                md_lines.append("")
                if isinstance(body, (dict, list)):
                    md_lines.append("```json")
                    md_lines.append(dumps(body))
                    md_lines.append("```")
                else:
                    md_lines.append(str(body))
            (OUT / "08_report.md").write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
        pdf_path = report_slim.get("pdf_path")
        if pdf_path:
            src = Path(pdf_path)
            if not src.is_absolute():
                src = ROOT / src
            if not src.exists():
                alt = ROOT / "backend" / str(pdf_path).lstrip("/\\")
                if alt.exists():
                    src = alt
            if not src.exists():
                for cand in (
                    ROOT / "backend" / "storage" / "reports" / str(pdf_path),
                    ROOT / "backend" / "storage" / "reports" / f"{pdf_path}.pdf",
                    ROOT / "backend" / "data" / "reports" / f"{pdf_path}.pdf",
                ):
                    if cand.exists():
                        src = cand
                        break
            if src.exists() and src.is_dir():
                # latex export dir: report.pdf / report.tex / report_data.json
                for name in ("report.pdf", "report.tex", "report_data.json"):
                    f = src / name
                    if f.exists():
                        shutil.copy2(f, OUT / f"08_{name}")
                fig_dir = src / "figures"
                if fig_dir.exists() and any(fig_dir.iterdir()):
                    dest_fig = OUT / "08_report_figures"
                    if dest_fig.exists():
                        shutil.rmtree(dest_fig)
                    shutil.copytree(fig_dir, dest_fig)
            elif src.exists() and src.is_file():
                shutil.copy2(src, OUT / (src.name if src.suffix else f"{pdf_path}.pdf"))

    exp_src = ROOT / "backend" / "storage" / "iterative_experiments" / f"{pid}.json"
    if exp_src.exists():
        shutil.copy2(exp_src, OUT / "09_iterative_experiments.json")

    pu = next(
        (
            s.get("output_data") or {}
            for s in stages
            if "PROBLEM_UNDERSTANDING" in str(s.get("stage"))
        ),
        {},
    )
    kg = next(
        (s.get("output_data") or {} for s in stages if "KNOWLEDGE_GAP" in str(s.get("stage"))),
        {},
    )
    lm = next(
        (
            s.get("output_data") or {}
            for s in stages
            if "LITERATURE_MINING" in str(s.get("stage"))
        ),
        {},
    )
    hr = next(
        (
            s.get("output_data") or {}
            for s in stages
            if "HYPOTHESIS_REVIEW" in str(s.get("stage"))
        ),
        {},
    )
    for obj_name, obj in (("pu", pu), ("kg", kg), ("lm", lm), ("hr", hr)):
        if not isinstance(obj, dict):
            locals()[obj_name] = {}
    if not isinstance(pu, dict):
        pu = {}
    if not isinstance(kg, dict):
        kg = {}
    if not isinstance(lm, dict):
        lm = {}
    if not isinstance(hr, dict):
        hr = {}

    models = sorted(
        {
            str(s.get("model_used"))
            for s in stages
            if s.get("model_used")
        }
    )
    ens = (hr.get("skill_outputs") or {}).get("ensemble_review") if isinstance(hr.get("skill_outputs"), dict) else {}

    lines = [
        "# 视频演示案例冻结快照 — 联邦智慧康养 / 合成数据跌倒检测",
        "",
        f"- 冻结时间：{frozen_at}",
        f"- 案例用途：赛道一方向 1 项目演示视频输入输出对照（与 `sjtu_q_087` 同结构）",
        f"- 项目 ID：`{pid}`",
        f"- 项目名：{project.get('name')}",
        f"- 研究问题：{project.get('research_question')}",
        f"- Pipeline run_id：`{run.get('run_id')}`",
        f"- pipeline_run_pk：`{run_pk}`",
        f"- 运行状态：{run.get('status')}，耗时 {run.get('total_duration_ms')} ms",
        f"- 模型：{', '.join(models) or '（见各阶段 JSON）'}（经阿里云百炼 / Qwen）",
        f"- 报告 ID：`{(report_d or {}).get('id')}`",
        f"- 报告标题：{(report_d or {}).get('title')}",
        "",
        "## 说明",
        "- 本目录为**演示用冻结件**，对应云端最新完整跑通的康养项目。",
        "- `文献/` 子目录保留用户已放的参考 PDF/文档，不被本脚本覆盖。",
        "- 目录布局对齐 `sjtu_q_087人工智能能否取代医生/`（00–09 + MANIFEST + SNAPSHOT）。",
        "",
        "## 输入侧要点",
        f"- 研究对象：{pu.get('research_object')}",
        f"- 主要矛盾：{pu.get('main_contradiction')}",
        f"- 知识缺口数：{len(kg.get('knowledge_gaps') or [])}",
        f"- 事实白名单：{len(lm.get('facts') or [])} 条；证据 {len(lm.get('evidence') or [])}；来源论文 {len(lm.get('source_papers') or [])}",
        f"- 约束：{project.get('constraints')}",
        "",
        "## 输出侧 — 假设",
    ]
    for i, h in enumerate(hyps, 1):
        lines.append(f"### H-{i:02d} status={h.get('status')} evidence_level={h.get('evidence_level')}")
        lines.append(f"- 陈述：{h.get('hypothesis')}")
        lines.append(f"- 依据 fact_ids：{h.get('supporting_fact_ids')}")
        lines.append(f"- 可检验性：{h.get('testability')}")
        lines.append(f"- 风险：{h.get('risk')}")
        lines.append("")
    lines += [
        "## 评审",
        f"- ensemble_decision：{hr.get('ensemble_decision')} overall={hr.get('ensemble_overall')} primary_index={hr.get('primary_index')}",
        f"- weaknesses：{(ens or {}).get('weaknesses') if isinstance(ens, dict) else None}",
        "",
        "## 文件清单",
        "- `00_project.json` 项目主数据",
        "- `01_pipeline_run.json` 运行记录",
        "- `02_stages/` 七阶段输出",
        "- `03_hypotheses.json` 假设",
        "- `04_evidences.json` 证据表",
        "- `05_documents.json` 入库文献",
        "- `06_coordinator_advice.json` 大家长提示",
        "- `07_run_extra_metadata.json` 闭环事件 / 门禁 / HITL",
        "- `08_report_meta.json` / `08_report.md` 报告",
        "- `09_iterative_experiments.json` 迭代实验",
        "- `文献/` 演示用外部文献（预置，非本脚本生成）",
        "- `MANIFEST.json` / `DEMO_SNAPSHOT.md`",
    ]
    (OUT / "DEMO_SNAPSHOT.md").write_text("\n".join(lines), encoding="utf-8")

    readme = f"""# 视频-项目演示输入输出（联邦智慧康养）

> 本目录为赛道一方向 1 **项目演示视频**对照材料，结构对齐 `sjtu_q_087人工智能能否取代医生/`。
> 数据来自本地 SQLite 冻结：项目 `{pid}`，run `{run.get('run_id')}`。

## 一、案例概况

| 项 | 值 |
|---|---|
| 演示主题 | 联邦智慧康养 · 合成数据补充跌倒危险样本的挑战 |
| 项目 ID | `{pid}`（status={project.get('status')}） |
| run_id | `{run.get('run_id')}` |
| 模型 | {', '.join(models) or '见阶段 JSON'}（Qwen / 阿里云百炼） |
| 假设数 | {len(hyps)} |
| 证据数 | {len(evidences)} |
| 文献数 | {len(docs)} |
| 报告 | {(report_d or {}).get('title')} |

## 二、目录结构

```
视频-项目演示输入输出/
├── 00_project.json
├── 01_pipeline_run.json
├── 02_stages/          # 01 问题理解 → 07 报告生成
├── 03_hypotheses.json
├── 04_evidences.json
├── 05_documents.json
├── 06_coordinator_advice.json
├── 07_run_extra_metadata.json
├── 08_report_meta.json / 08_report.md
├── 09_iterative_experiments.json
├── 文献/               # 预置参考 PDF/文档
├── MANIFEST.json
├── DEMO_SNAPSHOT.md
└── README.md
```

## 三、复现冻结

```bash
python scripts/freeze_video_demo_case.py
```
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    manifest = {
        "case_id": "video_demo_kangyang",
        "title": "联邦智慧康养-合成数据跌倒检测",
        "purpose": "视频项目演示输入输出",
        "round": 1,
        "frozen_at": frozen_at,
        "project_id": pid,
        "run_id": run.get("run_id"),
        "pipeline_run_pk": run_pk,
        "report_id": (report_d or {}).get("id"),
        "hypothesis_count": len(hyps),
        "evidence_count": len(evidences),
        "document_count": len(docs),
        "stage_count": len(stages),
        "models": models,
        "layout_aligned_with": "sjtu_q_087人工智能能否取代医生",
        "note": "Demo freeze for video I/O. Preserves 文献/ subdirectory.",
    }
    write(OUT / "MANIFEST.json", manifest)
    print(dumps(manifest))
    print("OUT", OUT)


if __name__ == "__main__":
    main()
