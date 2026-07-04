"""一键生成报告 — 创建项目并自动跑全流程"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.schemas.pipeline import PipelineRunRequest
from app.schemas.project import ProjectCreate, QuickReportRequest
from app.services.pipeline_service import get_pipeline_service
from app.services.project_service import ProjectService
from app.core.domain_data_catalog import merge_domain_hints_into_config, parse_category_from_description

logger = logging.getLogger(__name__)

QUICK_REPORT_PIPELINE_OPTIONS: Dict[str, Any] = {
    "enable_quick_report": True,
    "pipeline_mode": "discovery",
    "enable_hitl_gate": False,
    "discovery_max_rounds": 3,
    "enable_gap_search": True,
    "enable_hf_auto_import": True,
    "enable_teaching_auto_refinement": False,
    "enable_plot_vlm_critique": True,
}


def build_research_question(question_name: str, file_description: str) -> str:
    qn = (question_name or "").strip()
    fd = (file_description or "").strip()
    return f"{qn}。数据与文件背景：{fd}"


class QuickReportService:
    def __init__(self, db: Session):
        self.db = db

    def start(self, body: QuickReportRequest) -> Dict[str, Any]:
        research_question = build_research_question(body.question_name, body.file_description)
        category = parse_category_from_description(body.file_description)
        project_svc = ProjectService(self.db)
        project = project_svc.create_project(
            ProjectCreate(
                name=body.question_name.strip(),
                description=body.file_description.strip(),
                research_question=research_question,
                research_domain=category or None,
                expected_output="科研报告（一键生成）",
                data_source=body.file_description.strip()[:500],
            )
        )
        config = dict(project.config or {})
        config["quick_report"] = True
        config["data_spec_hints"] = merge_domain_hints_into_config(
            {"data_need_note": body.file_description.strip()},
            research_domain=category,
            file_description=body.file_description.strip(),
        )
        project.config = config
        self.db.commit()
        self.db.refresh(project)

        pipeline_svc = get_pipeline_service(self.db)
        run_id = pipeline_svc.start_pipeline_async(
            PipelineRunRequest(
                project_id=project.id,
                research_question=research_question,
                options=dict(QUICK_REPORT_PIPELINE_OPTIONS),
            )
        )
        meta = pipeline_svc.db_pipeline_run.extra_metadata if isinstance(
            pipeline_svc.db_pipeline_run.extra_metadata, dict
        ) else {}
        meta["quick_report"] = True
        pipeline_svc.db_pipeline_run.extra_metadata = meta
        self.db.commit()

        return {
            "project_id": project.id,
            "run_id": run_id,
            "research_question": research_question,
            "status": "running",
        }

    def get_status(self, run_id: str) -> Dict[str, Any]:
        from app.models.pipeline import PipelineRun
        from app.services.external_candidate_service import (
            STATUS_PENDING,
            STATUS_MERGED,
            list_manual_candidates,
        )
        from app.services.data_finder_service import get_data_finder_service
        from app.services.dataset_service import DatasetService

        run = self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            raise ValueError(f"Pipeline run 未找到: {run_id}")

        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        status_lower = status_val.lower()
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else {}
        du_gate = meta.get("data_upload_gate") or {}

        pending_candidates: List[Dict[str, Any]] = []
        try:
            df = get_data_finder_service(self.db).load_results(run.project_id) or {}
            manual = list_manual_candidates(df.get("external_candidates"))
            pending_candidates = [
                {
                    "candidate_id": c.get("candidate_id"),
                    "dataset_name": c.get("dataset_name") or c.get("name"),
                    "source_platform": c.get("source_platform"),
                    "availability": c.get("availability"),
                    "url": c.get("url") or c.get("dataset_url"),
                    "user_upload_status": c.get("user_upload_status"),
                    "description": c.get("description"),
                }
                for c in manual
                if c.get("user_upload_status") == STATUS_PENDING
            ]
            uploaded_count = sum(
                1 for c in manual if c.get("user_upload_status") == STATUS_MERGED
            )
        except Exception as exc:
            logger.warning("读取待上传候选失败: %s", exc)
            uploaded_count = 0

        awaiting = bool(du_gate.get("paused")) or (
            status_lower == "human_review_required"
            and (
                bool(meta.get("data_upload_gate"))
                or bool(meta.get("quick_report"))
                or bool((run.input_data or {}).get("options", {}).get("enable_quick_report"))
            )
        )
        final_report_id = meta.get("final_report_id")
        can_resume = (
            awaiting and (uploaded_count >= 1 or bool(
                DatasetService(self.db).get_project_datasets(run.project_id)
            ))
        ) or (
            status_lower == "completed"
            and uploaded_count >= 1
        )

        return {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "status": status_val,
            "awaiting_data_upload": awaiting,
            "pending_upload_count": len(pending_candidates),
            "uploaded_count": uploaded_count,
            "can_resume": can_resume,
            "pending_candidates": pending_candidates,
            "final_report_id": final_report_id,
        }


def get_quick_report_service(db: Session) -> QuickReportService:
    return QuickReportService(db)
