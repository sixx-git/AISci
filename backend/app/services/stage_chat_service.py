"""阶段多轮问答修改 — 对话式迭代修订阶段输出 / 报告"""
from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.report_fields import (
    REPORT_SECTION_FIELDS,
    apply_report_dict,
    normalize_section_keys,
    report_orm_to_dict,
)
from app.models.pipeline import PipelineRun, PipelineStage, PipelineStageExecution
from app.services.qwen_client import qwen_structured_chat
from app.services.stage_human_loop_service import StageHumanLoopService, get_stage_meta

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))

# 完整重新生成（对话式主路径）
STAGE_CHAT_SCHEMA_FULL = {
    "explanation": "本轮修改说明",
    "changes_summary": ["变更点1"],
    "revised_output": {"完整修订后的阶段输出": "顶层字段须与当前版本一致"},
}

# 轻量化降级：仅返回需改字段
STAGE_CHAT_SCHEMA_DELTA = {
    "explanation": "修改说明",
    "changes_summary": ["变更1"],
    "output_delta": {"仅包含需要修改的字段片段": "将与当前输出深度合并"},
}

REPORT_REVISE_SCHEMA = {
    "explanation": "修改说明",
    "changes_summary": ["变更1"],
    "report_delta": {"仅包含需修改的章节键": "与当前报告深度合并"},
}

REPORT_SECTION_REVISE_SCHEMA = {
    "explanation": "修改说明",
    "changes_summary": ["变更1"],
    "revised_sections": {"chapter_key": "新内容"},
}

STAGE_ADVISORY_SCHEMA = {
    "answer": "对用户问题的详细回答（可解释图表、方法、结果含义等）",
    "related_suggestions": ["可选的补充建议或替代方案"],
}

CHAT_MODE_ADVISORY = "advisory"
CHAT_MODE_REVISE = "revise"

MAX_CHAT_TURNS_IN_PROMPT = 8
FULL_REGEN_SIZE_THRESHOLD = 10000


def _strip_control_chars(value: str) -> str:
    if not isinstance(value, str):
        return value
    return "".join(ch for ch in value if ch in "\n\r\t" or ord(ch) >= 32)


def _slim_value_for_prompt(value: Any, *, max_str: int = 1200, max_list: int = 8, depth: int = 0) -> Any:
    """压缩阶段输出用于 Prompt，避免超长与不可见控制字符。"""
    if depth > 6:
        return "[nested]"
    if isinstance(value, str):
        cleaned = _strip_control_chars(value)
        if len(cleaned) > max_str:
            return cleaned[:max_str] + "…[truncated]"
        return cleaned
    if isinstance(value, list):
        slimmed = [_slim_value_for_prompt(v, max_str=max_str, max_list=max_list, depth=depth + 1) for v in value[:max_list]]
        if len(value) > max_list:
            slimmed.append(f"…[+{len(value) - max_list} items]")
        return slimmed
    if isinstance(value, dict):
        return {
            str(k): _slim_value_for_prompt(v, max_str=max_str, max_list=max_list, depth=depth + 1)
            for k, v in list(value.items())[:40]
        }
    return value


def _json_for_prompt(value: Any, *, max_len: int = 12000) -> str:
    text = json.dumps(_slim_value_for_prompt(value), ensure_ascii=False, indent=2)
    if len(text) > max_len:
        return text[:max_len] + "\n…[truncated]"
    return text


def _estimate_json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False))
    except Exception:
        return 0


def _format_chat_history(chat_history: List[Dict[str, Any]]) -> str:
    if not chat_history:
        return "（尚无历史对话，这是第一轮）"
    lines: List[str] = []
    for turn in chat_history[-MAX_CHAT_TURNS_IN_PROMPT:]:
        user = str(turn.get("user_message") or "").strip()
        assistant = str(turn.get("assistant_explanation") or "").strip()
        if user:
            lines.append(f"用户: {_strip_control_chars(user)}")
        if assistant:
            lines.append(f"助手: {_strip_control_chars(assistant)}")
    return "\n".join(lines)


