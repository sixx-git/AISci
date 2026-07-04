"""中文写作优化 Skill"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult

AI_TONE_PATTERNS = [
    re.compile(r"综上所述"),
    re.compile(r"值得注意的是"),
    re.compile(r"不可否认"),
    re.compile(r"在当今.*时代"),
    re.compile(r"随着.*的发展"),
    re.compile(r"赋能"),
    re.compile(r"助力"),
    re.compile(r"深度融合"),
]


class ChineseStyleDiagnosisSkill(BaseSkill):
    name = "ChineseStyleDiagnosis"
    description = "判断 AI 味、生硬表达、翻译腔、口号化"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        text = input_data.get("text") or input_data.get("content", "")
        issues: List[Dict[str, str]] = []
        for pat in AI_TONE_PATTERNS:
            for m in pat.finditer(text):
                issues.append({"type": "ai_tone", "span": m.group(), "pattern": pat.pattern})
        if len(text) > 50 and text.count("，") + text.count("。") < 2:
            issues.append({"type": "run_on", "span": text[:40], "pattern": "缺少断句"})
        score = max(0, 10 - min(10, len(issues)))
        result.data = {"style_score": score, "issues": issues[:20], "ai_flavor_risk": "high" if len(issues) >= 5 else "medium" if issues else "low"}
        return result


class HumanizeRewriteSkill(BaseSkill):
    name = "HumanizeRewrite"
    description = "按学术/汇报/本土/口语风格改写"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        text = input_data.get("text", "")
        style = input_data.get("style", "academic")
        style_map = {"academic": "学术", "report": "汇报", "local": "本土表达", "casual": "自然口语"}
        try:
            llm = qwen_structured_chat(
                prompt=f"将以下文本改写为{style_map.get(style, style)}风格，保持原意:\n{text[:3000]}",
                schema_example={"rewritten": "改写后文本", "style_applied": style},
                prompt_version="humanize_rewrite",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result


class RevisionReasonSkill(BaseSkill):
    name = "RevisionReason"
    description = "输出每处修改原因"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        original = input_data.get("original", "")
        revised = input_data.get("revised", "")
        try:
            llm = qwen_structured_chat(
                prompt=f"原文:\n{original[:2000]}\n\n修改后:\n{revised[:2000]}\n\n列出每处修改及原因。",
                schema_example={"revisions": [{"change": "...", "reason": "..."}]},
                prompt_version="revision_reason",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result


class MultiVersionRewriteSkill(BaseSkill):
    name = "MultiVersionRewrite"
    description = "生成保守版、自然版、正式版"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        text = input_data.get("text", "")
        try:
            llm = qwen_structured_chat(
                prompt=f"为以下段落生成三个版本（保守/自然/正式）:\n{text[:2500]}",
                schema_example={"conservative": "...", "natural": "...", "formal": "..."},
                prompt_version="multi_version_rewrite",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result


class ChineseGECCheckSkill(BaseSkill):
    name = "ChineseGECCheck"
    description = "语病、搭配、标点、冗余检测"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        text = input_data.get("text", "")
        issues: List[Dict[str, str]] = []
        if re.search(r"[,.!?;:]", text):
            issues.append({"type": "punctuation", "detail": "混用英文标点"})
        if "的的" in text or "了了" in text:
            issues.append({"type": "redundancy", "detail": "叠词冗余"})
        try:
            llm = qwen_structured_chat(
                prompt=f"检查以下中文文本的语病、搭配、标点问题:\n{text[:2500]}",
                schema_example={"errors": [{"type": "grammar", "text": "...", "suggestion": "..."}]},
                prompt_version="chinese_gec",
            )
            result.data = {"rule_issues": issues, **llm}
        except Exception as exc:
            result.data = {"rule_issues": issues, "errors": []}
            result.add_warning(str(exc))
        return result


class ToneControlSkill(BaseSkill):
    name = "ToneControl"
    description = "控制正式/自然/硕博论文/项目申报书风格"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        text = input_data.get("text", "")
        tone = input_data.get("tone", "formal")
        tone_guide = {
            "formal": "正式学术",
            "natural": "自然流畅",
            "thesis": "硕博论文",
            "grant": "项目申报书",
        }
        try:
            llm = qwen_structured_chat(
                prompt=f"将文本调整为「{tone_guide.get(tone, tone)}」语气:\n{text[:2500]}",
                schema_example={"adjusted_text": "...", "tone": tone, "notes": "调整说明"},
                prompt_version="tone_control",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result
