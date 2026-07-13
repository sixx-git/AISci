"""
结果验证 Skill
参考能力：AI Scientist result verification
——验证小样验证/初步分析结果是否与假设和实验设计一致，拒绝无数据支撑的结论。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.experiment_spec_service import is_proxy_validation_metrics
from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class ResultVerificationSkill(BaseSkill):
    """结果验证 Skill

    输入:
      - hypothesis: str
      - experiment_design: dict
      - preliminary_analysis: dict      PreliminaryAnalysisSkill 输出
      - expected_results: str
      - modeling_results: List[dict]

    输出 (SkillResult.data):
      - verified: bool
      - confidence: float               0-1
      - issues: List[str]
      - matched_metrics: List[str]
      - data_backed: bool
      - verification_summary: str
    """

    name = "ResultVerification"
    description = "验证初步分析结果是否有真实数据支撑并与假设一致"
    source_reference = "AI Scientist (arxiv:2408.06292) — automated result verification"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = (input_data.get("hypothesis") or "").strip()
        design = input_data.get("experiment_design") or {}
        pa = input_data.get("preliminary_analysis") or {}
        expected = (input_data.get("expected_results") or design.get("expected_results") or "").strip()
        modeling = input_data.get("modeling_results") or []
        sandbox = input_data.get("sandbox_execution") or {}
        pilot = input_data.get("pilot_analysis") or {}
        spec_alignment = input_data.get("spec_alignment") or {}
        has_real_flag = input_data.get("has_real_data") in (1, True, "1", "true")

        data_flag = pa.get("data_source_flag", "no_data")
        sb_metrics = sandbox.get("metrics") if isinstance(sandbox.get("metrics"), dict) else {}
        is_proxy = (
            sandbox.get("pilot_fallback")
            or is_proxy_validation_metrics(sb_metrics)
            or spec_alignment.get("aligned") is False
        )
        sandbox_ok = bool(sandbox.get("success")) and bool(
            sandbox.get("output_complete") or sandbox.get("plots") or sandbox.get("metrics")
        ) and not is_proxy
        pilot_ok = bool(pilot.get("success")) and not pilot.get("pilot_fallback")
        sb_plots = sandbox.get("plots") if isinstance(sandbox.get("plots"), list) else []
        if is_proxy:
            has_real = bool(modeling)
        else:
            has_real = (
                data_flag == "real_data"
                or bool(modeling)
                or has_real_flag
                or sandbox_ok
                or pilot_ok
            )
        stats = pa.get("summary_statistics") or {}
        plots = list(pa.get("plots") or [])
        if sb_plots:
            plots = plots + sb_plots
        preliminary = pa.get("preliminary_result") or {}

        issues: List[str] = []
        matched_metrics: List[str] = []

        if not has_real:
            issues.append("无真实数据支撑，结果为模拟或空")
        if data_flag == "simulated":
            issues.append("检测到模拟数据，不可作为最终结论")
        if is_proxy:
            issues.append("结果为代理统计或 pilot 兜底，未完成 experiment_spec 对齐的假设验证")
        if spec_alignment.get("aligned") is False and spec_alignment.get("reason"):
            issues.append(str(spec_alignment.get("reason")))

        metrics_text = (design.get("metrics") or "").lower()
        for key in stats.keys() if isinstance(stats, dict) else []:
            if key.lower() in metrics_text or any(m in key.lower() for m in ("accuracy", "f1", "auc", "loss")):
                matched_metrics.append(key)

        if isinstance(sb_metrics, dict):
            for key, val in sb_metrics.items():
                if key in ("note", "stdout_preview", "warning"):
                    continue
                if val is not None and str(val).strip() != "":
                    matched_metrics.append(str(key))

        for plot in plots[:5]:
            if isinstance(plot, dict) and plot.get("metric"):
                matched_metrics.append(str(plot["metric"]))

        matched_metrics = list(dict.fromkeys(matched_metrics))

        try:
            prompt = (
                "你是科研结果验证专家。请判断以下初步结果是否可信、是否与假设一致。\n\n"
                f"## 假设\n{hypothesis or '—'}\n\n"
                f"## 期望结果\n{expected[:500] or '—'}\n\n"
                f"## 数据状态\n- data_source_flag: {data_flag}\n"
                f"- has_modeling: {bool(modeling)}\n"
                f"- has_real_data_flag: {has_real_flag}\n"
                f"- sandbox_success: {sandbox.get('success')}\n"
                f"- sandbox_output_complete: {sandbox.get('output_complete')}\n"
                f"- spec_aligned: {spec_alignment.get('aligned')}\n"
                f"- pilot_success: {pilot_ok}\n"
                f"- matched_metrics: {matched_metrics}\n\n"
                f"## 统计摘要\n{str(stats)[:800]}\n\n"
                f"## 初步结论\n{str(preliminary)[:600]}\n\n"
                "若缺乏真实数据，必须标记 verified=false。"
            )
            schema = {
                "verified": has_real and (len(matched_metrics) > 0 or sandbox_ok or pilot_ok),
                "confidence": 0.7 if has_real else 0.2,
                "issues": issues,
                "verification_summary": "结果与假设方向一致" if has_real else "缺少真实数据验证",
            }
            llm = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema,
                prompt_version="result_verification",
            )

            verified = bool(llm.get("verified", False)) and has_real and not is_proxy
            if has_real and sandbox_ok and matched_metrics and spec_alignment.get("aligned") is not False:
                verified = True
            confidence = float(llm.get("confidence", 0.5 if verified else 0.2))
            llm_issues = list(llm.get("issues") or [])
            all_issues = list(dict.fromkeys(issues + llm_issues))

            if not verified:
                result.add_warning("结果验证未通过：" + (all_issues[0] if all_issues else "数据不足"))

            result.data = {
                "verified": verified,
                "confidence": round(confidence, 4),
                "issues": all_issues,
                "matched_metrics": matched_metrics,
                "data_backed": has_real,
                "verification_summary": str(llm.get("verification_summary", "")),
            }
            return result

        except Exception as e:
            logger.exception("ResultVerificationSkill 异常: %s", e)
            result.add_error(f"结果验证异常: {e}")
            result.data = {
                "verified": False,
                "confidence": 0.0,
                "issues": issues + [str(e)],
                "matched_metrics": matched_metrics,
                "data_backed": has_real,
                "verification_summary": "验证过程异常",
            }
            return result