def _deep_merge(base: Any, delta: Any) -> Any:
    """将 LLM 返回的增量合并进当前输出。"""
    if delta is None:
        return copy.deepcopy(base)
    if isinstance(base, dict) and isinstance(delta, dict):
        merged = copy.deepcopy(base)
        for key, val in delta.items():
            if key in merged and isinstance(merged[key], (dict, list)) and isinstance(val, type(merged[key])):
                merged[key] = _deep_merge(merged[key], val)
            else:
                merged[key] = copy.deepcopy(val)
        return merged
    if isinstance(base, list) and isinstance(delta, list):
        merged = copy.deepcopy(base)
        for idx, item in enumerate(delta):
            if idx < len(merged):
                merged[idx] = _deep_merge(merged[idx], item)
            else:
                merged.append(copy.deepcopy(item))
        return merged
    return copy.deepcopy(delta)


def _coerce_revised_output(current: Dict[str, Any], revised: Any) -> Dict[str, Any]:
    """将完整 revised_output 与当前版本深度合并，保留未修改的嵌套字段。"""
    if not isinstance(revised, dict):
        return copy.deepcopy(current)
    return _deep_merge(current, revised)


def _build_conversational_prompt(
    *,
    stage: str,
    research_question: str,
    input_data: Optional[Dict[str, Any]],
    current_output: Dict[str, Any],
    chat_history: List[Dict[str, Any]],
    user_message: str,
    prefer_full_regen: bool,
) -> str:
    input_block = _json_for_prompt(input_data or {}, max_len=6000)
    output_block = _json_for_prompt(current_output, max_len=12000)
    history_block = _format_chat_history(chat_history)
    regen_hint = (
        "请基于原始输入、当前版本与全部对话历史，生成完整 revised_output（完整 JSON 对象）。"
        if prefer_full_regen
        else "输出较大，请返回 output_delta（仅含需修改字段），将与当前版本合并。"
    )
    return f"""你是科研助手，与用户多轮协作修订 Pipeline 阶段「{stage}」的输出，体验类似 AI 网页对话：每轮在当前版本上根据用户反馈继续更正。

研究问题：{_strip_control_chars(research_question or '')}

## 原始阶段输入（input_data，生成时的上下文）
{input_block}

## 当前工作版本（上一轮结果，请在此基础上修订）
{output_block}

## 对话历史
{history_block}

## 本轮用户要求
{_strip_control_chars(user_message)}

## 输出要求
1. {regen_hint}
2. revised_output / output_delta 的顶层字段须与当前版本一致，不要删除未提及的字段。
3. 仅根据用户要求修改相关内容；未提及部分尽量保持。
4. 字符串内用 \\n 表示换行，不要输出非法控制字符。
5. explanation 与 changes_summary 必填。"""


