"""
开题报告科学逻辑审查 Skill
——检查矛盾→空白→内容→方法 逻辑链是否连贯。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

CONTRADICTION_HINTS = ("矛盾", "冲突", "不一致", "无法解释", "局限", "空白", "缺口")
BOUNDARY_HINTS = ("边界", "范围", "内部", "外部", "环境", "对象")
GAP_HINTS = ("空白", "缺口", "尚未", "未研究", "缺乏", "不足", "未知")
VERIFY_HINTS = ("验证", "实验", "测量", "指标", "对照", "baseline", "可重复", "假设")


def _chapter_text(report_data: Dict[str, Any], key: str) -> str:
    chapters = report_data.get("chapters") or {}
    value = chapters.get(key) or report_data.get(key) or ""
    if isinstance(value, (dict, list)):
        return str(value)
    return str(value).strip()


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(h in text or h.lower() in lower for h in hints)


class ProposalLogicReviewSkill(BaseSkill):
    """开题报告科学逻辑审查 Skill

    输入:
      - problem_understanding: dict
      - knowledge_gaps: dict | list
      - report_data: dict

    输出 (SkillResult.data):
      - logic_score: float 0-10
      - has_main_contradiction: bool
      - has_object_decomposition: bool
      - has_gap_to_content_chain: bool
      - has_verifiable_methods: bool
      - issues: List[str]
      - revision_hints: List[str]
    """

    name = "ProposalLogicReview"
    description = "审查开题报告科学逻辑链：矛盾、对象拆解、空白到内容、可验证方法"
    source_reference = "开题报告科学思维规范 — docs/SCIENTIFIC_PROPOSAL_LOGIC.md"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        pu = input_data.get("problem_understanding") or {}
        kg = input_data.get("knowledge_gaps") or {}
        report_data = input_data.get("report_data") or {}

        rule_issues, rule_hints, flags = self._rule_checks(pu, kg, report_data)

        llm_data: Dict[str, Any] = {}
        try:
            llm_data = self._llm_review(pu, kg, report_data, flags)
        except Exception as exc:
            logger.warning("ProposalLogicReview LLM 审查失败，仅使用规则结果: %s", exc)
            result.add_warning(f"科学逻辑 LLM 审查跳过: {exc}")

        issues = list(dict.fromkeys(rule_issues + list(llm_data.get("issues") or [])))
        revision_hints = list(dict.fromkeys(rule_hints + list(llm_data.get("revision_hints") or [])))

        has_main = bool(flags.get("has_main_contradiction"))
        has_object = bool(flags.get("has_object_decomposition"))
        has_gap_chain = bool(flags.get("has_gap_to_content_chain"))
        has_methods = bool(flags.get("has_verifiable_methods"))

        logic_score = float(llm_data.get("logic_score", self._score_from_flags(flags, len(issues))))

        if issues:
            result.add_warning(f"科学逻辑审查发现 {len(issues)} 项问题")

        result.data = {
            "logic_score": round(logic_score, 2),
            "has_main_contradiction": has_main,
            "has_object_decomposition": has_object,
            "has_gap_to_content_chain": has_gap_chain,
            "has_verifiable_methods": has_methods,
            "issues": issues[:10],
            "revision_hints": revision_hints[:8],
            "reviewer_summary": str(
                llm_data.get("reviewer_summary")
                or self._build_summary(flags, issues)
            ),
        }
        return result

    @staticmethod
    def _score_from_flags(flags: Dict[str, bool], issue_count: int) -> float:
        base = sum(2.5 for key in (
            "has_main_contradiction",
            "has_object_decomposition",
            "has_gap_to_content_chain",
            "has_verifiable_methods",
        ) if flags.get(key))
        penalty = min(issue_count * 0.8, 4.0)
        return max(0.0, min(10.0, base - penalty))

    @staticmethod
    def _build_summary(flags: Dict[str, bool], issues: List[str]) -> str:
        ok = [k for k, v in flags.items() if v]
        if len(ok) == 4 and not issues:
            return "科学逻辑链完整：矛盾、对象拆解、空白到内容、可验证方法均具备。"
        missing = []
        mapping = {
            "has_main_contradiction": "主要矛盾",
            "has_object_decomposition": "对象拆解",
            "has_gap_to_content_chain": "空白→内容链",
            "has_verifiable_methods": "可验证方法",
        }
        for key, label in mapping.items():
            if not flags.get(key):
                missing.append(label)
        return f"科学逻辑待加强：缺少 {', '.join(missing)}。" + (
            f" 首要问题：{issues[0]}" if issues else ""
        )

    def _rule_checks(
        self,
        pu: Dict[str, Any],
        kg: Dict[str, Any],
        report_data: Dict[str, Any],
    ) -> tuple[List[str], List[str], Dict[str, bool]]:
        issues: List[str] = []
        hints: List[str] = []

        main = str(pu.get("main_contradiction") or "").strip()
        ps = _chapter_text(report_data, "problem_statement")
        has_main = bool(main) or _contains_any(ps, CONTRADICTION_HINTS)
        if not has_main:
            issues.append("未明确主要矛盾（problem_understanding 与 problem_statement 均缺失）")
            hints.append("在 problem_statement 首段写清一个主要矛盾")

        ro = pu.get("research_object") if isinstance(pu.get("research_object"), dict) else {}
        internal = str(ro.get("internal") or "").strip()
        external = str(ro.get("external") or "").strip()
        boundary = str(ro.get("boundary") or "").strip() or str(pu.get("scope_boundary") or "").strip()
        scope = str(pu.get("scope_boundary") or "").strip()
        combined = " ".join([ps, scope, internal, external, boundary])
        has_object = bool(internal and external and boundary) or (
            _contains_any(combined, BOUNDARY_HINTS) and len(combined) > 40
        )
        if not has_object:
            issues.append("研究对象拆解不足（内/外/边界未写清）")
            hints.append("补充 research_object 或在 problem_statement 中定义内/外/边界")

        rationale = _chapter_text(report_data, "rationale")
        gaps_raw = kg.get("knowledge_gaps") if isinstance(kg, dict) else kg
        gap_text = ""
        if isinstance(gaps_raw, list):
            gap_text = " ".join(
                str(g.get("description", g) if isinstance(g, dict) else g) for g in gaps_raw
            )
        has_gap_chain = bool(gap_text) and _contains_any(rationale, GAP_HINTS + CONTRADICTION_HINTS)
        if not has_gap_chain:
            issues.append("rationale 未连贯呈现「已知事实→知识空白→假设」")
            hints.append("在 rationale 中按顺序写：已知事实、知识缺口、推理、科学假设")

        methods = _chapter_text(report_data, "methods")
        experiments = _chapter_text(report_data, "experiments")
        methods_text = f"{methods}\n{experiments}"
        has_methods = len(methods_text.strip()) > 80 and _contains_any(methods_text, VERIFY_HINTS)
        if not has_methods:
            issues.append("methods/experiments 缺少可验证的实验或测量设计")
            hints.append("在 methods 中写明验证手段、指标或对照方案")

        flags = {
            "has_main_contradiction": has_main,
            "has_object_decomposition": has_object,
            "has_gap_to_content_chain": has_gap_chain,
            "has_verifiable_methods": has_methods,
        }
        return issues, hints, flags

    def _llm_review(
        self,
        pu: Dict[str, Any],
        kg: Dict[str, Any],
        report_data: Dict[str, Any],
        flags: Dict[str, bool],
    ) -> Dict[str, Any]:
        preview = {
            "problem_statement": _chapter_text(report_data, "problem_statement")[:800],
            "rationale": _chapter_text(report_data, "rationale")[:800],
            "methods": _chapter_text(report_data, "methods")[:500],
            "main_contradiction": pu.get("main_contradiction", ""),
            "research_object": pu.get("research_object", {}),
        }
        prompt = (
            "你是开题报告科学逻辑审稿人。请评估以下材料是否遵循："
            "矛盾→对象拆解→现状/空白→研究内容→可验证方法。\n\n"
            f"## 规则预检\n{flags}\n\n"
            f"## 问题理解\n{preview.get('main_contradiction')}\n"
            f"对象: {preview.get('research_object')}\n\n"
            f"## 报告节选\n"
            f"problem_statement: {preview['problem_statement']}\n\n"
            f"rationale: {preview['rationale']}\n\n"
            f"methods: {preview['methods']}\n\n"
            f"## 知识缺口\n{kg}\n\n"
            "输出 logic_score(0-10)、issues、revision_hints、reviewer_summary。"
        )
        schema = {
            "logic_score": 7.0,
            "issues": ["示例问题"],
            "revision_hints": ["示例建议"],
            "reviewer_summary": "整体逻辑基本连贯",
        }
        return qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            prompt_version="proposal_logic_review",
        )
