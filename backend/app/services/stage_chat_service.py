"""阶段多轮问答修改 — 基于用户反馈 refine 阶段输出"""
from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineRun, PipelineStage, PipelineStageExecution
from app.services.qwen_client import qwen_structured_chat
from app.services.stage_human_loop_service import StageHumanLoopService, get_stage_meta

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class StageChatService:
    def __init__(self, db: Session):
        self.db = db
        self.human_loop = StageHumanLoopService(db)

    def chat(
        self,
        run_id: str,
        stage: str,
        user_message: str,
        apply_change: bool = True,
        editor: str = "user",
    ) -> Dict[str, Any]:
        detail = self.human_loop.get_stage_detail(run_id, stage)
        run = self._get_run(run_id)
        current_output = detail.get("human_modified_output") or detail.get("output_data") or {}

        prompt = f"""你是科研助手，帮助用户修改 Pipeline 阶段「{stage}」的输出。

研究问题：{run.research_question}

当前阶段输出（JSON）：
{json.dumps(current_output, ensure_ascii=False, indent=2)[:10000]}

用户反馈/要求：
{user_message}

请输出修改后的完整 JSON（保持与原结构兼容），并简要说明修改点。
返回格式：
{{
  "revised_output": {{...完整阶段输出...}},
  "explanation": "修改说明",
  "changes_summary": ["变更1", "变更2"]
}}"""

        try:
            raw = qwen_structured_chat(
                messages=[{"role": "user", "content": prompt}],
                prompt_version=f"stage_chat_{stage}",
                temperature=0.4,
            )
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            logger.warning(f"StageChat LLM 失败: {exc}")
            parsed = {
                "revised_output": current_output,
                "explanation": f"自动修改失败: {exc}",
                "changes_summary": [],
            }

        revised = parsed.get("revised_output") or current_output
        explanation = parsed.get("explanation", "")
        changes = parsed.get("changes_summary") or []

        chat_record = {
            "id": str(uuid.uuid4()),
            "at": datetime.now(CHINA_TZ).isoformat(),
            "user_message": user_message,
            "assistant_explanation": explanation,
            "changes_summary": changes,
        }

        if apply_change:
            stage_exec = self.human_loop.save_human_edit(
                run_id=run_id,
                stage=stage,
                output_data=revised if isinstance(revised, dict) else {"content": revised},
                human_feedback=user_message,
                mark_reviewed=True,
                editor=editor,
            )
            meta = get_stage_meta(stage_exec)
            chat_history = list(meta.get("chat_history") or [])
            chat_history.append(chat_record)
            meta["chat_history"] = chat_history[-50:]
            stage_exec.extra_metadata = meta
            self.db.commit()

        return {
            "run_id": run_id,
            "stage": stage,
            "user_message": user_message,
            "revised_output": revised,
            "explanation": explanation,
            "changes_summary": changes,
            "applied": apply_change,
        }

    def revise_report(
        self,
        project_id: str,
        report_id: str,
        user_message: str,
        editor: str = "user",
    ) -> Dict[str, Any]:
        from app.models.project import Report

        report = self.db.query(Report).filter(Report.id == report_id, Report.project_id == project_id).first()
        if not report:
            raise ValueError("报告未找到")

        report_data = report.report_data if isinstance(report.report_data, dict) else {}
        prompt = f"""用户希望修改科研报告，请根据反馈更新报告 JSON 字段（12 章节结构保持不变）。

用户反馈：
{user_message}

当前报告 JSON：
{json.dumps(report_data, ensure_ascii=False, indent=2)[:12000]}

返回：
{{
  "revised_report": {{...}},
  "explanation": "...",
  "changes_summary": ["..."]
}}"""

        try:
            raw = qwen_structured_chat(
                messages=[{"role": "user", "content": prompt}],
                prompt_version="report_revise",
                temperature=0.35,
            )
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            raise ValueError(f"报告修改失败: {exc}") from exc

        revised = parsed.get("revised_report") or report_data
        meta = report.extra_metadata if isinstance(report.extra_metadata, dict) else {}
        history = list(meta.get("revision_history") or [])
        history.append(
            {
                "id": str(uuid.uuid4()),
                "at": datetime.now(CHINA_TZ).isoformat(),
                "editor": editor,
                "user_message": user_message,
                "explanation": parsed.get("explanation", ""),
                "changes_summary": parsed.get("changes_summary") or [],
                "previous_report": copy.deepcopy(report_data),
            }
        )
        meta["revision_history"] = history[-30:]
        meta["last_human_feedback"] = user_message
        report.report_data = revised
        report.extra_metadata = meta
        if report.markdown_content and isinstance(revised, dict):
            report.markdown_content = revised.get("markdown_content") or report.markdown_content
        report.updated_at = datetime.now(CHINA_TZ)
        self.db.commit()

        return {
            "report_id": report_id,
            "revised_report": revised,
            "explanation": parsed.get("explanation", ""),
            "changes_summary": parsed.get("changes_summary") or [],
            "revision_history": meta["revision_history"],
        }

    def _get_run(self, run_id: str) -> PipelineRun:
        run = self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            raise ValueError(f"run 未找到: {run_id}")
        return run


def get_stage_chat_service(db: Session) -> StageChatService:
    return StageChatService(db)
