#!/usr/bin/env python3
"""
评分表生成与报告打分 — 简易 Web 界面

启动:
  cd web
  pip install -r requirements.txt
  uvicorn app:app --reload --host 127.0.0.1 --port 8765

环境变量 DASHSCOPE_API_KEY 或在页面中填写 API Key。
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from jobs import JobManager
from runner import ALLOWED_SUFFIXES, PACKAGES, REPORT_SUFFIXES, resolve_task_type, scores_output_path

APP_DIR = Path(__file__).resolve().parent
WORK_DIR = APP_DIR / "_jobs"
WORK_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Rubric Generator", docs_url=None, redoc_url=None)
job_manager = JobManager(WORK_DIR)


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(INDEX_HTML)


@app.post("/api/generate")
async def api_generate(
    task_type: str = Form(...),
    query: str = Form(""),
    api_key: str = Form(""),
    files: list[UploadFile] = File(...),
):
    if task_type not in PACKAGES:
        raise HTTPException(400, "请选择有效的报告类型")

    if not files:
        raise HTTPException(400, "请上传至少一个源文件")

    job_id = uuid.uuid4().hex[:12]
    job_dir = WORK_DIR / job_id
    source_dir = job_dir / "sources"
    output_dir = job_dir / "output"
    source_dir.mkdir(parents=True)

    saved = 0
    try:
        for f in files:
            if not f.filename:
                continue
            suffix = Path(f.filename).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise HTTPException(
                    400,
                    f"不支持的文件类型: {f.filename}（支持 PDF / CSV / MD / TXT）",
                )
            dest = source_dir / Path(f.filename).name
            content = await f.read()
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(400, f"文件过大: {f.filename}（上限 50MB）")
            dest.write_bytes(content)
            saved += 1

        if saved == 0:
            raise HTTPException(400, "没有有效的上传文件")

        job_manager.start_generate(
            job_id=job_id,
            task_type=task_type,
            query=query.strip(),
            source_dir=source_dir,
            output_dir=output_dir,
            api_key=api_key.strip(),
        )

        return {
            "ok": True,
            "job_id": job_id,
            "job_mode": "generate",
            "task_type": task_type,
            "label": PACKAGES[task_type]["label"],
            "file_count": saved,
            "status_url": f"/api/status/{job_id}",
        }
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(500, str(e)) from e


@app.post("/api/score")
async def api_score(
    task_file: UploadFile = File(...),
    report_file: UploadFile = File(...),
    api_key: str = Form(""),
    max_report_chars: int = Form(0),
    source_files: list[UploadFile] | None = File(None),
):
    if not task_file.filename:
        raise HTTPException(400, "请上传 task.json")
    if not report_file.filename:
        raise HTTPException(400, "请上传待评报告")

    task_suffix = Path(task_file.filename).suffix.lower()
    if task_suffix != ".json":
        raise HTTPException(400, "评分表文件须为 task.json")

    report_suffix = Path(report_file.filename).suffix.lower()
    if report_suffix not in REPORT_SUFFIXES:
        raise HTTPException(
            400,
            f"报告格式不支持: {report_file.filename}（支持 MD / TXT / PDF）",
        )

    job_id = uuid.uuid4().hex[:12]
    job_dir = WORK_DIR / job_id
    input_dir = job_dir / "input"
    source_dir = job_dir / "sources"
    output_dir = job_dir / "output"
    input_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)

    try:
        task_bytes = await task_file.read()
        if len(task_bytes) > 10 * 1024 * 1024:
            raise HTTPException(400, "task.json 过大（上限 10MB）")
        try:
            task_data = json.loads(task_bytes.decode("utf-8-sig"))
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"task.json 格式无效: {e}") from e

        task_type = resolve_task_type(task_data)
        task_path = input_dir / "task.json"
        task_path.write_bytes(task_bytes)

        report_bytes = await report_file.read()
        if len(report_bytes) > 50 * 1024 * 1024:
            raise HTTPException(400, "报告文件过大（上限 50MB）")
        report_path = input_dir / f"report{report_suffix}"
        report_path.write_bytes(report_bytes)

        saved_sources = 0
        for f in source_files or []:
            if not f.filename:
                continue
            suffix = Path(f.filename).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise HTTPException(
                    400,
                    f"源文件类型不支持: {f.filename}",
                )
            content = await f.read()
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(400, f"源文件过大: {f.filename}")
            (source_dir / Path(f.filename).name).write_bytes(content)
            saved_sources += 1

        job_manager.start_score(
            job_id=job_id,
            task_type=task_type,
            task_path=task_path,
            report_path=report_path,
            output_dir=output_dir,
            source_dir=source_dir if saved_sources > 0 else None,
            api_key=api_key.strip(),
            max_report_chars=max(0, max_report_chars),
        )

        return {
            "ok": True,
            "job_id": job_id,
            "job_mode": "score",
            "task_type": task_type,
            "label": PACKAGES[task_type]["label"],
            "source_file_count": saved_sources,
            "status_url": f"/api/status/{job_id}",
        }
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except ValueError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(500, str(e)) from e


@app.post("/api/impact")
async def api_impact(
    files: list[UploadFile] = File(...),
    api_key: str = Form(""),
    task_lit: UploadFile | None = None,
    scores_lit: UploadFile | None = None,
    task_data: UploadFile | None = None,
    scores_data: UploadFile | None = None,
    task_claim: UploadFile | None = None,
    scores_claim: UploadFile | None = None,
):
    job_id = uuid.uuid4().hex[:12]
    job_dir = WORK_DIR / job_id
    source_dir = job_dir / "sources"
    output_dir = job_dir / "output"
    source_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    pdf_saved = 0
    try:
        # 1) 只处理 PDF 文件（files 列表）
        for f in files:
            if not f.filename:
                continue
            suffix = Path(f.filename).suffix.lower()
            if suffix != ".pdf":
                continue
            content = await f.read()
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(400, f"文件过大: {f.filename}（上限 50MB）")
            dest = source_dir / Path(f.filename).name
            dest.write_bytes(content)
            pdf_saved += 1

        if pdf_saved == 0:
            raise HTTPException(400, "请上传至少一个 PDF 文件")

        # 整理已上传的评分表
        preloaded: dict[str, dict[str, Path | None]] = {
            "literature_review": {"task": None, "scores": None},
            "data_analysis": {"task": None, "scores": None},
            "claim_verification": {"task": None, "scores": None},
        }

        # 按前端字段名直接分类（最可靠）
        field_map = {
            "task_lit": ("literature_review", "task"),
            "scores_lit": ("literature_review", "scores"),
            "task_data": ("data_analysis", "task"),
            "scores_data": ("data_analysis", "scores"),
            "task_claim": ("claim_verification", "task"),
            "scores_claim": ("claim_verification", "scores"),
        }

        # 前端明确命名的文件（task_lit, scores_lit 等）
        named_files = {
            "task_lit": task_lit, "scores_lit": scores_lit,
            "task_data": task_data, "scores_data": scores_data,
            "task_claim": task_claim, "scores_claim": scores_claim,
        }
        for field_name, upload in named_files.items():
            if upload is None:
                continue
            tt, role = field_map[field_name]
            # 用 field_name 作为唯一文件名（避免 task.json 互相覆盖）
            dest = source_dir / f"{field_name}.json"
            content = await upload.read()
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(400, f"文件过大: {upload.filename}（上限 50MB）")
            dest.write_bytes(content)
            preloaded[tt][role] = dest

        job_manager.start_impact(
            job_id=job_id,
            source_dir=source_dir,
            output_dir=output_dir,
            api_key=api_key.strip(),
            preloaded_rubrics=preloaded,
        )

        return {
            "ok": True,
            "job_id": job_id,
            "job_mode": "impact",
            "file_count": pdf_saved,
            "status_url": f"/api/status/{job_id}",
        }
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(500, str(e)) from e


@app.get("/api/status/{job_id}")
async def api_status(job_id: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")

    data = job_manager.read_status(job_id)
    if data is None:
        raise HTTPException(404, "任务不存在或已过期")

    return data


@app.get("/api/download/{job_id}")
async def download_task(job_id: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")

    task_path = WORK_DIR / job_id / "output" / "task.json"
    if not task_path.exists():
        raise HTTPException(404, "文件不存在或已过期，请重新生成")

    return FileResponse(
        task_path,
        media_type="application/json",
        filename="task.json",
    )


@app.get("/api/download/{job_id}/scores")
async def download_scores(job_id: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")

    status = job_manager.read_status(job_id)
    if status is None:
        raise HTTPException(404, "任务不存在或已过期")

    task_type = status.get("task_type", "claim_verification")
    scores_path = scores_output_path(task_type, WORK_DIR / job_id / "output")
    if not scores_path.exists():
        raise HTTPException(404, "评分结果不存在或尚未完成")

    return FileResponse(
        scores_path,
        media_type="application/json",
        filename="rubric_scores.json",
    )


@app.get("/api/download/{job_id}/impact")
async def download_impact(job_id: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")

    impact_path = WORK_DIR / job_id / "output" / "impact_report.json"
    if not impact_path.exists():
        raise HTTPException(404, "影响力报告不存在或尚未完成")

    return FileResponse(
        impact_path,
        media_type="application/json",
        filename="impact_report.json",
    )


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>评分表工具</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
      max-width: 580px; margin: 48px auto; padding: 0 20px;
      color: #1a1a1a; line-height: 1.5;
    }
    h1 { font-size: 1.35rem; font-weight: 600; margin: 0 0 6px; }
    .sub { color: #666; font-size: 0.875rem; margin-bottom: 20px; }
    .tabs { display: flex; gap: 8px; margin-bottom: 24px; }
    .tab {
      flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 8px;
      background: #fafafa; font-size: 0.875rem; font-weight: 500; cursor: pointer; text-align: center;
    }
    .tab.active { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
    .panel { display: none; }
    .panel.active { display: block; }
    label { display: block; font-size: 0.8125rem; font-weight: 500; margin-bottom: 6px; color: #444; }
    select, textarea, input[type="password"], input[type="file"], input[type="number"], input[type="text"] {
      width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px;
      font-size: 0.9375rem; margin-bottom: 18px; background: #fff;
    }
    textarea { min-height: 100px; resize: vertical; }
    select:focus, textarea:focus, input:focus { outline: none; border-color: #333; }
    .hint { font-size: 0.75rem; color: #888; margin: -12px 0 18px; }
    button[type="submit"] {
      width: 100%; padding: 12px; border: none; border-radius: 8px;
      background: #1a1a1a; color: #fff; font-size: 0.9375rem; font-weight: 500;
      cursor: pointer;
    }
    button[type="submit"]:hover:not(:disabled) { background: #333; }
    button[type="submit"]:disabled { opacity: 0.5; cursor: not-allowed; }
    #status {
      margin-top: 20px; padding: 14px; border-radius: 8px; font-size: 0.875rem;
      display: none;
    }
    #status.info { display: block; background: #f5f5f5; color: #444; }
    #status.error { display: block; background: #fef2f2; color: #b91c1c; }
    #status.ok { display: block; background: #f0fdf4; color: #166534; }
    #status a { color: #166534; font-weight: 600; }
    .progress-wrap {
      height: 6px; background: #e5e5e5; border-radius: 3px; margin: 10px 0 8px; overflow: hidden;
    }
    .progress-bar {
      height: 100%; background: #1a1a1a; border-radius: 3px;
      width: 0%; transition: width 0.4s ease;
    }
    .progress-meta {
      display: flex; justify-content: space-between; font-size: 0.75rem; color: #666;
    }
    .log-box {
      margin-top: 10px; max-height: 140px; overflow-y: auto;
      background: #fff; border: 1px solid #e5e5e5; border-radius: 6px;
      padding: 8px 10px; font-family: ui-monospace, Consolas, monospace;
      font-size: 0.6875rem; line-height: 1.45; color: #555;
    }
    .log-box:empty { display: none; }
    .opt-api { margin-bottom: 18px; }
    .opt-api summary { cursor: pointer; font-size: 0.8125rem; color: #666; }
    .opt-api[open] summary { margin-bottom: 8px; }
  </style>
</head>
<body>
  <h1>评分表工具</h1>
  <p class="sub">生成领域评分表，或对已有报告自动打分</p>

  <div class="tabs">
    <button type="button" class="tab active" data-tab="generate">生成评分表</button>
    <button type="button" class="tab" data-tab="score">报告打分</button>
    <button type="button" class="tab" data-tab="impact">科学影响力预测</button>
  </div>

  <div id="panel-generate" class="panel active">
    <form id="form-generate">
      <label for="task_type">报告类型</label>
      <select id="task_type" name="task_type" required>
        <option value="claim_verification">主张核查 — 论文 PDF</option>
        <option value="data_analysis">数据分析 — PDF / CSV / MD</option>
        <option value="literature_review">科学调研 — 综述 PDF / MD</option>
      </select>

      <label for="files">上传文献 / 数据文件</label>
      <input id="files" name="files" type="file" multiple accept=".pdf,.csv,.md,.txt" required />
      <p class="hint" id="file-count-gen"></p>

      <details class="opt-api">
        <summary>补充说明（可选）</summary>
        <textarea id="query" name="query" placeholder="留空则根据文献自动生成研究问题" style="min-height:72px;margin-top:8px;"></textarea>
      </details>

      <details class="opt-api">
        <summary>API Key（可选）</summary>
        <input type="password" id="api_key_gen" name="api_key" placeholder="DASHSCOPE_API_KEY" autocomplete="off" />
      </details>

      <button type="submit" id="btn-generate">生成评分表</button>
    </form>
  </div>

  <div id="panel-score" class="panel">
    <form id="form-score">
      <label for="task_file">评分表 task.json</label>
      <input id="task_file" name="task_file" type="file" accept=".json,application/json" required />
      <p class="hint">须含 task_type 字段；系统自动选择对应生成器</p>

      <label for="report_file">待评报告</label>
      <input id="report_file" name="report_file" type="file" accept=".md,.txt,.pdf" required />
      <p class="hint">支持 Markdown / TXT / PDF</p>

      <label for="source_files">源文献（可选，辅助 source 引用评分）</label>
      <input id="source_files" name="source_files" type="file" multiple accept=".pdf,.csv,.md,.txt" />
      <p class="hint" id="file-count-score"></p>

      <details class="opt-api">
        <summary>高级选项</summary>
        <label for="max_report_chars" style="margin-top:8px;">报告截断上限（字符，0=默认 20000）</label>
        <input type="number" id="max_report_chars" name="max_report_chars" min="0" max="100000" value="0" />
        <input type="password" id="api_key_score" name="api_key" placeholder="DASHSCOPE_API_KEY" autocomplete="off" style="margin-top:8px;" />
      </details>

      <button type="submit" id="btn-score">开始打分</button>
    </form>
  </div>

  <div id="panel-impact" class="panel">
    <form id="form-impact">
      <label for="impact_files">上传论文 PDF（必需）</label>
      <input id="impact_files" name="files" type="file" accept=".pdf" required />
      <p class="hint" id="file-count-impact"></p>

      <div style="margin:16px 0;padding:12px 14px;background:#f8f9fa;border:1px solid #e5e5e5;border-radius:8px;">
        <div style="font-weight:600;margin-bottom:8px;font-size:0.9rem;">评分表（可选）</div>
        <div style="font-size:0.78rem;color:#666;margin-bottom:10px;">未上传的评分表将自动生成。若已打分，请同时上传 task.json 和 rubric_scores.json。</div>

        <div style="margin-bottom:10px;">
          <label for="impact_task_lit" style="font-size:0.8125rem;">科学调研报告 — task.json</label>
          <input id="impact_task_lit" name="task_lit" type="file" accept=".json" />
          <label for="impact_scores_lit" style="font-size:0.8125rem;margin-top:4px;">科学调研报告 — rubric_scores.json（已打分则上传）</label>
          <input id="impact_scores_lit" name="scores_lit" type="file" accept=".json" />
        </div>

        <div style="margin-bottom:10px;">
          <label for="impact_task_data" style="font-size:0.8125rem;">数据分析报告 — task.json</label>
          <input id="impact_task_data" name="task_data" type="file" accept=".json" />
          <label for="impact_scores_data" style="font-size:0.8125rem;margin-top:4px;">数据分析报告 — rubric_scores.json（已打分则上传）</label>
          <input id="impact_scores_data" name="scores_data" type="file" accept=".json" />
        </div>

        <div>
          <label for="impact_task_claim" style="font-size:0.8125rem;">主张核查报告 — task.json</label>
          <input id="impact_task_claim" name="task_claim" type="file" accept=".json" />
          <label for="impact_scores_claim" style="font-size:0.8125rem;margin-top:4px;">主张核查报告 — rubric_scores.json（已打分则上传）</label>
          <input id="impact_scores_claim" name="scores_claim" type="file" accept=".json" />
        </div>
      </div>

      <details class="opt-api">
        <summary>API Key（可选）</summary>
        <input type="password" id="api_key_impact" name="api_key" placeholder="DASHSCOPE_API_KEY" autocomplete="off" />
      </details>

      <button type="submit" id="btn-impact">开始预测</button>
    </form>
  </div>

  <div id="status"></div>

  <script>
    const tabs = document.querySelectorAll(".tab");
    const panels = { generate: document.getElementById("panel-generate"), score: document.getElementById("panel-score"), impact: document.getElementById("panel-impact") };
    const status = document.getElementById("status");
    const btnGenerate = document.getElementById("btn-generate");
    const btnScore = document.getElementById("btn-score");
    const btnImpact = document.getElementById("btn-impact");
    const fileInputGen = document.getElementById("files");
    const fileInputScore = document.getElementById("source_files");
    const fileInputImpact = document.getElementById("impact_files");
    const fileCountGen = document.getElementById("file-count-gen");
    const fileCountScore = document.getElementById("file-count-score");
    const fileCountImpact = document.getElementById("file-count-impact");

    let pollTimer = null;
    let elapsedTimer = null;
    let jobStartedAt = null;
    let activeMode = "generate";

    tabs.forEach(t => t.addEventListener("click", () => {
      activeMode = t.dataset.tab;
      tabs.forEach(x => x.classList.toggle("active", x === t));
      Object.entries(panels).forEach(([k, el]) => el.classList.toggle("active", k === activeMode));
      clearTimers();
      status.style.display = "none";
    }));

    fileInputGen.addEventListener("change", () => {
      fileCountGen.textContent = fileInputGen.files.length ? `已选择 ${fileInputGen.files.length} 个文件` : "";
    });
    fileInputScore.addEventListener("change", () => {
      fileCountScore.textContent = fileInputScore.files.length ? `已选择 ${fileInputScore.files.length} 个源文件` : "";
    });
    fileInputImpact.addEventListener("change", () => {
      fileCountImpact.textContent = fileInputImpact.files.length ? `已选择 ${fileInputImpact.files.length} 个文件` : "";
    });

    function clearTimers() {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
    }

    function formatElapsed(sec) {
      const m = Math.floor(sec / 60);
      const s = sec % 60;
      return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`;
    }

    function renderRunning(data) {
      const pct = data.progress ?? 0;
      const elapsed = data.elapsed_sec ?? (jobStartedAt ? Math.floor((Date.now() - jobStartedAt) / 1000) : 0);
      const logs = (data.logs || []).slice(-12).join("\\n");
      const title = data.mode_label || data.label || "处理中";
      status.className = "info";
      status.style.display = "block";
      status.innerHTML =
        `<div><strong>${title}</strong> — ${data.message || "正在处理…"}</div>` +
        `<div class="progress-wrap"><div class="progress-bar" style="width:${pct}%"></div></div>` +
        `<div class="progress-meta"><span>${pct}%</span><span>已用时 ${formatElapsed(elapsed)}</span></div>` +
        (logs ? `<div class="log-box">${logs.replace(/</g, "&lt;")}</div>` : "");
      const logBox = status.querySelector(".log-box");
      if (logBox) logBox.scrollTop = logBox.scrollHeight;
    }

    function renderDone(data) {
      clearTimers();
      status.className = "ok";
      if (data.job_mode === "score") {
        status.innerHTML =
          `<div><strong>评分完成</strong>：${data.label}，` +
          `${data.raw_score}/${data.total_score}（${data.score_percentage}%）` +
          (data.elapsed_sec ? `，用时 ${formatElapsed(data.elapsed_sec)}` : "") +
          `</div>` +
          `<div style="margin-top:8px"><a href="${data.download_url}" download="rubric_scores.json">下载 rubric_scores.json</a></div>`;
      } else if (data.job_mode === "impact") {
        const rating = data.rating || {};
        const totalScore = data.total_score ?? 0;
        const meta = data.metadata_summary || {};
        const title = meta.title || "未知标题";
        const venue = meta.venue || "";
        const year = meta.year || "";
        const citations = meta.citations ?? "";
        const bias = data.bias_explanation || null;
        const cq = data.content_quality || {};

        let metaParts = [];
        if (venue) metaParts.push(venue);
        if (year) metaParts.push(year + " 年");
        if (citations !== "") metaParts.push("被引 " + citations + " 次");

        // 构建内容质量详情
        let contentHtml = "";
        if (cq.details && cq.details.length) {
          contentHtml = `<div style="margin:8px 0;padding:8px 12px;background:#fff;border:1px solid #e5e5e5;border-radius:6px;font-size:0.8125rem;">`;
          contentHtml += `<div style="font-weight:600;margin-bottom:4px;">内容质量评分（取最高项 × 50%）</div>`;
          contentHtml += `<div style="color:#333;font-weight:600;">最高项: ${cq.best_pct ?? "?"}%</div>`;
          contentHtml += `<div style="margin-top:4px;">`;
          for (const d of cq.details) {
            const isBest = (d.score_percentage === cq.best_pct);
            contentHtml += `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #f0f0f0;${isBest ? 'color:#1565c0;' : ''}">`;
            contentHtml += `<span>${isBest ? '★ ' : ''}${d.label || d.task_type}</span>`;
            contentHtml += `<span style="font-weight:600;">${d.raw_score}/${d.total_score} (${d.score_percentage}%)</span>`;
            contentHtml += `</div>`;
          }
          contentHtml += `</div></div>`;
        }

        // 构建影响力详情
        let impactPts = data.impact_score ?? "?";
        let impactMax = data.impact_max || 30;
        let impactPct = impactPts !== "?" ? (impactPts / impactMax * 100).toFixed(1) : "?";
        let impactHtml = `<div style="margin:8px 0;padding:8px 12px;background:#fff;border:1px solid #e5e5e5;border-radius:6px;font-size:0.8125rem;">`;
        impactHtml += `<div style="font-weight:600;margin-bottom:4px;">影响力评估（× 50%）</div>`;
        impactHtml += `<span style="font-weight:600;">${impactPts} / ${impactMax} (${impactPct}%)</span>`;
        impactHtml += `</div>`;

        // 构建偏差解释 HTML
        let biasHtml = "";
        if (bias) {
          biasHtml = `<div style="margin:14px 0;padding:12px 14px;background:#f8f9fa;border:1px solid #e5e5e5;border-radius:8px;">` +
            `<div style="font-weight:600;margin-bottom:8px;font-size:0.95rem;">偏差解释</div>`;

          // 现状诊断
          if (bias.current_assessment) {
            biasHtml += `<div style="margin-bottom:10px;font-size:0.8125rem;color:#333;line-height:1.5;">${bias.current_assessment.replace(/</g, "&lt;")}</div>`;
          }

          // 偏低误差分析
          if (bias.underestimation_bias && bias.underestimation_bias.length) {
            biasHtml += `<div style="font-weight:600;margin:8px 0 4px;font-size:0.8125rem;color:#1565c0;">偏低误差 — 得分可能低估了实际影响力</div>`;
            biasHtml += `<div style="font-size:0.8125rem;color:#444;">`;
            for (const item of bias.underestimation_bias) {
              const dim = item.dimension || "";
              const score = item.current_score || "?/?";
              const reason = item.score_may_be_low_because || "";
              const evidence = item.evidence || "";
              const estRange = item.estimated_true_range || "";
              biasHtml += `<div style="margin-bottom:6px;padding-left:12px;border-left:2px solid #1565c0;">`;
              biasHtml += `<div><strong>${dim}</strong> (${score})</div>`;
              biasHtml += `<div style="color:#555;">原因: ${reason.replace(/</g, "&lt;")}</div>`;
              if (evidence) biasHtml += `<div style="color:#666;font-size:0.78rem;">证据: ${evidence.replace(/</g, "&lt;")}</div>`;
              if (estRange) biasHtml += `<div style="color:#1565c0;font-size:0.78rem;">估计真实范围: ${estRange}</div>`;
              biasHtml += `</div>`;
            }
            biasHtml += `</div>`;
          }

          // 偏高误差分析
          if (bias.overestimation_bias && bias.overestimation_bias.length) {
            biasHtml += `<div style="font-weight:600;margin:8px 0 4px;font-size:0.8125rem;color:#c62828;">偏高误差 — 得分可能高估了实际影响力</div>`;
            biasHtml += `<div style="font-size:0.8125rem;color:#444;">`;
            for (const item of bias.overestimation_bias) {
              const dim = item.dimension || "";
              const score = item.current_score || "?/?";
              const reason = item.score_may_be_high_because || "";
              const evidence = item.evidence || "";
              const risk = item.risk_level || "Medium";
              biasHtml += `<div style="margin-bottom:6px;padding-left:12px;border-left:2px solid #c62828;">`;
              biasHtml += `<div><strong>${dim}</strong> (${score}) <span style="color:#c62828;font-size:0.78rem;">[风险: ${risk}]</span></div>`;
              biasHtml += `<div style="color:#555;">原因: ${reason.replace(/</g, "&lt;")}</div>`;
              if (evidence) biasHtml += `<div style="color:#666;font-size:0.78rem;">证据: ${evidence.replace(/</g, "&lt;")}</div>`;
              biasHtml += `</div>`;
            }
            biasHtml += `</div>`;
          }

          // 提升路径（基于评分标准档位）
          if (bias.improvement_path && bias.improvement_path.length) {
            biasHtml += `<div style="font-weight:600;margin:8px 0 4px;font-size:0.8125rem;color:#2e7d32;">提升路径</div>`;
            biasHtml += `<div style="font-size:0.8125rem;color:#444;">`;
            for (const item of bias.improvement_path) {
              const dim = item.dimension || "";
              const cur = item.current_score || "?/?";
              const curTier = item.current_rubric_tier || "";
              const nextTier = item.next_tier || "";
              const gap = item.gap_to_close || "";
              const real = item.realistic ? "可行" : "不确定";
              biasHtml += `<div style="margin-bottom:6px;padding-left:12px;border-left:2px solid #2e7d32;">`;
              biasHtml += `<div><strong>${dim}</strong> (${cur})</div>`;
              if (curTier) biasHtml += `<div style="color:#666;font-size:0.78rem;">当前档位: ${curTier.replace(/</g, "&lt;")}</div>`;
              if (nextTier) biasHtml += `<div style="color:#2e7d32;font-size:0.78rem;">下一档位: ${nextTier.replace(/</g, "&lt;")}</div>`;
              if (gap) biasHtml += `<div>差距: ${gap.replace(/</g, "&lt;")} (${real})</div>`;
              biasHtml += `</div>`;
            }
            biasHtml += `</div>`;
          }

          // 下降风险（基于评分标准档位）
          if (bias.decline_risks && bias.decline_risks.length) {
            biasHtml += `<div style="font-weight:600;margin:8px 0 4px;font-size:0.8125rem;color:#c62828;">下降风险</div>`;
            biasHtml += `<div style="font-size:0.8125rem;color:#444;">`;
            for (const item of bias.decline_risks) {
              const dim = item.dimension || "";
              const cur = item.current_score || "?/?";
              const curTier = item.current_rubric_tier || "";
              const dropTier = item.risk_drop_to_tier || "";
              const trigger = item.trigger || "";
              const sev = item.severity || "Medium";
              biasHtml += `<div style="margin-bottom:6px;padding-left:12px;border-left:2px solid #c62828;">`;
              biasHtml += `<div><strong>${dim}</strong> (${cur}) <span style="color:#c62828;font-size:0.78rem;">[风险: ${sev}]</span></div>`;
              if (curTier) biasHtml += `<div style="color:#666;font-size:0.78rem;">当前档位: ${curTier.replace(/</g, "&lt;")}</div>`;
              if (dropTier) biasHtml += `<div style="color:#c62828;font-size:0.78rem;">可能跌至: ${dropTier.replace(/</g, "&lt;")}</div>`;
              if (trigger) biasHtml += `<div>触发条件: ${trigger.replace(/</g, "&lt;")}</div>`;
              biasHtml += `</div>`;
            }
            biasHtml += `</div>`;
          }

          // 依据声明
          if (bias.data_reliability) {
            const dr = bias.data_reliability;
            biasHtml += `<div style="font-weight:600;margin:8px 0 4px;font-size:0.8125rem;color:#555;">依据声明</div>`;
            biasHtml += `<div style="font-size:0.78rem;color:#666;">`;
            if (dr.verified_claims && dr.verified_claims.length) {
              for (const c of dr.verified_claims) {
                biasHtml += `<div>✓ ${c.replace(/</g, "&lt;")}</div>`;
              }
            }
            if (dr.inferred_claims && dr.inferred_claims.length) {
              for (const c of dr.inferred_claims) {
                biasHtml += `<div>~ ${c.replace(/</g, "&lt;")}</div>`;
              }
            }
            if (dr.missing_data && dr.missing_data.length) {
              for (const c of dr.missing_data) {
                biasHtml += `<div>? ${c.replace(/</g, "&lt;")}</div>`;
              }
            }
            biasHtml += `</div>`;
          }

          biasHtml += `</div>`;
        }

        status.innerHTML =
          `<div><strong>预测完成</strong>` +
          (data.elapsed_sec ? `（用时 ${formatElapsed(data.elapsed_sec)}）` : "") +
          `</div>` +
          `<div style="margin:10px 0;padding:10px 14px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;">` +
            `<div style="font-size:1.1rem;font-weight:600;margin-bottom:6px;">` +
              `<span style="display:inline-block;padding:3px 10px;border-radius:6px;background:#1a1a1a;color:#fff;font-size:1rem;font-weight:700;margin-right:8px;">${rating.rating || "N/A"}</span>` +
              `总分 ${totalScore}%` +
              `<span style="color:#888;font-weight:400;">（${rating.rating_label || ""}）</span>` +
            `</div>` +
            `<div style="font-size:0.8125rem;color:#555;margin-top:6px;">` +
              `<div><strong>${title.replace(/</g, "&lt;")}</strong></div>` +
              (metaParts.length ? `<div style="margin-top:2px;color:#777;">${metaParts.join("  ·  ")}</div>` : "") +
            `</div>` +
          `</div>` +
          contentHtml +
          impactHtml +
          biasHtml +
          `<div style="margin-top:8px"><a href="${data.download_url}" download="impact_report.json">下载 impact_report.json</a></div>`;
      } else {
        status.innerHTML =
          `<div><strong>生成完成</strong>：${data.label}，共 ${data.item_count} 项，${data.total_score} 分` +
          (data.elapsed_sec ? `（用时 ${formatElapsed(data.elapsed_sec)}）` : "") +
          `</div>` +
          `<div style="margin-top:8px"><a href="${data.download_url}" download="task.json">下载 task.json</a></div>`;
      }
    }

    function renderError(msg) {
      clearTimers();
      status.className = "error";
      status.textContent = msg;
    }

    function setButtonsDisabled(disabled) {
      btnGenerate.disabled = disabled;
      btnScore.disabled = disabled;
      btnImpact.disabled = disabled;
    }

    async function pollStatus(jobId) {
      try {
        const res = await fetch(`/api/status/${jobId}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || res.statusText || "获取状态失败");

        if (data.status === "completed") {
          renderDone(data);
          setButtonsDisabled(false);
          return;
        }
        if (data.status === "failed") {
          renderError(data.error || data.message || "任务失败");
          setButtonsDisabled(false);
          return;
        }
        renderRunning(data);
      } catch (err) {
        renderError(err.message || String(err));
        setButtonsDisabled(false);
      }
    }

    async function submitJob(url, formData, label, hint) {
      clearTimers();
      setButtonsDisabled(true);
      jobStartedAt = Date.now();

      status.className = "info";
      status.style.display = "block";
      status.innerHTML =
        `<div><strong>准备中</strong> — ${hint}</div>` +
        `<div class="progress-wrap"><div class="progress-bar" style="width:2%"></div></div>` +
        `<div class="progress-meta"><span>2%</span><span>已用时 0 秒</span></div>`;

      try {
        const res = await fetch(url, { method: "POST", body: formData });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || res.statusText || "提交失败");

        renderRunning({
          job_mode: data.job_mode,
          mode_label: data.job_mode === "score" ? "报告打分" : data.job_mode === "impact" ? "科学影响力预测" : "生成评分表",
          label: data.label,
          message: data.job_mode === "score" ? "任务已提交，正在逐条评分…" : data.job_mode === "impact" ? "任务已提交，正在分析论文影响力…" : "任务已提交，正在生成（通常 3–8 分钟）…",
          progress: 3,
          logs: [],
        });

        pollTimer = setInterval(() => pollStatus(data.job_id), 2000);
        elapsedTimer = setInterval(() => {
          const bar = status.querySelector(".progress-meta span:last-child");
          if (bar && jobStartedAt) {
            bar.textContent = "已用时 " + formatElapsed(Math.floor((Date.now() - jobStartedAt) / 1000));
          }
        }, 1000);
        await pollStatus(data.job_id);
      } catch (err) {
        renderError(err.message || String(err));
        setButtonsDisabled(false);
      }
    }

    document.getElementById("form-generate").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      fd.delete("files");
      for (const f of fileInputGen.files) fd.append("files", f);
      await submitJob("/api/generate", fd, "generate", `正在上传 ${fileInputGen.files.length} 个文件…`);
    });

    document.getElementById("form-score").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData();
      fd.append("task_file", document.getElementById("task_file").files[0]);
      fd.append("report_file", document.getElementById("report_file").files[0]);
      const maxChars = document.getElementById("max_report_chars").value || "0";
      fd.append("max_report_chars", maxChars);
      const apiKey = document.getElementById("api_key_score").value;
      if (apiKey) fd.append("api_key", apiKey);
      for (const f of fileInputScore.files) fd.append("source_files", f);
      await submitJob("/api/score", fd, "score", "正在上传评分表与报告…");
    });

    document.getElementById("form-impact").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      fd.delete("files");
      for (const f of fileInputImpact.files) fd.append("files", f);
      // 收集评分表文件
      const taskLit = document.getElementById("impact_task_lit").files[0];
      const scoresLit = document.getElementById("impact_scores_lit").files[0];
      const taskData = document.getElementById("impact_task_data").files[0];
      const scoresData = document.getElementById("impact_scores_data").files[0];
      const taskClaim = document.getElementById("impact_task_claim").files[0];
      const scoresClaim = document.getElementById("impact_scores_claim").files[0];
      if (taskLit) fd.append("task_lit", taskLit);
      if (scoresLit) fd.append("scores_lit", scoresLit);
      if (taskData) fd.append("task_data", taskData);
      if (scoresData) fd.append("scores_data", scoresData);
      if (taskClaim) fd.append("task_claim", taskClaim);
      if (scoresClaim) fd.append("scores_claim", scoresClaim);
      const apiKey = document.getElementById("api_key_impact").value;
      if (apiKey) fd.set("api_key", apiKey);
      await submitJob("/api/impact", fd, "impact", `正在上传 ${fileInputImpact.files.length} 个 PDF…`);
    });
  </script>
</body>
</html>
"""