def _resolve_regenerate_result(
    current_output: Dict[str, Any],
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """从 LLM 响应解析修订结果（优先完整 revised_output，其次 output_delta）。"""
    revised_raw = parsed.get("revised_output")
    delta = parsed.get("output_delta")
    if isinstance(revised_raw, dict) and revised_raw:
        revised = _coerce_revised_output(current_output, revised_raw)
    elif isinstance(delta, dict) and delta:
        revised = _deep_merge(current_output, delta)
    else:
        revised = copy.deepcopy(current_output)
    return {
        "revised_output": revised,
        "explanation": str(parsed.get("explanation") or ""),
        "changes_summary": list(parsed.get("changes_summary") or []),
        "mode": "full" if isinstance(revised_raw, dict) and revised_raw else "delta",
    }


def _call_llm_for_revision(
    *,
    prompt: str,
    prefer_full_regen: bool,
    stage: str,
    attempt: str,
) -> Dict[str, Any]:
    if prefer_full_regen:
        return qwen_structured_chat(
            prompt=prompt,
            schema_example=STAGE_CHAT_SCHEMA_FULL,
            system_prompt=(
                "你是科研助手。根据多轮对话上下文，重新生成完整 revised_output。"
                "顶层 JSON 字段须与当前版本一致，仅修改用户要求的部分。"
            ),
            prompt_version=f"stage_chat_{stage}_{attempt}",
            temperature=0.35,
            max_tokens=8192,
        )
    return qwen_structured_chat(
        prompt=prompt,
        schema_example=STAGE_CHAT_SCHEMA_DELTA,
        system_prompt="根据对话上下文返回 output_delta，确保 JSON 合法可解析。",
        prompt_version=f"stage_chat_{stage}_{attempt}_delta",
        temperature=0.25,
        max_tokens=4096,
    )


def _build_advisory_prompt(
    *,
    stage: str,
    research_question: str,
    input_data: Optional[Dict[str, Any]],
    current_output: Dict[str, Any],
    chat_history: List[Dict[str, Any]],
    user_message: str,
) -> str:
    input_block = _json_for_prompt(input_data or {}, max_len=6000)
    output_block = _json_for_prompt(current_output, max_len=12000)
    history_block = _format_chat_history(chat_history)
    return f"""你是科研助手，用户正在查看 Pipeline 阶段「{stage}」的输出，与你进行**咨询对话**。

研究问题：{_strip_control_chars(research_question or '')}

## 阶段输入（生成时的上下文）
{input_block}

## 当前阶段输出（只读参考）
{output_block}

## 对话历史
{history_block}

## 用户问题
{_strip_control_chars(user_message)}

## 要求
1. 只回答问题、解释图表/指标/方法、给出建议或替代方案。
2. **不要**修改、重写或输出阶段 JSON；不要假装已经改了 Pipeline 结果。
3. 若信息不足，明确说明并给出可操作的下一步。
4. answer 与 related_suggestions 必填。"""


def _append_chat_record(
    stage_exec: PipelineStageExecution,
    *,
    user_message: str,
    explanation: str,
    changes_summary: List[str],
    revision_mode: str,
    applied: bool,
    mode: str,
) -> List[Dict[str, Any]]:
    meta = get_stage_meta(stage_exec)
    chat_record = {
        "id": str(uuid.uuid4()),
        "at": datetime.now(CHINA_TZ).isoformat(),
        "user_message": user_message,
        "assistant_explanation": explanation,
        "changes_summary": changes_summary,
        "revision_mode": revision_mode,
        "mode": mode,
        "applied": applied,
    }
    chat_history = list(meta.get("chat_history") or [])
    chat_history.append(chat_record)
    meta["chat_history"] = chat_history[-50:]
    stage_exec.extra_metadata = meta
    return meta["chat_history"]


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
        mode: str = CHAT_MODE_ADVISORY,
    ) -> Dict[str, Any]:
        normalized_mode = (mode or CHAT_MODE_ADVISORY).strip().lower()
        if normalized_mode == CHAT_MODE_ADVISORY or not apply_change:
            return self._advisory_chat(
                run_id=run_id,
                stage=stage,
                user_message=user_message,
                editor=editor,
            )
        return self._revise_chat(
            run_id=run_id,
            stage=stage,
            user_message=user_message,
            apply_change=apply_change,
            editor=editor,
        )

    def _advisory_chat(
        self,
        run_id: str,
        stage: str,
        user_message: str,
        editor: str = "user",
    ) -> Dict[str, Any]:
        detail = self.human_loop.get_stage_detail(run_id, stage)
        run = self._get_run(run_id)
        stage_exec = self._get_stage_exec(run_id, stage)
        meta = get_stage_meta(stage_exec)
        chat_history: List[Dict[str, Any]] = list(meta.get("chat_history") or [])

        current_output = detail.get("human_modified_output") or detail.get("output_data") or {}
        if not isinstance(current_output, dict):
            current_output = {"content": current_output}
        input_data = detail.get("input_data")
        if not isinstance(input_data, dict):
            input_data = {}

        prompt = _build_advisory_prompt(
            stage=stage,
            research_question=run.research_question or "",
            input_data=input_data,
            current_output=current_output,
            chat_history=chat_history,
            user_message=user_message,
        )

        try:
            parsed = qwen_structured_chat(
                prompt=prompt,
                schema_example=STAGE_ADVISORY_SCHEMA,
                system_prompt=(
                    "你是科研咨询助手。基于阶段上下文回答问题，"
                    "禁止修改 Pipeline 输出或输出 revised_output。"
                ),
                prompt_version=f"stage_advisory_{stage}",
                temperature=0.4,
                max_tokens=4096,
            )
            if not isinstance(parsed, dict):
                raise ValueError("模型返回非 JSON 对象")
            answer = str(parsed.get("answer") or "").strip()
            suggestions = [str(s) for s in (parsed.get("related_suggestions") or []) if s]
            if not answer:
                raise ValueError("模型未返回答案")
            explanation = answer
            if suggestions:
                explanation += "\n\n补充建议：\n" + "\n".join(f"- {s}" for s in suggestions)
            changes: List[str] = suggestions
        except Exception as exc:
            logger.warning("StageAdvisory 失败: %s", exc)
            explanation = f"咨询回答失败: {exc}"
            changes = []

        chat_history = _append_chat_record(
            stage_exec,
            user_message=user_message,
            explanation=explanation,
            changes_summary=changes,
            revision_mode="advisory",
            applied=False,
            mode=CHAT_MODE_ADVISORY,
        )
        self.db.commit()

        return {
            "run_id": run_id,
            "stage": stage,
            "user_message": user_message,
            "revised_output": current_output,
            "explanation": explanation,
            "changes_summary": changes,
            "applied": False,
            "chat_history": chat_history,
            "revision_mode": "advisory",
            "mode": CHAT_MODE_ADVISORY,
        }

    def _revise_chat(
        self,
        run_id: str,
        stage: str,
        user_message: str,
        apply_change: bool = True,
        editor: str = "user",
    ) -> Dict[str, Any]:
        detail = self.human_loop.get_stage_detail(run_id, stage)
        run = self._get_run(run_id)
        stage_exec = self._get_stage_exec(run_id, stage)
        meta = get_stage_meta(stage_exec)
        chat_history: List[Dict[str, Any]] = list(meta.get("chat_history") or [])

        current_output = detail.get("human_modified_output") or detail.get("output_data") or {}
        if not isinstance(current_output, dict):
            current_output = {"content": current_output}
        input_data = detail.get("input_data")
        if not isinstance(input_data, dict):
            input_data = {}

        prefer_full = _estimate_json_size(current_output) <= FULL_REGEN_SIZE_THRESHOLD
        prompt = _build_conversational_prompt(
            stage=stage,
            research_question=run.research_question or "",
            input_data=input_data,
            current_output=current_output,
            chat_history=chat_history,
            user_message=user_message,
            prefer_full_regen=prefer_full,
        )

        resolved: Dict[str, Any]
        revision_mode = "full" if prefer_full else "delta"
        try:
            parsed = _call_llm_for_revision(
                prompt=prompt,
                prefer_full_regen=prefer_full,
                stage=stage,
                attempt="v1",
            )
            if not isinstance(parsed, dict):
                raise ValueError("模型返回非 JSON 对象")
            resolved = _resolve_regenerate_result(current_output, parsed)
            if resolved["revised_output"] == current_output and not resolved.get("changes_summary"):
                raise ValueError("模型未产生有效修订")
        except Exception as exc:
            logger.warning("StageChat 首轮失败，尝试降级重试: %s", exc)
            try:
                fallback_full = not prefer_full
                retry_prompt = prompt + (
                    "\n\n请重新生成完整 revised_output，仅修改用户点名的内容。"
                    if fallback_full
                    else "\n\n仅修改用户点名的 1-2 个字段，output_delta 尽量短小。"
                )
                parsed = _call_llm_for_revision(
                    prompt=retry_prompt,
                    prefer_full_regen=fallback_full,
                    stage=stage,
                    attempt="retry",
                )
                if not isinstance(parsed, dict):
                    raise ValueError("重试返回非 JSON 对象")
                resolved = _resolve_regenerate_result(current_output, parsed)
                revision_mode = resolved.get("mode", "delta")
                if resolved["revised_output"] == current_output and not resolved.get("changes_summary"):
                    raise ValueError("重试未产生有效修订")
            except Exception as retry_exc:
                logger.warning("StageChat 重试仍失败: %s", retry_exc)
                resolved = {
                    "revised_output": current_output,
                    "explanation": f"自动修改失败: {retry_exc}",
                    "changes_summary": [],
                    "mode": "failed",
                }

        revised = resolved["revised_output"]
        explanation = resolved["explanation"]
        changes = resolved["changes_summary"]
        apply_failed = explanation.startswith("自动修改失败")

        if apply_change and not apply_failed:
            stage_exec = self.human_loop.save_human_edit(
                run_id=run_id,
                stage=stage,
                output_data=revised if isinstance(revised, dict) else {"content": revised},
                human_feedback=user_message,
                mark_reviewed=True,
                editor=editor,
                action="chat_apply",
            )

        chat_history = _append_chat_record(
            stage_exec,
            user_message=user_message,
            explanation=explanation,
            changes_summary=changes,
            revision_mode=revision_mode,
            applied=apply_change and not apply_failed,
            mode=CHAT_MODE_REVISE,
        )
        self.db.commit()

        return {
            "run_id": run_id,
            "stage": stage,
            "user_message": user_message,
            "revised_output": revised,
            "explanation": explanation,
            "changes_summary": changes,
            "applied": apply_change and not apply_failed,
            "chat_history": chat_history,
            "revision_mode": revision_mode,
            "mode": CHAT_MODE_REVISE,
        }

    def revise_report(
        self,
        project_id: str,
        report_id: str,
        user_message: str,
        editor: str = "user",
        section_keys: Optional[List[str]] = None,
        apply_change: bool = True,
    ) -> Dict[str, Any]:
        from app.models.project import Report

        report = self.db.query(Report).filter(Report.id == report_id, Report.project_id == project_id).first()
        if not report:
            raise ValueError("报告未找到")

        report_data = report_orm_to_dict(report)
        sections = normalize_section_keys(section_keys)
        scope_label = "、".join(sections) if sections else "整份报告（12 章节）"

        if sections:
            scoped = {k: _slim_value_for_prompt(report_data.get(k, ""), max_str=2000) for k in sections}
            prompt = f"""用户希望修改科研报告的指定章节，请仅更新下列字段。

目标章节：{scope_label}
用户反馈：{_strip_control_chars(user_message)}

当前章节内容（JSON）：
{json.dumps(scoped, ensure_ascii=False, indent=2)[:8000]}

只返回 revised_sections（被修改章节），不要输出完整报告。"""
            prompt_version = "report_revise_section"
        else:
            slim_report = _slim_value_for_prompt(report_data, max_str=1500, max_list=5)
            prompt = f"""用户希望修改科研报告，请仅返回 report_delta（需修改的章节片段）。

用户反馈：{_strip_control_chars(user_message)}

当前报告 JSON（供参考）：
{json.dumps(slim_report, ensure_ascii=False, indent=2)[:10000]}

report_delta 将与原报告深度合并；不要重复未修改章节。"""
            prompt_version = "report_revise"

        try:
            parsed = qwen_structured_chat(
                prompt=prompt,
                schema_example=REPORT_SECTION_REVISE_SCHEMA if sections else REPORT_REVISE_SCHEMA,
                system_prompt="你是科研写作助手，根据用户反馈修订报告章节，禁止编造文献与实验数据。",
                prompt_version=prompt_version,
                temperature=0.35,
            )
            if not isinstance(parsed, dict):
                raise ValueError("模型返回非 JSON 对象")
        except Exception as exc:
            raise ValueError(f"报告修改失败: {exc}") from exc

        if sections:
            revised_partial = parsed.get("revised_sections") or {}
            if not isinstance(revised_partial, dict):
                revised_partial = {}
            revised = dict(report_data)
            for key in sections:
                if key in revised_partial:
                    revised[key] = revised_partial[key]
        else:
            delta = parsed.get("report_delta")
            legacy = parsed.get("revised_report")
            if isinstance(delta, dict) and delta:
                revised = _deep_merge(report_data, delta)
            elif isinstance(legacy, dict) and legacy:
                revised = legacy
            else:
                revised = report_data

        explanation = parsed.get("explanation", "")
        changes = parsed.get("changes_summary") or []

        chat_record = {
            "id": str(uuid.uuid4()),
            "at": datetime.now(CHINA_TZ).isoformat(),
            "editor": editor,
            "user_message": user_message,
            "assistant_explanation": explanation,
            "changes_summary": changes,
            "section_keys": sections,
            "applied": apply_change,
        }

        meta = report.extra_metadata if isinstance(report.extra_metadata, dict) else {}
        chat_history = list(meta.get("chat_history") or [])
        chat_history.append(chat_record)
        meta["chat_history"] = chat_history[-50:]

        if not apply_change:
            return {
                "report_id": report_id,
                "revised_report": revised,
                "explanation": explanation,
                "changes_summary": changes,
                "section_keys": sections,
                "applied": False,
                "chat_history": meta["chat_history"],
            }

        history = list(meta.get("revision_history") or [])
        history.append(
            {
                "id": chat_record["id"],
                "at": chat_record["at"],
                "editor": editor,
                "user_message": user_message,
                "explanation": explanation,
                "changes_summary": changes,
                "section_keys": sections,
                "previous_report": copy.deepcopy(report_data),
            }
        )
        meta["revision_history"] = history[-30:]
        meta["last_human_feedback"] = user_message

        apply_report_dict(report, revised)
        report.extra_metadata = meta
        if revised.get("title") or revised.get("paper_title"):
            report.title = str(revised.get("title") or revised.get("paper_title") or report.title)
        report.updated_at = datetime.now(CHINA_TZ)
        self.db.commit()

        pdf_regen: Optional[Dict[str, Any]] = None
        if report.pdf_path:
            try:
                from app.services.report_service import ReportService

                pdf_regen = ReportService(self.db).regenerate_pdf(report_id)
                self.db.refresh(report)
            except Exception as exc:
                logger.warning("修订后 PDF 重新生成失败 report=%s: %s", report_id, exc)

        return {
            "report_id": report_id,
            "revised_report": revised,
            "explanation": explanation,
            "changes_summary": changes,
            "section_keys": sections,
            "revision_history": meta["revision_history"],
            "chat_history": meta["chat_history"],
            "applied": True,
            "pdf_success": (pdf_regen or {}).get("pdf_success"),
            "export_method": (pdf_regen or {}).get("export_method"),
        }

    def _get_run(self, run_id: str) -> PipelineRun:
        run = self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            raise ValueError(f"run 未找到: {run_id}")
        return run

    def _get_stage_exec(self, run_id: str, stage: str) -> PipelineStageExecution:
        run = self._get_run(run_id)
        stage_enum = PipelineStage(stage)
        stage_exec = (
            self.db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == run.id,
                PipelineStageExecution.stage == stage_enum,
            )
            .first()
        )
        if not stage_exec:
            raise ValueError(f"阶段 {stage} 不存在于 run {run_id}")
        return stage_exec


def get_stage_chat_service(db: Session) -> StageChatService:
    return StageChatService(db)
