"""迭代实验 API（对齐 shaxiang ExperimentService；失败返回可读错误，无 mock 降级）

阻塞调用一律走 run_blocking；设计脚本 / 跑到完成走后台 job + 轮询。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.async_utils import run_blocking
from app.core.database import get_db
from app.integrations.shaxiang.bridge import ShaxiangBridgeError, shaxiang_root
from app.schemas.common import success_response, error_response
from app.services.iterative_experiment_jobs import (
    KIND_APPLY_FL_SCRIPT,
    KIND_DESIGN_SCRIPT,
    KIND_REDESIGN,
    KIND_RUN_TO_COMPLETION,
    get_ie_job_store,
)
from app.services.iterative_experiment_service import get_iterative_experiment_service

router = APIRouter()


class CreateExperimentBody(BaseModel):
    hypothesis: str
    research_goal: Optional[str] = ""
    constraints: List[str] = Field(default_factory=list)
    executor_type: str = "sandbox"
    max_iterations: int = 10
    # True: 用户已有数据，跳过 LLM 推荐，直接进入绑定/设计
    skip_dataset_recommend: bool = False


class ReportIdsBody(BaseModel):
    experiment_ids: List[str] = Field(default_factory=list)


class DesignScriptBody(BaseModel):
    data_config: Optional[Dict[str, Any]] = None


class RunModeBody(BaseModel):
    run_mode: str = "smoke_only"


class QualityModeBody(BaseModel):
    quality_mode: str = "draft"


class FeedbackBody(BaseModel):
    feedback: str = ""


class ApplyFlScriptBody(BaseModel):
    script_id: str = Field(..., description="FL Pack 脚本 id 或相对 path")


class VerifyDataBody(BaseModel):
    data_config: Dict[str, Any]


class AutoDetectBody(BaseModel):
    directory_path: str


def _err(exc: Exception, default_code: int = 400):
    msg = str(exc) or exc.__class__.__name__
    if isinstance(exc, ShaxiangBridgeError):
        return error_response(msg, code=400)
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return error_response(msg, code=400)
    return error_response(msg, code=default_code)


def _start_long_job(
    *,
    project_id: str,
    experiment_id: str,
    kind: str,
    runner,
    message: str,
):
    store = get_ie_job_store()
    # 启动前确认实验存在（轻量，仍放线程外快速失败）
    svc = get_iterative_experiment_service()
    if not svc.get(project_id, experiment_id):
        raise ValueError("实验不存在")
    job = store.start(
        project_id=project_id,
        experiment_id=experiment_id,
        kind=kind,
        runner=runner,
        message=message,
    )
    return job.to_dict()


@router.get("/projects/{project_id}/iterative-experiments")
async def list_experiments(project_id: str, db: Session = Depends(get_db)):
    try:
        def _work():
            svc = get_iterative_experiment_service()
            return {
                "items": svc.list(project_id),
                "report_experiment_ids": svc.get_report_ids(project_id),
            }

        return success_response(await run_blocking(_work))
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments")
async def create_experiment(project_id: str, body: CreateExperimentBody, db: Session = Depends(get_db)):
    try:
        payload = body.model_dump()
        exp = await run_blocking(
            get_iterative_experiment_service().create, project_id, payload
        )
        return success_response(exp, message="实验已创建")
    except Exception as e:
        return _err(e)


@router.get("/projects/{project_id}/iterative-experiments/jobs/{job_id}")
async def get_experiment_job(project_id: str, job_id: str):
    """轮询长任务状态（design-script / apply-fl-script / redesign / run-to-completion）。"""
    try:
        job = get_ie_job_store().get(job_id)
        if not job or job.project_id != project_id:
            return error_response("任务不存在", code=404)
        return success_response(job.to_dict())
    except Exception as e:
        return _err(e)


@router.get("/projects/{project_id}/iterative-experiments/{experiment_id}/active-job")
async def get_active_experiment_job(project_id: str, experiment_id: str):
    try:
        job = get_ie_job_store().get_active_for_experiment(experiment_id)
        if not job or job.project_id != project_id:
            return success_response({"job": None})
        return success_response({"job": job.to_dict()})
    except Exception as e:
        return _err(e)


@router.get("/iterative-experiments/charts/{chart_path:path}")
async def get_iteration_chart(chart_path: str):
    """提供 shaxiang data/charts 下的迭代图表（对齐 Streamlit 图片展示）。"""
    try:
        root = (shaxiang_root() / "data" / "charts").resolve()
        rel = chart_path.replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            return error_response("非法图表路径", code=400)
        target = (root / rel).resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            return error_response("图表不存在", code=404)
        suffix = target.suffix.lower()
        media = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }.get(suffix, "application/octet-stream")
        return FileResponse(path=str(target), media_type=media, filename=target.name)
    except Exception as e:
        return _err(e)


@router.get("/iterative-experiments/{experiment_id}")
async def get_experiment(experiment_id: str, project_id: str):
    try:
        exp = await run_blocking(
            get_iterative_experiment_service().get, project_id, experiment_id
        )
        if not exp:
            return error_response("实验不存在", code=404)
        return success_response(exp)
    except Exception as e:
        return _err(e)


@router.delete("/projects/{project_id}/iterative-experiments/{experiment_id}")
async def delete_experiment(project_id: str, experiment_id: str):
    try:
        await run_blocking(
            get_iterative_experiment_service().delete, project_id, experiment_id
        )
        return success_response({"deleted": True})
    except Exception as e:
        return _err(e)


@router.put("/projects/{project_id}/iterative-experiments/report-selection")
async def set_report_selection(project_id: str, body: ReportIdsBody):
    try:
        ids = await run_blocking(
            get_iterative_experiment_service().set_report_ids,
            project_id,
            body.experiment_ids,
        )
        return success_response({"report_experiment_ids": ids})
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/toggle-report")
async def toggle_report(project_id: str, experiment_id: str):
    try:
        ids = await run_blocking(
            get_iterative_experiment_service().toggle_report, project_id, experiment_id
        )
        return success_response({"report_experiment_ids": ids})
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/recommend-datasets")
async def recommend_datasets(project_id: str, experiment_id: str, body: FeedbackBody = FeedbackBody()):
    try:
        feedback = body.feedback or None
        exp = await run_blocking(
            get_iterative_experiment_service().recommend_datasets,
            project_id,
            experiment_id,
            feedback,
        )
        return success_response(exp)
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/upload")
async def upload_dataset(
    project_id: str,
    experiment_id: str,
    file: UploadFile = File(...),
):
    try:
        content = await file.read()
        if not content:
            return error_response("上传文件为空", code=400)
        filename = file.filename or "upload.csv"
        out = await run_blocking(
            get_iterative_experiment_service().upload_dataset,
            project_id,
            experiment_id,
            filename,
            content,
        )
        return success_response(out, message="上传并试加载成功")
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/verify-data")
async def verify_data(project_id: str, experiment_id: str, body: VerifyDataBody):
    try:
        out = await run_blocking(
            get_iterative_experiment_service().verify_data,
            project_id,
            experiment_id,
            body.data_config,
        )
        return success_response(out)
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/auto-detect-profile")
async def auto_detect_profile(project_id: str, experiment_id: str, body: AutoDetectBody):
    try:
        path = (body.directory_path or "").strip()
        if not path:
            return error_response("请填写数据集目录路径", code=400)
        out = await run_blocking(
            get_iterative_experiment_service().auto_detect,
            project_id,
            experiment_id,
            path,
        )
        return success_response(out)
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/design-script")
async def design_script(project_id: str, experiment_id: str, body: DesignScriptBody):
    """启动设计脚本后台任务，立即返回 job_id；请轮询 jobs/{job_id}。"""
    try:
        data_config = body.data_config

        def _runner():
            return get_iterative_experiment_service().design_script(
                project_id, experiment_id, data_config
            )

        # 启动本身很快；runner 在独立线程执行
        job = await run_blocking(
            _start_long_job,
            project_id=project_id,
            experiment_id=experiment_id,
            kind=KIND_DESIGN_SCRIPT,
            runner=_runner,
            message="设计脚本已启动（后台执行）",
        )
        return success_response(job, message="设计脚本已启动，后台执行中")
    except Exception as e:
        return _err(e)


@router.get("/projects/{project_id}/fl-pack/scripts")
async def list_fl_pack_scripts(project_id: str):
    try:
        items = await run_blocking(
            get_iterative_experiment_service().list_fl_script_templates, project_id
        )
        return success_response({"items": items, "count": len(items)})
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/apply-fl-script")
async def apply_fl_script(project_id: str, experiment_id: str, body: ApplyFlScriptBody):
    """以 FL 模板为反馈设计/重设计脚本：后台任务 + 轮询（与 design-script 同协议）。"""
    try:
        script_id = body.script_id

        def _runner():
            return get_iterative_experiment_service().apply_fl_script_template(
                project_id, experiment_id, script_id
            )

        job = await run_blocking(
            _start_long_job,
            project_id=project_id,
            experiment_id=experiment_id,
            kind=KIND_APPLY_FL_SCRIPT,
            runner=_runner,
            message="基于 FL 模板设计脚本已启动（后台执行）",
        )
        return success_response(job, message="基于 FL 模板设计已启动，后台执行中")
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/run-mode")
async def set_run_mode(project_id: str, experiment_id: str, body: RunModeBody):
    try:
        exp = await run_blocking(
            get_iterative_experiment_service().set_run_mode,
            project_id,
            experiment_id,
            body.run_mode,
        )
        return success_response(exp)
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/quality-mode")
async def set_quality_mode(project_id: str, experiment_id: str, body: QualityModeBody):
    try:
        exp = await run_blocking(
            get_iterative_experiment_service().set_quality_mode,
            project_id,
            experiment_id,
            body.quality_mode,
        )
        return success_response(exp)
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/run-iteration")
async def run_iteration(project_id: str, experiment_id: str):
    try:
        def _work():
            svc = get_iterative_experiment_service()
            record = svc.run_iteration(project_id, experiment_id)
            exp = svc.get(project_id, experiment_id)
            return {"record": record, "experiment": exp}

        return success_response(await run_blocking(_work))
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/run-to-completion")
async def run_to_completion(project_id: str, experiment_id: str):
    """启动跑到完成后台任务，立即返回 job_id；请轮询 jobs/{job_id}。"""
    try:
        def _runner():
            return get_iterative_experiment_service().run_to_completion(
                project_id, experiment_id
            )

        job = await run_blocking(
            _start_long_job,
            project_id=project_id,
            experiment_id=experiment_id,
            kind=KIND_RUN_TO_COMPLETION,
            runner=_runner,
            message="自动运行已启动（后台执行）",
        )
        return success_response(job, message="自动运行已启动，后台执行中")
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/feedback")
async def submit_feedback(project_id: str, experiment_id: str, body: FeedbackBody):
    try:
        exp = await run_blocking(
            get_iterative_experiment_service().submit_feedback,
            project_id,
            experiment_id,
            body.feedback,
        )
        return success_response(exp)
    except Exception as e:
        return _err(e)


@router.post("/projects/{project_id}/iterative-experiments/{experiment_id}/redesign")
async def redesign(project_id: str, experiment_id: str, body: FeedbackBody):
    """基于人工反馈重设计脚本：后台任务 + 轮询（与 design-script 同协议）。"""
    try:
        feedback = body.feedback

        def _runner():
            return get_iterative_experiment_service().redesign_from_feedback(
                project_id, experiment_id, feedback
            )

        job = await run_blocking(
            _start_long_job,
            project_id=project_id,
            experiment_id=experiment_id,
            kind=KIND_REDESIGN,
            runner=_runner,
            message="基于反馈重设计脚本已启动（后台执行）",
        )
        return success_response(job, message="基于反馈重设计已启动，后台执行中")
    except Exception as e:
        return _err(e)
