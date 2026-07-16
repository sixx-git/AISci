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
import os
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.composite_scorer import resolve_display_composite_score  # noqa: E402
from jobs import JobManager
from runner import ALLOWED_SUFFIXES, PACKAGES, REPORT_SUFFIXES, resolve_task_type, scores_output_path

APP_DIR = Path(__file__).resolve().parent


def _resolve_work_dir() -> Path:
    """任务落盘目录：优先环境变量，便于 AISci 与独立启动共用同一套历史。"""
    raw = (os.environ.get("PINGFENBIAO_WORK_DIR") or "").strip()
    if raw:
        path = Path(raw).expanduser().resolve()
    else:
        path = APP_DIR / "_jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


WORK_DIR = _resolve_work_dir()

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
    max_report_chars: int = Form(200000),
    source_files: list[UploadFile] | None = File(None),
):
    if not task_file.filename:
        raise HTTPException(400, "请上传 task.json")
    if not report_file.filename:
        raise HTTPException(400, "请上传待评报告")

    # 报告截断上限：默认 200000，允许用户上调
    report_limit = max_report_chars if max_report_chars > 0 else 200000
    if report_limit > 2_000_000:
        raise HTTPException(400, "报告截断上限过大（最大 2000000）")

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
            max_report_chars=report_limit,
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
    max_report_chars: int = Form(200000),
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

    report_limit = max_report_chars if max_report_chars > 0 else 200000
    if report_limit > 2_000_000:
        raise HTTPException(400, "报告截断上限过大（最大 2000000）")

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
            max_report_chars=report_limit,
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


# ── 新增：影响力预测历史与详情 API ──────────────────────────

@app.delete("/api/impact/{job_id}")
async def api_delete_impact(job_id: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")
    job_dir = WORK_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, "任务不存在")
    # 只删除汇总文件，保留文献和评分表
    impact_report = job_dir / "output" / "impact_report.json"
    if impact_report.exists():
        impact_report.unlink()
    status_file = job_dir / "status.json"
    if status_file.exists():
        status_file.unlink()
    return {"ok": True, "job_id": job_id}


