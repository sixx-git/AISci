"""
迭代实验科研叙事提炼 Skill
——把多轮 plan/decision/成败重组为可发表风格的阶段性/负结果叙事，禁止编造指标。
"""
from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

_POSITIVE_CLAIM_HINTS = ("成功验证", "充分验证", "显著提升", "证实了假设", "完美支持")

_ASSESSMENT_LABELS = {
    "significant_issue": "需重大调整",
    "major_issue": "需重大调整",
    "minor_issue": "需小幅调整",
    "needs_adjustment": "需调整",
    "ok": "基本达标",
    "success": "达标",
    "passed": "达标",
    "failed": "未达标",
    "error": "执行出错",
    "blocked": "受阻",
}


def _clip_text(text: str, limit: int) -> str:
    """按句读边界截断，避免半句收尾。"""
    s = (text or "").strip()
    if not s or len(s) <= limit:
        return s
    cut = s[:limit]
    for sep in ("。", "；", ";", "！", "？", "，", ","):
        pos = cut.rfind(sep)
        if pos >= int(limit * 0.55):
            end = pos + (1 if sep in "。；;！？" else 0)
            return cut[:end].rstrip("，,") + ("…" if end < len(s) else "")
    return cut.rstrip("，,;；") + "…"


def _humanize_assessment(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    key = re.sub(r"[\s_\-]+", "_", s.lower())
    key = key.replace("significantissue", "significant_issue")
    if key in _ASSESSMENT_LABELS:
        return _ASSESSMENT_LABELS[key]
    # 去掉 snake_case 下划线，避免 LaTeX 当成下标
    if re.fullmatch(r"[A-Za-z]+(?:_[A-Za-z0-9]+)+", s):
        return s.replace("_", " ")
    return s


def _format_decision_reason(reason: Any) -> str:
    if reason is None:
        return ""
    if isinstance(reason, (list, tuple)):
        parts = [str(x).strip() for x in reason if str(x).strip()]
        return "；".join(parts)
    s = str(reason).strip()
    if not s:
        return ""
    if s.startswith("["):
        try:
            parsed = ast.literal_eval(s if s.endswith("]") else (s + "]"))
            if isinstance(parsed, (list, tuple)):
                parts = [str(x).strip() for x in parsed if str(x).strip()]
                if parts:
                    return "；".join(parts)
        except (SyntaxError, ValueError):
            pass
        # 截断的 list 字面量：抽取引号片段
        quoted = re.findall(r"['\"]([^'\"]{3,})['\"]", s)
        if quoted:
            return "；".join(q.strip() for q in quoted if q.strip())
        s = re.sub(r"^\[\s*", "", s)
        s = re.sub(r"\s*\]$", "", s)
        s = s.replace("','", "；").replace('","', "；")
        s = s.replace("', '", "；").replace('", "', "；")
        s = s.replace("'", "").replace('"', "")
    return s


class IterationNarrativeSkill(BaseSkill):
    """迭代科研叙事提炼

    输入:
      - small_validation: dict（须含 narrative_brief 更佳）
      - hypothesis: str（可选，覆盖 sv.hypothesis）

    输出 (SkillResult.data):
      - story_arc: str
      - negative_or_partial_results_paragraph: str
      - method_boundary: str
      - next_experiments: List[str]
      - evidence_verdict: str
    """

    name = "IterationNarrative"
    description = "将迭代实验 timeline 提炼为科研叙事（负结果/阶段性结论），不伪造正面结果"
    source_reference = "迭代报告科研叙事方案 — synthesize_report_fields.narrative_brief"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        sv = input_data.get("small_validation") if isinstance(input_data.get("small_validation"), dict) else {}
        data = self.build_narrative(
            small_validation=sv,
            hypothesis=str(input_data.get("hypothesis") or sv.get("hypothesis") or ""),
        )
        result.data = data
        return result

    @classmethod
    def build_narrative(
        cls,
        *,
        small_validation: Dict[str, Any],
        hypothesis: str = "",
    ) -> Dict[str, Any]:
        """同步规则版（报告 agent 可直接调用，无需 await）。"""
        sv = small_validation or {}
        brief = sv.get("narrative_brief") if isinstance(sv.get("narrative_brief"), dict) else {}
        hyp = (hypothesis or brief.get("hypothesis") or sv.get("hypothesis") or "").strip()
        verdict = str(brief.get("evidence_verdict") or "").strip() or cls._infer_verdict(sv)
        timeline = brief.get("iteration_timeline") if isinstance(brief.get("iteration_timeline"), list) else []
        chain = brief.get("adjustment_chain") if isinstance(brief.get("adjustment_chain"), list) else []
        notes = brief.get("notes") if isinstance(brief.get("notes"), dict) else {}

        if not timeline:
            # 从 actual_results 回退构建简表
            actual = (sv.get("results") or {}).get("actual_results") or {}
            for r in list(actual.get("successful_iterations") or []) + list(actual.get("failed_iterations") or []):
                if isinstance(r, dict):
                    timeline.append(
                        {
                            "iteration_number": r.get("iteration_number"),
                            "status": r.get("status"),
                            "failed_round": str(r.get("status") or "").lower() in {"failed", "error"},
                            "plan_summary": r.get("plan_summary") or "",
                            "decision_reason": r.get("decision_reason") or "",
                            "overall_assessment": r.get("overall_assessment") or "",
                            "summary": r.get("summary") or "",
                        }
                    )
            timeline.sort(key=lambda x: int(x.get("iteration_number") or 0))

        story_parts: List[str] = []
        if hyp:
            story_parts.append(f"围绕假设「{_clip_text(hyp, 480)}」，开展了可执行的最小代理迭代实验。")
        else:
            story_parts.append("围绕既定科学假设，开展了可执行的最小代理迭代实验。")

        if timeline:
            arcs: List[str] = []
            for t in timeline[:8]:
                n = t.get("iteration_number")
                plan = str(t.get("plan_summary") or "").strip()
                assess = _humanize_assessment(
                    str(t.get("overall_assessment") or t.get("status") or "").strip()
                )
                reason = _format_decision_reason(t.get("decision_reason"))
                bit = f"第{n}轮"
                if plan:
                    bit += f"尝试「{_clip_text(plan, 280)}」"
                if t.get("failed_round"):
                    bit += "未达成功标准"
                elif assess:
                    bit += f"评估为「{_clip_text(assess, 40)}」"
                if reason:
                    bit += f"；随后调整依据：{_clip_text(reason, 360)}"
                arcs.append(bit)
            story_parts.append("演化路径：" + " → ".join(arcs) + "。")
        elif chain:
            cleaned_chain = [_format_decision_reason(c) or str(c) for c in chain[:6]]
            story_parts.append(
                "调整链：" + "；".join(_clip_text(c, 240) for c in cleaned_chain if c) + "。"
            )
        else:
            story_parts.append("当前可用轮次记录有限，叙事仅基于已注入的阶段性证据。")

        # 负结果 / 阶段性段落
        if verdict == "contradicted":
            neg = (
                "综合已跑轮次，现有协议下未能形成稳定支持假设的正向证据；"
                "失败与问题记录更宜解读为方法边界或假设可操作推论需修正，而非假设已被证实。"
            )
        elif verdict == "blocked":
            neg = "实验证据尚不足以支撑结论（无可用轮次或数据未绑定），正文仅能陈述预期路径。"
        elif verdict == "inconclusive":
            neg = (
                "当前结果属于阶段性/试探性证据"
                + ("（含需调整评估）" if notes.get("draft_needs_adjustment") else "")
                + ("，且含失败反例" if notes.get("has_negative_evidence") else "")
                + "，不得外推为充分验证。"
            )
        else:
            neg = (
                "已获得可引用的阶段性正向观测，但仍须在验证边界内解读："
                "代理实验支持可操作推论，不等于领域终极问题已彻底解决。"
            )

        boundary = (
            "本节为最小可执行代理实验（如表格学习/统计检验），用于检验假设的可操作推论；"
            "不等于完整领域解析、全物理模拟或多机联邦部署。"
        )
        if notes.get("smoke") or notes.get("partial_run"):
            boundary += " 证据层级为小样本或未跑满计划轮次，外推需谨慎。"

        next_exps: List[str] = []
        for c in chain[:4]:
            s = str(c).strip()
            m = re.match(r"^(第\d+轮)[:：]\s*(.*)$", s, flags=re.S)
            if m:
                s = f"{m.group(1)}调整：{_format_decision_reason(m.group(2))}"
            else:
                s = _format_decision_reason(s) or s
            if s and len(s) > 8:
                next_exps.append(f"针对既有调整信号继续收敛：{_clip_text(s, 280)}")
        if verdict in {"contradicted", "inconclusive"}:
            next_exps.append("收紧数据契约与评价指标，显式排除平凡解/泄漏后再复验。")
            next_exps.append("将失败轮次中的 identified_issues 转化为可检验的对照实验。")
        if not next_exps:
            next_exps.append("在保持验证边界声明的前提下扩展样本量或对照设置。")

        return {
            "story_arc": "".join(story_parts),
            "negative_or_partial_results_paragraph": neg,
            "method_boundary": boundary,
            "next_experiments": next_exps[:6],
            "evidence_verdict": verdict,
        }

    @staticmethod
    def _infer_verdict(sv: Dict[str, Any]) -> str:
        results = sv.get("results") if isinstance(sv.get("results"), dict) else {}
        rtype = str(results.get("result_type_summary") or "")
        actual = results.get("actual_results") if isinstance(results.get("actual_results"), dict) else {}
        failed = bool(actual.get("failed_iterations") or actual.get("counterexamples"))
        sandbox = sv.get("sandbox_execution") if isinstance(sv.get("sandbox_execution"), dict) else {}
        has_pos = bool(sandbox.get("success") or (sandbox.get("metrics") or {}) or (sv.get("artifacts") or {}).get("plots"))
        if rtype == "none" and not has_pos and not failed:
            return "blocked"
        if failed and not has_pos:
            return "contradicted"
        if sandbox.get("partial_run") or rtype == "has_negative_evidence":
            return "inconclusive"
        if has_pos:
            return "supported" if not failed else "inconclusive"
        return "inconclusive"

    @staticmethod
    def strip_overclaim(text: str, verdict: str) -> str:
        """若证据为否定/不确定，去掉过度正面措辞（不破坏「不得外推为充分验证」等限定句）。"""
        if verdict not in {"contradicted", "inconclusive", "blocked"}:
            return text
        out = text or ""
        # 先保护限定性否定句
        placeholders = {
            "__P1__": "不得外推为充分验证",
            "__P2__": "尚不足以充分验证",
            "__P3__": "不得外推为稳健验证",
            "__P4__": "不得外推为充分验证假设",
        }
        for key, phrase in placeholders.items():
            out = out.replace(phrase, key)
        for h in _POSITIVE_CLAIM_HINTS:
            out = out.replace(h, "尚待进一步验证")
        for key, phrase in placeholders.items():
            out = out.replace(key, phrase)
        out = out.replace("不得外推为尚待进一步验证", "不得外推为充分验证")
        out = out.replace("尚不足以尚待进一步验证", "尚不足以充分验证")
        return out