@app.get("/api/rubric/{job_id}/{task_type}")
async def api_get_rubric(job_id: str, task_type: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")
    if task_type not in ("literature_review", "data_analysis", "claim_verification"):
        raise HTTPException(400, "无效的任务类型")
    job_dir = WORK_DIR / job_id
    rubric_path = job_dir / "output" / task_type / "task.json"
    if not rubric_path.exists():
        raise HTTPException(404, "评分表不存在")
    return FileResponse(str(rubric_path), media_type="application/json")


@app.get("/api/impact/history")
async def api_impact_history():
    """扫描所有 status.json，返回已完成的 impact 任务列表（按时间倒序）。"""
    results: list[dict] = []
    if not WORK_DIR.exists():
        return results
    for d in sorted(WORK_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        sp = d / "status.json"
        if not sp.exists():
            continue
        try:
            sd = json.loads(sp.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        if sd.get("job_mode") != "impact" or sd.get("status") != "completed":
            continue

        # 优先从 impact_report.json 获取更丰富的元数据
        title = ""
        venue = ""
        year = None
        citations = None
        rp = d / "output" / "impact_report.json"
        if rp.exists():
            try:
                rd = json.loads(rp.read_text(encoding="utf-8-sig"))
                meta = rd.get("metadata") or {}
                title = meta.get("title") or rd.get("title", "")
                venue = meta.get("venue") or meta.get("host_venue", "")
                year = meta.get("year") or meta.get("publication_year")
                citations = meta.get("citations") or meta.get("cited_by_count")
            except (json.JSONDecodeError, OSError):
                pass

        ms = sd.get("metadata_summary") or {}
        if not title:
            title = ms.get("title", "")
        if not venue:
            venue = ms.get("venue", "")
        if year is None:
            year = ms.get("year")
        if citations is None:
            citations = ms.get("citations")

        ri = sd.get("rating") or {}
        # 百分制统一：优先 composite_score，兼容旧 200 分制 total_score / raw
        ts = resolve_display_composite_score(ri, sd.get("total_score"))

        results.append({
            "job_id": sd.get("job_id", d.name),
            "title": title,
            "venue": venue,
            "year": year,
            "rating": ri.get("rating", "N/A"),
            "total_score": ts,
            "citations": citations,
            "completed_at": sd.get("updated_at", ""),
        })
    return results


@app.get("/api/impact/detail/{job_id}")
async def api_impact_detail(job_id: str):
    """读取并返回指定 job 的 impact_report.json 完整数据。"""
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(400, "无效的 job_id")

    report_path = WORK_DIR / job_id / "output" / "impact_report.json"
    if not report_path.exists():
        raise HTTPException(404, "影响力报告不存在")

    try:
        data = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(500, f"读取报告失败: {e}") from e

    return data


# ── 前端页面 ────────────────────────────────────────────────

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>评分表工具</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#1a1a1a;line-height:1.5;background:#f5f5f5}

    /* ── 两栏布局 ── */
    #app-layout{display:flex;min-height:100vh}
    #sidebar{width:250px;background:#1a1a1a;color:#fff;position:fixed;top:0;left:0;bottom:0;display:flex;flex-direction:column;z-index:100}
    #main-content{margin-left:250px;flex:1;min-height:100vh}

    /* ── 侧边栏 ── */
    .sidebar-header{padding:20px 16px 14px;border-bottom:1px solid #333}
    .sidebar-header h2{font-size:.95rem;font-weight:600;color:#eee;letter-spacing:.3px}
    .sidebar-list{flex:1;overflow-y:auto;padding:8px}
    .sidebar-list::-webkit-scrollbar{width:4px}
    .sidebar-list::-webkit-scrollbar-thumb{background:#555;border-radius:2px}
    .sidebar-item{padding:10px 12px;border-radius:6px;cursor:pointer;margin-bottom:4px;transition:background .15s;position:relative}
    .sidebar-item:hover{background:#2a2a2a}
    .sidebar-item.active{background:#333}
    .sidebar-item-title{font-size:.8rem;color:#ddd;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px;padding-right:20px}
    .sidebar-item-meta{display:flex;align-items:center;gap:8px;font-size:.73rem;color:#999}
    .sidebar-item-del{position:absolute;top:6px;right:6px;width:18px;height:18px;border:none;border-radius:50%;background:transparent;color:#666;font-size:11px;line-height:18px;text-align:center;cursor:pointer;padding:0;display:none;transition:all .15s;z-index:5}
    .sidebar-item:hover .sidebar-item-del{display:block}
    .sidebar-item-del:hover{background:#555;color:#fff}
    .sidebar-footer{padding:12px;border-top:1px solid #333}
    #btn-new-impact{width:100%;padding:10px;border:1px solid #555;border-radius:6px;background:transparent;color:#ccc;font-size:.8125rem;cursor:pointer;transition:all .15s}
    #btn-new-impact:hover{background:#333;border-color:#888;color:#fff}
    .sidebar-empty{padding:24px 16px;color:#666;font-size:.8rem;text-align:center;line-height:1.6}
    .sidebar-loading{padding:24px 16px;color:#888;font-size:.8rem;text-align:center}

    /* ── 评级徽章 ── */
    .rb{display:inline-block;padding:1px 8px;border-radius:4px;font-size:.72rem;font-weight:700;color:#fff;line-height:1.6}
    .rb-S{background:#4caf50}.rb-A{background:#2196f3}.rb-A-{background:#00bcd4}
    .rb-B{background:#ff9800}.rb-C{background:#f44336}.rb-D{background:#9e9e9e}.rb-N{background:#666}

    /* ── 主内容区：表单模式 ── */
    #form-area{max-width:640px;margin:0 auto;padding:36px 32px 60px;background:#fff;min-height:100vh}
    .tabs{display:flex;gap:8px;margin-bottom:24px}
    .tab{flex:1;padding:10px;border:1px solid #ddd;border-radius:8px;background:#fafafa;font-size:.85rem;font-weight:500;cursor:pointer;text-align:center}
    .tab.active{background:#1a1a1a;color:#fff;border-color:#1a1a1a}
    .panel{display:none}.panel.active{display:block}
    label{display:block;font-size:.8rem;font-weight:500;margin-bottom:6px;color:#444}
    select,textarea,input[type="password"],input[type="file"],input[type="number"],input[type="text"]{
      width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;font-size:.9rem;margin-bottom:18px;background:#fff}
    textarea{min-height:100px;resize:vertical}
    select:focus,textarea:focus,input:focus{outline:none;border-color:#333}
    .hint{font-size:.74rem;color:#888;margin:-12px 0 18px}
    button[type="submit"]{width:100%;padding:12px;border:none;border-radius:8px;background:#1a1a1a;color:#fff;font-size:.9rem;font-weight:500;cursor:pointer}
    button[type="submit"]:hover:not(:disabled){background:#333}
    button[type="submit"]:disabled{opacity:.5;cursor:not-allowed}
    #status{margin-top:20px;padding:14px;border-radius:8px;font-size:.85rem;display:none}
    #status.info{display:block;background:#f5f5f5;color:#444}
    #status.error{display:block;background:#fef2f2;color:#b91c1c}
    #status.ok{display:block;background:#f0fdf4;color:#166534}
    #status a{color:#166534;font-weight:600}
    .progress-wrap{height:6px;background:#e5e5e5;border-radius:3px;margin:10px 0 8px;overflow:hidden}
    .progress-bar{height:100%;background:#1a1a1a;border-radius:3px;width:0%;transition:width .4s ease}
    .progress-meta{display:flex;justify-content:space-between;font-size:.74rem;color:#666}
    .log-box{margin-top:10px;max-height:140px;overflow-y:auto;background:#fff;border:1px solid #e5e5e5;border-radius:6px;padding:8px 10px;font-family:ui-monospace,Consolas,monospace;font-size:.68rem;line-height:1.45;color:#555}
    .log-box:empty{display:none}
    .opt-api{margin-bottom:18px}
    .opt-api summary{cursor:pointer;font-size:.8rem;color:#666}
    .opt-api[open] summary{margin-bottom:8px}
    .page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:22px}
    .page-header-text{flex:1;min-width:0}
    .page-header h1{font-size:1.3rem;font-weight:600;margin-bottom:4px}
    .page-header .sub{color:#666;font-size:.85rem;margin-bottom:0}
    .global-limit{flex-shrink:0;text-align:right;min-width:180px}
    .global-limit label{display:block;font-size:.72rem;font-weight:500;color:#666;margin-bottom:4px;text-align:right}
    .global-limit input[type=number]{width:160px;padding:8px 10px;border:1px solid #ddd;border-radius:8px;font-size:.85rem;margin-bottom:0;text-align:right}
    .global-limit .hint{margin:4px 0 0;text-align:right}

    /* ── 主内容区：详情模式 ── */
    #detail-area{max-width:860px;margin:0 auto;padding:28px 36px 60px;background:#fff;min-height:100vh;display:none}
    .detail-top-bar{display:flex;align-items:center;gap:12px;margin-bottom:20px}
    .btn-back{padding:6px 14px;border:1px solid #ddd;border-radius:6px;background:#fff;font-size:.82rem;cursor:pointer;color:#444;white-space:nowrap}
    .btn-back:hover{background:#f5f5f5}
    .detail-title{font-size:1.15rem;font-weight:600;flex:1;line-height:1.35}
    .detail-summary{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:20px;padding:16px 18px;background:#fafafa;border:1px solid #eee;border-radius:10px}
    .detail-summary .score-big{font-size:2rem;font-weight:700;color:#1a1a1a}
    .detail-summary .score-label{font-size:.78rem;color:#888}
    .detail-meta-row{display:flex;gap:12px;flex-wrap:wrap;font-size:.8rem;color:#666;margin-bottom:20px}
    .detail-meta-row span{background:#f5f5f5;padding:3px 10px;border-radius:4px}
    .btn-download{padding:6px 14px;border:1px solid #1a1a1a;border-radius:6px;background:#1a1a1a;color:#fff;font-size:.78rem;cursor:pointer;text-decoration:none;display:inline-block}
    .btn-download:hover{background:#333}

    /* ── 折叠面板 ── */
    #detail-panels details{margin-bottom:8px;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden}
    #detail-panels summary{padding:12px 16px;font-size:.88rem;font-weight:600;cursor:pointer;background:#fafafa;border-bottom:1px solid transparent;transition:background .15s;list-style:none;display:flex;align-items:center;gap:8px}
    #detail-panels summary::-webkit-details-marker{display:none}
    #detail-panels summary::before{content:"\25B6";font-size:.65rem;color:#999;transition:transform .2s}
    #detail-panels details[open]>summary{background:#f0f0f0;border-bottom-color:#e0e0e0}
    #detail-panels details[open]>summary::before{transform:rotate(90deg)}
    .dpc{padding:16px 18px}

    /* ── 详情内部卡片 ── */
    .dcard{background:#fafafa;border:1px solid #eee;border-radius:8px;padding:12px 14px;margin-bottom:10px}
    .dcard-title{font-size:.8rem;font-weight:600;margin-bottom:6px;color:#333}
    .dcard-body{font-size:.78rem;color:#555;line-height:1.55}
    .dcard-body p{margin-bottom:4px}
    .factor-row{display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:.78rem}
    .factor-row:last-child{border-bottom:none}
    .factor-dir{font-weight:600;white-space:nowrap;min-width:48px;font-size:.72rem;padding:1px 6px;border-radius:3px;color:#fff}
    .factor-dir.pos{background:#4caf50}.factor-dir.neg{background:#f44336}
    .factor-mag{font-size:.72rem;color:#888;min-width:40px}
    .bias-dim{border-left:3px solid #ccc;padding:8px 12px;margin-bottom:8px;background:#fff;border-radius:0 6px 6px 0}
    .bias-dim.detected{border-left-color:#f44336}
    .bias-dim.clean{border-left-color:#4caf50}
    .bias-dim-label{font-size:.78rem;font-weight:600;margin-bottom:3px}
    .bias-dim-body{font-size:.75rem;color:#555;line-height:1.5}
    .dim-score-bar{display:flex;align-items:center;gap:8px;margin-bottom:6px}
    .dim-score-bar label{margin:0;min-width:100px;font-size:.78rem}
    .dim-score-bar .bar-track{flex:1;height:8px;background:#e5e5e5;border-radius:4px;overflow:hidden}
    .dim-score-bar .bar-fill{height:100%;border-radius:4px;transition:width .4s}
    .dim-score-bar .dim-val{font-size:.78rem;font-weight:600;min-width:60px;text-align:right}
    .chart-box{width:100%;height:280px;margin:10px 0}
    .info-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}
    .info-cell{padding:10px 12px;background:#f8f9fa;border-radius:6px}
    .info-cell .ic-label{font-size:.72rem;color:#888;margin-bottom:2px}
    .info-cell .ic-value{font-size:.85rem;font-weight:600;color:#1a1a1a}
    .sens-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:.78rem}
    .sens-row:last-child{border-bottom:none}
    .tag{display:inline-block;padding:1px 8px;border-radius:4px;font-size:.72rem;font-weight:600}
    .tag-green{background:#e8f5e9;color:#2e7d32}.tag-red{background:#fce4ec;color:#c62828}
    .tag-blue{background:#e3f2fd;color:#1565c0}.tag-orange{background:#fff3e0;color:#e65100}
    .tag-gray{background:#f5f5f5;color:#666}
    .section-label{font-size:.82rem;font-weight:600;color:#333;margin:12px 0 6px;padding-bottom:4px;border-bottom:1px solid #eee}
    .no-data{color:#aaa;font-size:.8rem;font-style:italic;padding:8px 0}
  </style>
</head>
<body>
<div id="app-layout">

  <!-- ── 左侧侧边栏 ── -->
  <aside id="sidebar">
    <div class="sidebar-header"><h2>已预测文献</h2></div>
    <div id="sidebar-list" class="sidebar-list"><div class="sidebar-loading">加载中...</div></div>
    <div class="sidebar-footer"><button id="btn-new-impact" type="button">+ 新建预测</button></div>
  </aside>

  <!-- ── 右侧主内容区 ── -->
  <main id="main-content">

    <!-- 表单视图 -->
    <div id="form-area">
      <div class="page-header">
        <div class="page-header-text">
          <h1>评分表工具</h1>
          <p class="sub">生成领域评分表，或对已有报告自动打分</p>
        </div>
        <div class="global-limit">
          <label for="max_report_chars">报告截断上限（字符）</label>
          <input type="number" id="max_report_chars" name="max_report_chars" min="1000" step="10000" value="200000" title="三个 Tab 共用；默认 200000" />
          <p class="hint">默认 200000，可调</p>
        </div>
      </div>

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
          <p class="hint">研究问题将根据上传文献自动生成</p>
          <details class="opt-api">
            <summary>API Key（可选）</summary>
            <input type="password" id="api_key_gen" name="api_key" placeholder="DASHSCOPE_API_KEY（填写后优先使用）" autocomplete="off" />
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
            <summary>API Key（可选）</summary>
            <input type="password" id="api_key_score" name="api_key" placeholder="DASHSCOPE_API_KEY（填写后优先使用）" autocomplete="off" />
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
            <div style="font-weight:600;margin-bottom:8px;font-size:.88rem;">评分表（可选）</div>
            <div style="font-size:.76rem;color:#666;margin-bottom:10px;">未上传的评分表将自动生成。若已打分，请同时上传 task.json 和 rubric_scores.json。</div>
            <div style="margin-bottom:10px;">
              <label for="impact_task_lit" style="font-size:.8rem;">科学调研报告 — task.json</label>
              <input id="impact_task_lit" name="task_lit" type="file" accept=".json" />
              <label for="impact_scores_lit" style="font-size:.8rem;margin-top:4px;">科学调研报告 — rubric_scores.json</label>
              <input id="impact_scores_lit" name="scores_lit" type="file" accept=".json" />
            </div>
            <div style="margin-bottom:10px;">
              <label for="impact_task_data" style="font-size:.8rem;">数据分析报告 — task.json</label>
              <input id="impact_task_data" name="task_data" type="file" accept=".json" />
              <label for="impact_scores_data" style="font-size:.8rem;margin-top:4px;">数据分析报告 — rubric_scores.json</label>
              <input id="impact_scores_data" name="scores_data" type="file" accept=".json" />
            </div>
            <div>
              <label for="impact_task_claim" style="font-size:.8rem;">主张核查报告 — task.json</label>
              <input id="impact_task_claim" name="task_claim" type="file" accept=".json" />
              <label for="impact_scores_claim" style="font-size:.8rem;margin-top:4px;">主张核查报告 — rubric_scores.json</label>
              <input id="impact_scores_claim" name="scores_claim" type="file" accept=".json" />
            </div>
          </div>
          <details class="opt-api">
            <summary>API Key（可选）</summary>
            <input type="password" id="api_key_impact" name="api_key" placeholder="DASHSCOPE_API_KEY（填写后优先使用）" autocomplete="off" />
          </details>
          <button type="submit" id="btn-impact">开始预测</button>
        </form>
      </div>

      <div id="status"></div>
    </div>

    <!-- 详情视图 -->
    <div id="detail-area">
      <div class="detail-top-bar">
        <button class="btn-back" id="btn-back" type="button">&larr; 返回</button>
        <div class="detail-title" id="detail-title"></div>
        <a id="detail-download" class="btn-download" href="#" download="impact_report.json">下载报告</a>
      </div>
      <div class="detail-summary" id="detail-summary"></div>
      <div class="detail-meta-row" id="detail-meta"></div>

      <div id="detail-panels">
        <!-- 维度1：预测结果与核心判据 -->
        <details id="dim-result" open>
          <summary>预测结果与核心判据 (Result &amp; Drivers)</summary>
          <div class="dpc" id="dpc-result"></div>
        </details>
        <!-- 维度2：可解释性分析 -->
        <details id="dim-interpret">
          <summary>可解释性分析 (Interpretability)</summary>
          <div class="dpc" id="dpc-interpret"></div>
        </details>
        <!-- 维度3：偏差识别与公平性 -->
        <details id="dim-bias">
          <summary>偏差识别与公平性 (Bias &amp; Fairness)</summary>
          <div class="dpc" id="dpc-bias"></div>
        </details>
        <!-- 维度4：复现性与过程回溯 -->
        <details id="dim-reproducibility">
          <summary>复现性与过程回溯 (Reproducibility)</summary>
          <div class="dpc" id="dpc-reproducibility"></div>
        </details>
      </div>
    </div>

  </main>
</div>

<script>
(function(){
"use strict";

/* ── 全局状态 ── */
var pollTimer = null;
var elapsedTimer = null;
var jobStartedAt = null;
var activeMode = "generate";
var impactHistory = [];
var currentDetailJobId = null;
var radarChartInst = null;
var factorChartInst = null;

/* ── DOM 缓存 ── */
var $ = function(id){ return document.getElementById(id); };
var tabs = document.querySelectorAll(".tab");
var panels = {
  generate: $("panel-generate"),
  score: $("panel-score"),
  impact: $("panel-impact")
};
var statusEl = $("status");
var btnGenerate = $("btn-generate");
var btnScore = $("btn-score");
var btnImpact = $("btn-impact");
var fileInputGen = $("files");
var fileInputScore = $("source_files");
var fileInputImpact = $("impact_files");
var fileCountGen = $("file-count-gen");
var fileCountScore = $("file-count-score");
var fileCountImpact = $("file-count-impact");
var formArea = $("form-area");
var detailArea = $("detail-area");

/* ── 工具函数 ── */
function esc(s){ if(!s) return ""; return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function ratingClass(r){ if(!r) return "rb-N"; r = r.trim(); if(r==="S") return "rb-S"; if(r==="A-") return "rb-A-"; return "rb-"+r; }
function safeNum(v,def){ var n = parseFloat(v); return isNaN(n) ? (def||0) : n; }

/** 百分制综合分：优先新格式 composite_score，兼容旧 200 分制 */
function resolveCompositeScore(rating, totalScore){
  rating = rating || {};
  if(rating.composite_score != null && !isNaN(Number(rating.composite_score))){
    return Number(rating.composite_score);
  }
  var totalMax = Number(rating.total_max || 100);
  if(rating.composite_score_raw != null && totalMax > 0){
    var raw = Number(rating.composite_score_raw);
    if(!isNaN(raw)) return raw / totalMax * 100;
  }
  if(totalScore != null && !isNaN(Number(totalScore))){
    var ts = Number(totalScore);
    if(totalMax === 200) return ts / 200 * 100;
    return ts;
  }
  return null;
}

/** 影响力分：优先 calibrated_total.score（新），兼容 impact.total_score / rating.impact_score */
function resolveImpactScore(impact, rating){
  impact = impact || {};
  rating = rating || {};
  var cal = impact.calibrated_total;
  if(cal && typeof cal === "object" && cal.score != null){
    return { score: cal.score, max: cal.max != null ? cal.max : 30 };
  }
  if(impact.total_score != null && typeof impact.total_score !== "object"){
    return { score: impact.total_score, max: impact.max_score || impact.total_max || 30 };
  }
  if(rating.impact_score != null){
    return { score: rating.impact_score, max: rating.impact_max || 30 };
  }
  return { score: null, max: 30 };
}

function clearTimers(){
  if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
  if(elapsedTimer){clearInterval(elapsedTimer);elapsedTimer=null;}
}
function formatElapsed(sec){
  var m=Math.floor(sec/60), s=sec%60;
  return m>0 ? m+" 分 "+s+" 秒" : s+" 秒";
}
function setButtonsDisabled(d){
  btnGenerate.disabled=d; btnScore.disabled=d; btnImpact.disabled=d;
}

/* ── 侧边栏 ── */
function loadImpactHistory(){
  fetch("/api/impact/history").then(function(r){return r.json();}).then(function(data){
    impactHistory = data || [];
    renderSidebar();
  }).catch(function(){
    $("sidebar-list").innerHTML = '<div class="sidebar-empty">加载失败</div>';
  });
}

function renderSidebar(){
  var el = $("sidebar-list");
  if(!impactHistory.length){
    el.innerHTML = '<div class="sidebar-empty">暂无预测记录<br>上传 PDF 开始预测</div>';
    return;
  }
  var html = "";
  for(var i=0;i<impactHistory.length;i++){
    var it = impactHistory[i];
    var active = (currentDetailJobId === it.job_id) ? " active" : "";
    var cls = ratingClass(it.rating);
    var score = (it.total_score != null) ? Number(it.total_score).toFixed(1) : "--";
    html += '<div class="sidebar-item'+active+'" data-jid="'+esc(it.job_id)+'">'
      + '<button class="sidebar-item-del" title="删除此记录" data-jid="'+esc(it.job_id)+'">✕</button>'
      + '<div class="sidebar-item-title">'+esc(it.title||"未知标题")+'</div>'
      + '<div class="sidebar-item-meta">'
      + '<span class="rb '+cls+'">'+esc(it.rating||"N/A")+'</span>'
      + '<span>'+score+' 分</span>'
      + (it.year ? '<span>'+it.year+'</span>' : '')
      + '</div></div>';
  }
  el.innerHTML = html;

  // 绑定点击事件（打开详情）
  el.querySelectorAll(".sidebar-item").forEach(function(item){
    item.addEventListener("click", function(e){
      if(e.target.closest(".sidebar-item-del")) return; // 删除按钮不触发详情
      showDetail(item.getAttribute("data-jid"));
    });
  });

  // 绑定删除事件
  el.querySelectorAll(".sidebar-item-del").forEach(function(btn){
    btn.addEventListener("click", function(e){
      e.stopPropagation();
      deleteJob(btn.getAttribute("data-jid"));
    });
  });
}

/* ── 详情视图切换 ── */
function showDetail(jobId){
  currentDetailJobId = jobId;
  // 更新侧边栏高亮
  $("sidebar-list").querySelectorAll(".sidebar-item").forEach(function(el){
    el.classList.toggle("active", el.getAttribute("data-jid")===jobId);
  });
  // 显示加载状态
  detailArea.style.display = "block";
  formArea.style.display = "none";
  $("detail-title").textContent = "加载中...";
  $("detail-summary").innerHTML = "";
  $("detail-meta").innerHTML = "";
  ["dpc-result","dpc-interpret","dpc-bias","dpc-reproducibility"].forEach(function(id){
    $(id).innerHTML = '<div class="no-data">加载中...</div>';
  });
  // 销毁旧图表
  if(radarChartInst){radarChartInst.dispose();radarChartInst=null;}
  if(factorChartInst){factorChartInst.dispose();factorChartInst=null;}

  fetch("/api/impact/detail/"+jobId).then(function(r){
    if(!r.ok) throw new Error("HTTP "+r.status);
    return r.json();
  }).then(function(data){
    renderDetail(data, jobId);
    // 第一个面板默认 open，初始化图表
    setTimeout(function(){ initResultCharts(data); }, 50);
  }).catch(function(err){
    $("detail-title").textContent = "加载失败";
    $("dpc-result").innerHTML = '<div class="no-data">'+esc(err.message)+'</div>';
  });
}

function hideDetail(){
  currentDetailJobId = null;
  detailArea.style.display = "none";
  formArea.style.display = "block";
  if(radarChartInst){radarChartInst.dispose();radarChartInst=null;}
  if(factorChartInst){factorChartInst.dispose();factorChartInst=null;}
  $("sidebar-list").querySelectorAll(".sidebar-item").forEach(function(el){
    el.classList.remove("active");
  });
}

function deleteJob(jobId){
  if(!confirm("确定要删除这条预测记录吗？")) return;
  fetch("/api/impact/"+jobId, {method:"DELETE"}).then(function(r){
    if(!r.ok) throw new Error("删除失败: HTTP "+r.status);
    return r.json();
  }).then(function(){
    // 如果当前正在查看的就是这条记录，返回列表页
    if(currentDetailJobId === jobId) hideDetail();
    // 刷新历史列表
    loadImpactHistory();
  }).catch(function(err){
    alert(err.message);
  });
}

function newPrediction(){
  hideDetail();
  switchTab("impact");
}

/* ── Tab 切换 ── */
function switchTab(name){
  activeMode = name;
  tabs.forEach(function(t){ t.classList.toggle("active", t.getAttribute("data-tab")===name); });
  Object.keys(panels).forEach(function(k){ panels[k].classList.toggle("active", k===name); });
  clearTimers();
  statusEl.style.display = "none";
}

/* ── 详情渲染 ── */
function renderDetail(d, jobId){
  var meta = d.metadata || {};
  var impact = d.impact || {};
  var rating = d.rating || {};
  var biasExp = d.bias_explanation || {};
  var cq = d.content_quality || {};

  // 标题 & 下载链接
  var title = meta.title || d.title || "未知标题";
  $("detail-title").textContent = title;
  $("detail-download").href = "/api/download/"+jobId+"/impact";

  // 评级摘要（百分制：优先 composite_score）
  var rRating = rating.rating || "N/A";
  var rLabel = rating.rating_label || "";
  var compNum = resolveCompositeScore(rating, d.total_score);
  var compScore = compNum != null ? Number(compNum).toFixed(1) : "--";
  var impResolved = resolveImpactScore(impact, rating);
  var impScore = impResolved.score;
  var impMax = impResolved.max;
  var impLevel = impact.impact_level || "";

  var summaryHtml = '<span class="rb '+ratingClass(rRating)+'" style="font-size:1.3rem;padding:4px 14px">'+esc(rRating)+'</span>'
    + '<div><div class="score-big">'+compScore+'</div><div class="score-label">综合得分</div></div>';
  if(impScore != null){
    summaryHtml += '<div><div class="score-big">'+impScore+'/'+impMax+'</div><div class="score-label">影响力得分'+(impLevel?' ('+esc(impLevel)+')':'')+'</div></div>';
  }
  var cqPct = cq.best_pct != null ? cq.best_pct : (rating.best_content_pct != null ? rating.best_content_pct : (rating.content_quality != null ? rating.content_quality : null));
  if(cqPct != null){
    summaryHtml += '<div><div class="score-big">'+Number(cqPct).toFixed(1)+'%</div><div class="score-label">内容质量（最高项）</div></div>';
  }
  if(rLabel){
    summaryHtml += '<div style="font-size:.82rem;color:#666;margin-left:4px">'+esc(rLabel)+'</div>';
  }
  $("detail-summary").innerHTML = summaryHtml;

  // 元信息行
  var metaParts = [];
  var venue = meta.host_venue || "";
  var year = meta.publication_year || "";
  var cites = meta.cited_by_count;
  var doi = d.doi || meta.doi || "";
  var authors = (meta.authors||[]).map(function(a){return a.name;}).join(", ");
  if(venue) metaParts.push(venue);
  if(year) metaParts.push(year+" 年");
  if(cites != null) metaParts.push("被引 "+cites+" 次");
  if(doi) metaParts.push("DOI: "+doi);
  var metaHtml = metaParts.map(function(p){ return '<span>'+esc(p)+'</span>'; }).join("");
  if(authors){
    metaHtml += '<span style="flex-basis:100%;font-size:.75rem;color:#999">'+esc(authors)+'</span>';
  }
  $("detail-meta").innerHTML = metaHtml;

  // 渲染各维度面板
  renderResultPanel(d);
  renderInterpretPanel(d);
  renderBiasPanel(d);
  renderReproducibilityPanel(d, jobId);
}

/* ── 维度1：预测结果与核心判据 ── */
function getDimensions(impact){
  var dims = [];
  // 新格式 (evaluate_impact 输出)
  if(impact.d1_text_quality){
    dims.push({name:"D1 文本质量", score:impact.d1_text_quality.score, max:impact.d1_text_quality.max, rationale:impact.d1_text_quality.rationale||impact.d1_text_quality.reason});
  } else if(impact.academic_reach){
    dims.push({name:"学术影响力", score:impact.academic_reach.score, max:impact.academic_reach.max, rationale:impact.academic_reach.rationale||impact.academic_reach.reason});
  }
  if(impact.d2_reputation){
    dims.push({name:"D2 声誉", score:impact.d2_reputation.score, max:impact.d2_reputation.max, rationale:impact.d2_reputation.rationale||impact.d2_reputation.reason});
  } else if(impact.venue_quality){
    dims.push({name:"期刊/会议质量", score:impact.venue_quality.score, max:impact.venue_quality.max, rationale:impact.venue_quality.rationale||impact.venue_quality.reason});
  }
  if(impact.d3_future_potential){
    dims.push({name:"D3 未来潜力", score:impact.d3_future_potential.score, max:impact.d3_future_potential.max, rationale:impact.d3_future_potential.rationale||impact.d3_future_potential.reason});
  } else if(impact.author_influence){
    dims.push({name:"作者影响力", score:impact.author_influence.score, max:impact.author_influence.max, rationale:impact.author_influence.rationale||impact.author_influence.reason});
  }
  if(impact.d4_bias_fairness){
    dims.push({name:"D4 偏差公平", score:impact.d4_bias_fairness.score, max:impact.d4_bias_fairness.max, rationale:impact.d4_bias_fairness.rationale||impact.d4_bias_fairness.reason});
  } else if(impact.network_position){
    dims.push({name:"网络位置", score:impact.network_position.score, max:impact.network_position.max, rationale:impact.network_position.rationale||impact.network_position.reason});
  }
  return dims;
}

function renderResultPanel(d){
  var impact = d.impact || {};
  var dims = getDimensions(impact);
  var ad = impact._analysis_data || {};
  var cg = ad.citation_graph || {};
  var cq = d.content_quality || {};
  var cal = impact.calibration_details || {};

  var html = "";

  // 维度评分条
  html += '<div class="section-label">维度评分</div>';
  var colors = ["#2196f3","#4caf50","#ff9800","#9c27b0"];
  for(var i=0;i<dims.length;i++){
    var dm = dims[i];
    var pct = safeNum(dm.max,1)>0 ? (safeNum(dm.score,0)/safeNum(dm.max,1)*100) : 0;
    var c = colors[i % colors.length];
    html += '<div class="dim-score-bar">'
      + '<label>'+esc(dm.name)+'</label>'
      + '<div class="bar-track"><div class="bar-fill" style="width:'+pct.toFixed(1)+'%;background:'+c+'"></div></div>'
      + '<span class="dim-val">'+dm.score+'/'+dm.max+'</span></div>';
  }

  // 雷达图容器
  if(dims.length >= 3){
    html += '<div id="radar-chart" class="chart-box"></div>';
  }

  // 校准详情（敏感性分析）
  if(cal.raw_reputation_component != null || cal.raw_quality_component != null){
    html += '<div class="section-label">校准公式分量</div><div class="dcard"><div class="dcard-body">';
    var repComp = safeNum(cal.raw_reputation_component,0);
    var qualComp = safeNum(cal.raw_quality_component,0);
    var repAdj = safeNum(cal.reputation_adjustment,0);
    var qualAdj = safeNum(cal.quality_adjustment,0);
    html += '<p>声誉分量: <strong>'+repComp.toFixed(1)+'</strong>'+(repAdj!==0 ? ' (调整 '+repAdj.toFixed(1)+')' : '')+'</p>';
    html += '<p>质量分量: <strong>'+qualComp.toFixed(1)+'</strong>'+(qualAdj!==0 ? ' (调整 '+qualAdj.toFixed(1)+')' : '')+'</p>';
    // 假设分析（影响力校准总分：优先 calibrated_total.score）
    var currentTotal = resolveImpactScore(impact, {}).score;
    if(currentTotal != null){
      html += '<p style="margin-top:6px;color:#888;font-size:.75rem">假设分析：';
      html += '如果声誉分量为 0，总分约 <strong>'+(safeNum(currentTotal,0) - repComp + repAdj).toFixed(1)+'</strong>；';
      html += '如果质量分量为 0，总分约 <strong>'+(safeNum(currentTotal,0) - qualComp + qualAdj).toFixed(1)+'</strong></p>';
    }
    if(cal.bias_mitigation_summary){
      html += '<p style="margin-top:4px;color:#666">'+esc(cal.bias_mitigation_summary)+'</p>';
    }
    html += '</div></div>';
  }

  // 关键影响因子
  var kf = impact.key_factors;
  if(kf && kf.length){
    html += '<div class="section-label">关键影响因子</div><div class="dcard"><div class="dcard-body">';
    for(var i=0;i<kf.length;i++){
      var f = kf[i];
      var dirCls = (f.impact==="positive"||f.impact==="pos") ? "pos" : "neg";
      var dirText = (f.impact==="positive"||f.impact==="pos") ? "正面" : "负面";
      html += '<div class="factor-row">'
        + '<span class="factor-dir '+dirCls+'">'+dirText+'</span>'
        + '<span class="factor-mag">'+esc(f.magnitude||"")+'</span>'
        + '<span>'+esc(f.factor||f.description||"")+'</span></div>';
    }
    html += '</div></div>';
    if(kf.length > 0) html += '<div id="factor-chart" class="chart-box"></div>';
  }

  // 内容质量来源
  var cqDetails = cq.details;
  if(cqDetails && cqDetails.length){
    html += '<div class="section-label">内容质量来源</div><div class="dcard"><div class="dcard-body">';
    for(var i=0;i<cqDetails.length;i++){
      var dd = cqDetails[i];
      var isBest = (dd.score_percentage === cq.best_pct);
      html += '<div class="factor-row"'+(isBest?' style="color:#1565c0;font-weight:600"':'')+'  >'
        + '<span style="min-width:80px">'+(isBest?"* ":"")+esc(dd.label||dd.task_type)+'</span>'
        + '<span>'+dd.raw_score+'/'+dd.total_score+' ('+dd.score_percentage+'%)</span></div>';
    }
    html += '</div></div>';
  }

  // 影响力来源
  html += '<div class="section-label">影响力来源</div><div class="info-grid">';
  if(cg.citation_velocity != null){
    html += '<div class="info-cell"><div class="ic-label">引用速度</div><div class="ic-value">'+safeNum(cg.citation_velocity,0).toFixed(1)+' 次/月</div></div>';
  }
  if(cg.field_percentile != null){
    html += '<div class="info-cell"><div class="ic-label">领域百分位</div><div class="ic-value">'+safeNum(cg.field_percentile,0).toFixed(1)+'%</div></div>';
  }
  if(cg.network_size && cg.network_size.total != null){
    html += '<div class="info-cell"><div class="ic-label">引用网络规模</div><div class="ic-value">'+cg.network_size.total+'</div></div>';
  }
  var cites = (d.metadata||{}).cited_by_count;
  if(cites != null){
    html += '<div class="info-cell"><div class="ic-label">总引用次数</div><div class="ic-value">'+cites+'</div></div>';
  }
  if(impact.impact_level){
    html += '<div class="info-cell"><div class="ic-label">影响力等级</div><div class="ic-value">'+esc(impact.impact_level)+'</div></div>';
  }
  html += '</div>';

  // 总评
  if(impact.overall_assessment){
    html += '<div class="section-label">综合评语</div><div class="dcard"><div class="dcard-body">'+esc(impact.overall_assessment)+'</div></div>';
  }

  $("dpc-result").innerHTML = html;
}

/* ── 维度2：可解释性分析 ── */
function renderInterpretPanel(d){
  var impact = d.impact || {};
  var ad = (impact._analysis_data) || {};
  var pf = ad.paper_features || {};
  var cg = ad.citation_graph || {};
  var corrections = impact.corrections || [];
  var html = "";

  // 论文文本特征
  if(pf.structure || pf.content || pf.innovation || pf.quality_signals){
    html += '<div class="section-label">论文文本特征</div><div class="info-grid">';
    if(pf.overall_quality_score != null){
      html += '<div class="info-cell"><div class="ic-label">整体质量评分</div><div class="ic-value">'+safeNum(pf.overall_quality_score,0).toFixed(0)+'</div></div>';
    }
    // 结构完整性
    var struct = pf.structure || {};
    if(struct.sections_found || struct.has_abstract != null){
      var secList = struct.sections_found || [];
      html += '<div class="info-cell"><div class="ic-label">结构完整性</div><div class="ic-value">';
      if(struct.has_abstract != null) html += (struct.has_abstract ? "有摘要, " : "无摘要, ");
      if(struct.has_methodology != null) html += (struct.has_methodology ? "有方法, " : "");
      if(struct.has_results != null) html += (struct.has_results ? "有结果, " : "");
      if(struct.has_conclusion != null) html += (struct.has_conclusion ? "有结论, " : "");
      if(secList.length) html += "章节: "+secList.join(", ");
      html += '</div></div>';
    }
    // 方法论深度
    if(struct.methodology_depth != null){
      html += '<div class="info-cell"><div class="ic-label">方法论深度</div><div class="ic-value">'+esc(struct.methodology_depth)+'</div></div>';
    }
    // 创新密度
    var innov = pf.innovation || {};
    if(innov.novelty_density != null){
      html += '<div class="info-cell"><div class="ic-label">创新密度</div><div class="ic-value">'+esc(innov.novelty_density)+'</div></div>';
    }
    if(innov.novelty_claims_count != null){
      html += '<div class="info-cell"><div class="ic-label">新颖性声明数</div><div class="ic-value">'+innov.novelty_claims_count+'</div></div>';
    }
    // 内容质量信号
    var qs = pf.quality_signals || {};
    if(qs.experiment_rigor != null){
      html += '<div class="info-cell"><div class="ic-label">实验严谨度</div><div class="ic-value">'+esc(qs.experiment_rigor)+'</div></div>';
    }
    if(qs.reproducibility_signals != null){
      html += '<div class="info-cell"><div class="ic-label">可复现信号</div><div class="ic-value">'+esc(qs.reproducibility_signals)+'</div></div>';
    }
    html += '</div>';
  }

  // 跨领域程度
  var concepts = (d.metadata||{}).concepts || [];
  if(concepts.length){
    html += '<div class="section-label">跨领域标签</div><div class="dcard"><div class="dcard-body">';
    html += concepts.map(function(c){ return '<span class="tag tag-blue" style="margin:2px">'+esc(c)+'</span>'; }).join(" ");
    html += '</div></div>';
  }

  // 引用网络
  if(cg.citation_velocity != null || cg.field_percentile != null || cg.diversity != null){
    html += '<div class="section-label">引用网络数据</div><div class="info-grid">';
    if(cg.diversity != null){
      html += '<div class="info-cell"><div class="ic-label">引用多样性</div><div class="ic-value">'+esc(cg.diversity)+'</div></div>';
    }
    if(cg.high_impact_ratio != null){
      html += '<div class="info-cell"><div class="ic-label">高影响力引用比例</div><div class="ic-value">'+safeNum(cg.high_impact_ratio,0).toFixed(2)+'</div></div>';
    }
    if(cg.connectivity != null){
      html += '<div class="info-cell"><div class="ic-label">网络连通性</div><div class="ic-value">'+esc(cg.connectivity)+'</div></div>';
    }
    if(cg.avg_citation_age != null){
      html += '<div class="info-cell"><div class="ic-label">平均引用年龄</div><div class="ic-value">'+safeNum(cg.avg_citation_age,0).toFixed(1)+' 年</div></div>';
    }
    html += '</div>';
  }

  // 元数据修正记录
  if(corrections.length){
    html += '<div class="section-label">元数据修正记录</div><div class="dcard"><div class="dcard-body">';
    for(var i=0;i<corrections.length;i++){
      var cr = corrections[i];
      html += '<p><strong>'+esc(cr.field)+'</strong>: '+esc(cr.raw)+' &rarr; <strong>'+esc(cr.corrected)+'</strong></p>';
      html += '<p style="color:#888;font-size:.73rem;margin-bottom:6px">'+esc(cr.reason)+'</p>';
    }
    html += '</div></div>';
  }

  // 逻辑链条
  var dims = getDimensions(impact);
  if(dims.length){
    html += '<div class="section-label">各维度判据说明</div>';
    for(var i=0;i<dims.length;i++){
      var dm = dims[i];
      if(dm.rationale){
        html += '<div class="dcard"><div class="dcard-title">'+esc(dm.name)+' ('+dm.score+'/'+dm.max+')</div>'
          + '<div class="dcard-body">'+esc(dm.rationale)+'</div></div>';
      }
    }
  }

  if(!html) html = '<div class="no-data">无可解释性数据（文本特征和引用网络数据在当前版本中未完整提取）</div>';
  $("dpc-interpret").innerHTML = html;
}

/* ── 维度3：偏差识别与公平性 ── */
function renderBiasPanel(d){
  var biasExp = d.bias_explanation || {};
  var html = "";

  // 新格式：bias_analysis（7维度）
  var ba = biasExp.bias_analysis;
  if(ba && typeof ba === "object" && Object.keys(ba).length){
    html += '<div class="section-label">偏差维度分析</div>';
    var keys = Object.keys(ba);
    for(var i=0;i<keys.length;i++){
      var k = keys[i];
      var dim = ba[k];
      if(!dim || typeof dim !== "object") continue;
      var detected = dim.detected;
      var cls = detected ? "detected" : "clean";
      var dirTag = dim.direction ? ' <span class="tag '+(dim.direction==="positive"?"tag-green":"tag-red")+'">'+esc(dim.direction)+'</span>' : "";
      html += '<div class="bias-dim '+cls+'">'
        + '<div class="bias-dim-label">'+esc(k.replace(/_/g," "))+dirTag+(detected?" <span class=\"tag tag-red\">已检测到</span>":" <span class=\"tag tag-green\">未检测到</span>")+'</div>'
        + '<div class="bias-dim-body">';
      if(dim.estimated_impact != null) html += '<p>估计影响: <strong>'+safeNum(dim.estimated_impact,0).toFixed(2)+'</strong></p>';
      if(dim.description) html += '<p>'+esc(dim.description)+'</p>';
      if(dim.mitigation) html += '<p style="color:#2e7d32">缓解措施: '+esc(dim.mitigation)+'</p>';
      html += '</div></div>';
    }
  }

  // 当前评估总述
  if(biasExp.current_assessment){
    html += '<div class="section-label">评估总述</div><div class="dcard"><div class="dcard-body">'+esc(biasExp.current_assessment)+'</div></div>';
  }

  // 公平性评估
  var fa = biasExp.fairness_assessment;
  if(fa){
    html += '<div class="section-label">公平性评估</div><div class="info-grid">';
    if(fa.overall_fairness_score != null){
      html += '<div class="info-cell"><div class="ic-label">公平性总评</div><div class="ic-value">'+safeNum(fa.overall_fairness_score,0).toFixed(1)+'/'+safeNum(fa.max,10)+'</div></div>';
    }
    if(fa.confidence) html += '<div class="info-cell"><div class="ic-label">置信度</div><div class="ic-value">'+esc(fa.confidence)+'</div></div>';
    html += '</div>';
    if(fa.key_concerns && fa.key_concerns.length){
      html += '<div class="dcard"><div class="dcard-title">关键关注点</div><div class="dcard-body">';
      for(var i=0;i<fa.key_concerns.length;i++){
        html += '<p>'+esc(fa.key_concerns[i])+'</p>';
      }
      html += '</div></div>';
    }
    if(fa.recommendations && fa.recommendations.length){
      html += '<div class="dcard"><div class="dcard-title">建议</div><div class="dcard-body">';
      for(var i=0;i<fa.recommendations.length;i++){
        html += '<p>'+esc(fa.recommendations[i])+'</p>';
      }
      html += '</div></div>';
    }
  }

  // 偏低/偏高偏差分析
  if(biasExp.underestimation_bias && biasExp.underestimation_bias.length){
    html += '<div class="section-label" style="color:#1565c0">偏低误差 — 得分可能低估</div>';
    for(var i=0;i<biasExp.underestimation_bias.length;i++){
      var item = biasExp.underestimation_bias[i];
      html += '<div class="dcard" style="border-left:3px solid #1565c0"><div class="dcard-body">'
        + '<p><strong>'+esc(item.dimension)+'</strong> ('+esc(item.current_score||"")+')</p>'
        + '<p>'+esc(item.score_may_be_low_because||"")+'</p>'
        + (item.evidence ? '<p style="color:#888;font-size:.73rem">证据: '+esc(item.evidence)+'</p>' : '')
        + (item.estimated_true_range ? '<p style="color:#1565c0;font-size:.73rem">估计范围: '+esc(item.estimated_true_range)+'</p>' : '')
        + '</div></div>';
    }
  }
  if(biasExp.overestimation_bias && biasExp.overestimation_bias.length){
    html += '<div class="section-label" style="color:#c62828">偏高误差 — 得分可能高估</div>';
    for(var i=0;i<biasExp.overestimation_bias.length;i++){
      var item = biasExp.overestimation_bias[i];
      html += '<div class="dcard" style="border-left:3px solid #c62828"><div class="dcard-body">'
        + '<p><strong>'+esc(item.dimension)+'</strong> ('+esc(item.current_score||"")+' ) '
        + '<span class="tag tag-red">风险: '+esc(item.risk_level||"Medium")+'</span></p>'
        + '<p>'+esc(item.score_may_be_high_because||"")+'</p>'
        + (item.evidence ? '<p style="color:#888;font-size:.73rem">证据: '+esc(item.evidence)+'</p>' : '')
        + '</div></div>';
    }
  }

  // 提升路径 & 下降风险
  if(biasExp.improvement_path && biasExp.improvement_path.length){
    html += '<div class="section-label" style="color:#2e7d32">提升路径</div>';
    for(var i=0;i<biasExp.improvement_path.length;i++){
      var item = biasExp.improvement_path[i];
      html += '<div class="dcard" style="border-left:3px solid #2e7d32"><div class="dcard-body">'
        + '<p><strong>'+esc(item.dimension)+'</strong> ('+esc(item.current_score||"")+')</p>'
        + (item.gap_to_close ? '<p>'+esc(item.gap_to_close)+'</p>' : '')
        + (item.realistic!=null ? '<p style="color:#2e7d32">可行性: '+(item.realistic?"可行":"不确定")+'</p>' : '')
        + '</div></div>';
    }
  }
  if(biasExp.decline_risks && biasExp.decline_risks.length){
    html += '<div class="section-label" style="color:#c62828">下降风险</div>';
    for(var i=0;i<biasExp.decline_risks.length;i++){
      var item = biasExp.decline_risks[i];
      html += '<div class="dcard" style="border-left:3px solid #c62828"><div class="dcard-body">'
        + '<p><strong>'+esc(item.dimension)+'</strong> <span class="tag tag-red">风险: '+esc(item.severity||"Medium")+'</span></p>'
        + (item.trigger ? '<p>触发条件: '+esc(item.trigger)+'</p>' : '')
        + (item.risk_drop_to_tier ? '<p>可能跌至: '+esc(item.risk_drop_to_tier)+'</p>' : '')
        + '</div></div>';
    }
  }

  // 依据声明
  if(biasExp.data_reliability){
    var dr = biasExp.data_reliability;
    html += '<div class="section-label">依据声明</div><div class="dcard"><div class="dcard-body">';
    if(dr.verified_claims && dr.verified_claims.length){
      html += '<p style="color:#2e7d32;font-weight:600">已验证</p>';
      for(var i=0;i<dr.verified_claims.length;i++) html += '<p>&#10003; '+esc(dr.verified_claims[i])+'</p>';
    }
    if(dr.inferred_claims && dr.inferred_claims.length){
      html += '<p style="color:#e65100;font-weight:600;margin-top:8px">推断</p>';
      for(var i=0;i<dr.inferred_claims.length;i++) html += '<p>~ '+esc(dr.inferred_claims[i])+'</p>';
    }
    if(dr.missing_data && dr.missing_data.length){
      html += '<p style="color:#999;font-weight:600;margin-top:8px">缺失</p>';
      for(var i=0;i<dr.missing_data.length;i++) html += '<p>? '+esc(dr.missing_data[i])+'</p>';
    }
    html += '</div></div>';
  }

  if(!html) html = '<div class="no-data">无偏差分析数据</div>';
  $("dpc-bias").innerHTML = html;
}

/* ── 维度4：复现性与过程回溯 ── */
function renderReproducibilityPanel(d, jobId){
  var meta = d.metadata || {};
  var impact = d.impact || {};
  var html = "";

  // DOI 提取
  html += '<div class="section-label">数据获取痕迹</div><div class="dcard"><div class="dcard-body">';
  html += '<p><strong>DOI</strong>: '+esc(d.doi || "未提取到")+'</p>';
  html += '<p><strong>标题提取</strong>: '+(d.title ? esc(d.title) : "未提取");
  if(meta.title && d.title && meta.title !== d.title){
    html += ' <span style="color:#e65100">(元数据修正: '+esc(meta.title)+')</span>';
  }
  html += '</p>';
  if(meta.openalex_id) html += '<p><strong>OpenAlex ID</strong>: '+esc(meta.openalex_id)+'</p>';
  if(meta.type) html += '<p><strong>文献类型</strong>: '+esc(meta.type)+'</p>';
  if(meta.publication_date) html += '<p><strong>出版日期</strong>: '+esc(meta.publication_date)+'</p>';
  if(meta.open_access != null) html += '<p><strong>开放获取</strong>: '+(meta.open_access ? "是" : "否")+'</p>';
  if(meta.referenced_works_count != null) html += '<p><strong>参考文献数</strong>: '+meta.referenced_works_count+'</p>';
  html += '</div></div>';

  // PDF 文本提取
  html += '<div class="section-label">PDF 处理</div><div class="dcard"><div class="dcard-body">';
  html += '<p><strong>文件</strong>: '+esc(d.pdf_file || "未知")+'</p>';
  html += '<p><strong>元数据来源</strong>: OpenAlex API (按 DOI 查询)</p>';
  html += '</div></div>';

  // 引用网络数据来源
  var ad = (impact._analysis_data) || {};
  var cg = ad.citation_graph || {};
  html += '<div class="section-label">引用网络数据来源</div><div class="dcard"><div class="dcard-body">';
  html += '<p>引用次数: 来自 OpenAlex cited_by_count</p>';
  if(cg.data_source) html += '<p>网络数据: '+esc(cg.data_source)+'</p>';
  if(cg.network_size && cg.network_size.source) html += '<p>网络规模: '+esc(cg.network_size.source)+'</p>';
  html += '</div></div>';

  // 评分维度参数
  var dims = getDimensions(impact);
  if(dims.length){
    html += '<div class="section-label">评分维度固定参数</div><div class="dcard"><div class="dcard-body">';
    for(var i=0;i<dims.length;i++){
      html += '<p>'+esc(dims[i].name)+': max = '+dims[i].max+'</p>';
    }
    html += '</div></div>';
  }

  // 处理日志摘要（从 status.json 获取）
  html += '<div class="section-label">处理日志摘要</div><div class="dcard"><div id="repro-log" class="dcard-body"><span class="no-data">加载中...</span></div></div>';

  // 异步加载日志
  fetch("/api/status/"+jobId).then(function(r){return r.json();}).then(function(sd){
    var logs = sd.logs || [];
    var logEl = $("repro-log");
    if(logEl){
      if(logs.length){
        logEl.innerHTML = logs.map(function(l){
          var m = l.match(/^\[(literature_review|data_analysis|claim_verification)\]\s+(使用.+评分表[，,]?\s*)?(.+)$/);
          if(m){
            var tt = m[1];
            var label = tt==="literature_review"?"科学调研":tt==="data_analysis"?"数据分析":"主张核查";
            var prefix = m[2] || "";
            var rest = m[3] || "";
            return '<p style="position:relative;padding-right:90px;">'
              + '<a href="#" class="rubric-link" data-task="'+tt+'" style="color:#4caf50;text-decoration:underline;cursor:pointer;font-weight:600;">['+label+']</a> '
              + esc(prefix+rest)
              + '<button class="rubric-toggle" data-task="'+tt+'" style="position:absolute;right:0;top:0;padding:2px 8px;font-size:11px;background:#1a1a1a;color:#4caf50;border:1px solid #4caf50;border-radius:4px;cursor:pointer;">查看评分表</button>'
              + '</p>'
              + '<pre class="rubric-json" id="rubric-'+tt+'" style="display:none;background:#111;padding:12px;border-radius:6px;font-size:11px;overflow:auto;max-height:400px;color:#aaa;border:1px solid #333;margin:4px 0 12px 0;"></pre>';
          }
          return '<p>'+esc(l)+'</p>';
        }).join("");
        // 绑定评分表查看事件
        logEl.querySelectorAll('.rubric-toggle').forEach(function(btn){
          btn.addEventListener('click', function(e){
            e.preventDefault();
            var tt = btn.getAttribute('data-task');
            var pre = $('rubric-'+tt);
            if(!pre) return;
            if(pre.style.display === 'block'){
              pre.style.display = 'none';
              btn.textContent = '查看评分表';
            } else {
              if(!pre.dataset.loaded){
                pre.textContent = '加载中...';
                fetch('/api/rubric/'+jobId+'/'+tt).then(function(r){return r.json();}).then(function(data){
                  pre.textContent = JSON.stringify(data, null, 2);
                  pre.dataset.loaded = '1';
                }).catch(function(err){
                  pre.textContent = '加载失败: '+err.message;
                });
              }
              pre.style.display = 'block';
              btn.textContent = '收起评分表';
            }
          });
        });
        // 链接点击也触发展开
        logEl.querySelectorAll('.rubric-link').forEach(function(link){
          link.addEventListener('click', function(e){
            e.preventDefault();
            var tt = link.getAttribute('data-task');
            var btn = logEl.querySelector('.rubric-toggle[data-task="'+tt+'"]');
            if(btn) btn.click();
          });
        });
      } else {
        logEl.innerHTML = '<span class="no-data">无日志记录</span>';
      }
    }
  }).catch(function(){
    var logEl = $("repro-log");
    if(logEl) logEl.innerHTML = '<span class="no-data">日志加载失败</span>';
  });

  $("dpc-reproducibility").innerHTML = html;
}

/* ── ECharts 图表初始化 ── */
function initResultCharts(d){
  var impact = d.impact || {};
  var dims = getDimensions(impact);

  // 雷达图
  var radarEl = $("radar-chart");
  if(radarEl && dims.length >= 3 && typeof echarts !== "undefined"){
    radarChartInst = echarts.init(radarEl);
    var indicator = [];
    var values = [];
    for(var i=0;i<dims.length;i++){
      var pct = safeNum(dims[i].max,1) > 0 ? (safeNum(dims[i].score,0)/safeNum(dims[i].max,1)*100) : 0;
      indicator.push({name:dims[i].name, max:100});
      values.push(parseFloat(pct.toFixed(1)));
    }
    radarChartInst.setOption({
      tooltip:{},
      radar:{indicator:indicator, radius:"65%", axisName:{fontSize:11}},
      series:[{type:"radar", data:[{value:values, name:"得分率 %",
        areaStyle:{color:"rgba(33,150,243,0.15)"},
        lineStyle:{color:"#2196f3",width:2},
        itemStyle:{color:"#2196f3"}}]}]
    });
  }

  // 因子贡献柱状图
  var kf = impact.key_factors;
  var factorEl = $("factor-chart");
  if(factorEl && kf && kf.length && typeof echarts !== "undefined"){
    factorChartInst = echarts.init(factorEl);
    var names = [];
    var vals = [];
    var colors = [];
    for(var i=0;i<kf.length;i++){
      var f = kf[i];
      names.push(f.factor || f.description || "因子"+(i+1));
      var mag = f.magnitude || "medium";
      vals.push(mag==="high"?3:mag==="medium"?2:1);
      colors.push((f.impact==="positive"||f.impact==="pos") ? "#4caf50" : "#f44336");
    }
    factorChartInst.setOption({
      tooltip:{trigger:"axis", axisPointer:{type:"shadow"}},
      grid:{left:120, right:30, top:10, bottom:20},
      xAxis:{type:"value", max:3.5, axisLabel:{formatter:function(v){return v===3?"高":v===2?"中":v===1?"低":"";}}},
      yAxis:{type:"category", data:names.reverse(), axisLabel:{fontSize:11}},
      series:[{type:"bar", data:vals.reverse().map(function(v,i){ return {value:v, itemStyle:{color:colors[colors.length-1-i]}}; }), barWidth:18}]
    });
  }

  // 响应窗口大小变化
  window.addEventListener("resize", function(){
    if(radarChartInst) radarChartInst.resize();
    if(factorChartInst) factorChartInst.resize();
  });
}

/* ── 详情面板 toggle 事件（用于延迟初始化图表） ── */
document.querySelectorAll("#detail-panels details").forEach(function(det){
  det.addEventListener("toggle", function(){
    if(!det.open) return;
    // 第一个面板 open 时图表已初始化，其他面板无图表
  });
});

/* ── 表单提交与轮询（保留原有逻辑） ── */
function renderRunning(data){
  var pct = data.progress || 0;
  var elapsed = data.elapsed_sec || (jobStartedAt ? Math.floor((Date.now()-jobStartedAt)/1000) : 0);
  var logs = (data.logs || []).slice(-12).join("\\n");
  var title = data.mode_label || data.label || "处理中";
  statusEl.className = "info";
  statusEl.style.display = "block";
  statusEl.innerHTML =
    "<div><strong>"+esc(title)+"</strong> — "+esc(data.message||"正在处理...")+"</div>"
    + '<div class="progress-wrap"><div class="progress-bar" style="width:'+pct+'%"></div></div>'
    + '<div class="progress-meta"><span>'+pct+'%</span><span>已用时 '+formatElapsed(elapsed)+'</span></div>'
    + (logs ? '<div class="log-box">'+esc(logs)+'</div>' : "");
  var logBox = statusEl.querySelector(".log-box");
  if(logBox) logBox.scrollTop = logBox.scrollHeight;
}

function renderDone(data){
  clearTimers();
  statusEl.className = "ok";
  if(data.job_mode === "score"){
    statusEl.innerHTML =
      "<div><strong>评分完成</strong>："+esc(data.label)+"，"
      +(data.raw_score||"?")+"/"+(data.total_score||"?")+"（"+(data.score_percentage||"?")+"%）"
      +(data.elapsed_sec ? "，用时 "+formatElapsed(data.elapsed_sec) : "")
      +"</div>"
      +'<div style="margin-top:8px"><a href="'+esc(data.download_url)+'" download="rubric_scores.json">下载 rubric_scores.json</a></div>';
  } else if(data.job_mode === "impact"){
    var rating = data.rating || {};
    var totalScore = resolveCompositeScore(rating, data.total_score);
    var displayScore = totalScore != null ? Number(totalScore).toFixed(1) : "--";
    var meta = data.metadata_summary || {};
    var title = meta.title || "未知标题";
    var venue = meta.venue || "";
    var year = meta.year || "";
    var citations = meta.citations;
    var rRating = rating.rating || "N/A";

    var metaParts = [];
    if(venue) metaParts.push(venue);
    if(year) metaParts.push(year+" 年");
    if(citations != null) metaParts.push("被引 "+citations+" 次");

    statusEl.innerHTML =
      "<div><strong>预测完成</strong>"
      +(data.elapsed_sec ? "（用时 "+formatElapsed(data.elapsed_sec)+"）" : "")
      +"</div>"
      +'<div style="margin:10px 0;padding:10px 14px;background:#fff;border:1px solid #e5e5e5;border-radius:8px;">'
      +'<div style="font-size:1.1rem;font-weight:600;margin-bottom:6px;">'
      +'<span class="rb '+ratingClass(rRating)+'" style="font-size:1rem;margin-right:8px">'+esc(rRating)+'</span>'
      +"总分 "+esc(String(displayScore))
      +'<span style="color:#888;font-weight:400">（'+esc(rating.rating_label||"")+'）</span>'
      +'</div>'
      +'<div style="font-size:.8rem;color:#555;margin-top:6px;">'
      +'<div><strong>'+esc(title)+'</strong></div>'
      +(metaParts.length ? '<div style="margin-top:2px;color:#777">'+metaParts.join("  ·  ")+'</div>' : '')
      +'</div></div>'
      +'<div style="margin-top:8px;display:flex;gap:12px;align-items:center">'
      +'<a href="'+esc(data.download_url)+'" download="impact_report.json">下载报告</a>'
      +(data.job_id ? ' <a href="javascript:void(0)" id="link-view-detail" style="cursor:pointer;color:#1565c0;font-weight:600">查看详细分析 &rarr;</a>' : '')
      +'</div>';

    // 绑定"查看详细分析"链接
    var linkEl = $("link-view-detail");
    if(linkEl){
      linkEl.addEventListener("click", function(){
        showDetail(data.job_id);
      });
    }
    // 刷新侧边栏
    loadImpactHistory();
  } else {
    statusEl.innerHTML =
      "<div><strong>生成完成</strong>："+esc(data.label)+"，共 "+(data.item_count||"?")+" 项，"+(data.total_score||"?")+" 分"
      +(data.elapsed_sec ? "（用时 "+formatElapsed(data.elapsed_sec)+"）" : "")
      +"</div>"
      +'<div style="margin-top:8px"><a href="'+esc(data.download_url)+'" download="task.json">下载 task.json</a></div>';
  }
}

function renderError(msg){
  clearTimers();
  statusEl.className = "error";
  statusEl.textContent = msg;
}

async function pollStatus(jobId){
  try {
    var res = await fetch("/api/status/"+jobId);
    var data = await res.json().catch(function(){return {};});
    if(!res.ok) throw new Error(data.detail || res.statusText || "获取状态失败");
    if(data.status === "completed"){ renderDone(data); setButtonsDisabled(false); return; }
    if(data.status === "failed"){ renderError(data.error || data.message || "任务失败"); setButtonsDisabled(false); return; }
    renderRunning(data);
  } catch(err){
    renderError(err.message || String(err));
    setButtonsDisabled(false);
  }
}

async function submitJob(url, formData, label, hint){
  clearTimers();
  setButtonsDisabled(true);
  jobStartedAt = Date.now();
  statusEl.className = "info";
  statusEl.style.display = "block";
  statusEl.innerHTML =
    "<div><strong>准备中</strong> — "+esc(hint)+"</div>"
    +'<div class="progress-wrap"><div class="progress-bar" style="width:2%"></div></div>'
    +'<div class="progress-meta"><span>2%</span><span>已用时 0 秒</span></div>';
  try {
    var res = await fetch(url, {method:"POST", body:formData});
    var data = await res.json().catch(function(){return {};});
    if(!res.ok) throw new Error(data.detail || res.statusText || "提交失败");
    renderRunning({
      job_mode:data.job_mode,
      mode_label: data.job_mode==="score" ? "报告打分" : data.job_mode==="impact" ? "科学影响力预测" : "生成评分表",
      label:data.label,
      message: data.job_mode==="score" ? "任务已提交，正在逐条评分..." : data.job_mode==="impact" ? "任务已提交，正在分析论文影响力..." : "任务已提交，正在生成（通常 3-8 分钟）...",
      progress:3, logs:[]
    });
    pollTimer = setInterval(function(){ pollStatus(data.job_id); }, 2000);
    elapsedTimer = setInterval(function(){
      var bar = statusEl.querySelector(".progress-meta span:last-child");
      if(bar && jobStartedAt) bar.textContent = "已用时 "+formatElapsed(Math.floor((Date.now()-jobStartedAt)/1000));
    }, 1000);
    await pollStatus(data.job_id);
  } catch(err){
    renderError(err.message || String(err));
    setButtonsDisabled(false);
  }
}

/* ── 事件绑定 ── */
tabs.forEach(function(t){
  t.addEventListener("click", function(){ switchTab(t.getAttribute("data-tab")); });
});

fileInputGen.addEventListener("change", function(){
  fileCountGen.textContent = fileInputGen.files.length ? "已选择 "+fileInputGen.files.length+" 个文件" : "";
});
fileInputScore.addEventListener("change", function(){
  fileCountScore.textContent = fileInputScore.files.length ? "已选择 "+fileInputScore.files.length+" 个源文件" : "";
});
fileInputImpact.addEventListener("change", function(){
  fileCountImpact.textContent = fileInputImpact.files.length ? "已选择 "+fileInputImpact.files.length+" 个文件" : "";
});

$("btn-back").addEventListener("click", hideDetail);
$("btn-new-impact").addEventListener("click", newPrediction);

function getMaxReportChars(){
  var limit = parseInt(($("max_report_chars") || {}).value, 10);
  if(isNaN(limit) || limit <= 0) return 200000;
  if(limit > 2000000) return 2000000;
  return limit;
}

$("form-generate").addEventListener("submit", async function(e){
  e.preventDefault();
  var fd = new FormData();
  fd.append("task_type", $("task_type").value);
  fd.append("query", "");
  fd.append("max_report_chars", String(getMaxReportChars()));
  var apiKeyGen = ($("api_key_gen").value || "").trim();
  if(apiKeyGen) fd.append("api_key", apiKeyGen);
  for(var i=0;i<fileInputGen.files.length;i++) fd.append("files", fileInputGen.files[i]);
  await submitJob("/api/generate", fd, "generate", "正在上传 "+fileInputGen.files.length+" 个文件...");
});

$("form-score").addEventListener("submit", async function(e){
  e.preventDefault();
  var fd = new FormData();
  fd.append("task_file", $("task_file").files[0]);
  fd.append("report_file", $("report_file").files[0]);
  fd.append("max_report_chars", String(getMaxReportChars()));
  var apiKey = ($("api_key_score").value || "").trim();
  if(apiKey) fd.append("api_key", apiKey);
  for(var i=0;i<fileInputScore.files.length;i++) fd.append("source_files", fileInputScore.files[i]);
  await submitJob("/api/score", fd, "score", "正在上传评分表与报告...");
});

$("form-impact").addEventListener("submit", async function(e){
  e.preventDefault();
  var fd = new FormData();
  for(var i=0;i<fileInputImpact.files.length;i++) fd.append("files", fileInputImpact.files[i]);
  var taskLit = $("impact_task_lit").files[0];
  var scoresLit = $("impact_scores_lit").files[0];
  var taskData = $("impact_task_data").files[0];
  var scoresData = $("impact_scores_data").files[0];
  var taskClaim = $("impact_task_claim").files[0];
  var scoresClaim = $("impact_scores_claim").files[0];
  if(taskLit) fd.append("task_lit", taskLit);
  if(scoresLit) fd.append("scores_lit", scoresLit);
  if(taskData) fd.append("task_data", taskData);
  if(scoresData) fd.append("scores_data", scoresData);
  if(taskClaim) fd.append("task_claim", taskClaim);
  if(scoresClaim) fd.append("scores_claim", scoresClaim);
  fd.append("max_report_chars", String(getMaxReportChars()));
  var apiKey = ($("api_key_impact").value || "").trim();
  if(apiKey) fd.append("api_key", apiKey);
  await submitJob("/api/impact", fd, "impact", "正在上传 "+fileInputImpact.files.length+" 个 PDF...");
});

/* ── 初始化 ── */
loadImpactHistory();

})();
</script>
</body>
</html>
"""