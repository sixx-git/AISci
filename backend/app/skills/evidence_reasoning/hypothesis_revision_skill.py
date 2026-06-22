"""假设修正 Skill — LLM 深度修订 + fact 白名单"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from app.core.config import get_settings
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()


class HypothesisRevisionSkill(BaseSkill):
    name = "HypothesisRevision"
    description = "基于支持/反对证据修正假设（LLM + fact 白名单）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        original = input_data.get("hypothesis", "")
        supporting = input_data.get("supporting_evidence", [])
        counter = input_data.get("counter_evidence", [])
        facts = input_data.get("facts", []) or []
        fact_whitelist: Set[str] = set(input_data.get("fact_whitelist") or [])
        for f in facts:
            fid = f.get("fact_id")
            if fid:
                fact_whitelist.add(str(fid))
        for ev in supporting + counter:
            eid = ev.get("evidence_id")
            if eid:
                fact_whitelist.add(str(eid))

        llm_revision = self._llm_revise(
            original, supporting, counter, fact_whitelist, input_data
        )
        if llm_revision:
            result.data = llm_revision
            return result

        result.data = self._rule_revise(original, supporting, counter)
        result.add_warning("LLM 修订不可用，已降级为规则修订")
        return result

    def _llm_revise(
        self,
        original: str,
        supporting: List[Dict[str, Any]],
        counter: List[Dict[str, Any]],
        fact_whitelist: Set[str],
        input_data: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        if settings.USE_MOCK_LLM or not settings.QWEN_API_KEY:
            return None
        try:
            from app.services.qwen_client import qwen_structured_chat

            support_lines = [
                f"- [{e.get('evidence_id', '?')}] {e.get('source_title', '')}: {str(e.get('claim', ''))[:120]}"
                for e in supporting[:6]
            ]
            counter_lines = [
                f"- [{e.get('evidence_id', '?')}] {e.get('source_title', '')}: {str(e.get('claim', ''))[:120]}"
                for e in counter[:4]
            ]
            whitelist_note = ", ".join(sorted(fact_whitelist)[:20]) or "（无 fact 白名单）"

            prompt = (
                f"原假设:\n{original}\n\n"
                f"支持证据:\n" + ("\n".join(support_lines) or "无") + "\n\n"
                f"反对证据:\n" + ("\n".join(counter_lines) or "无") + "\n\n"
                f"研究问题: {input_data.get('research_question', '')}\n"
                f"可用 fact_id 白名单（禁止引用名单外 ID）: {whitelist_note}\n\n"
                "请修订假设：融入反对证据的限制条件，保留可验证性；不得编造文献或 fact_id。"
            )
            schema = {
                "revised_hypothesis": "修订后的假设文本",
                "revision_reason": "修订理由",
                "what_changed": ["变更点1"],
                "remaining_risks": ["剩余风险1"],
                "cited_fact_ids": ["fact_id 仅限白名单内"],
            }
            raw = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema,
                prompt_version="hypothesis_revision",
                temperature=0.2,
            )
            cited = [
                str(fid) for fid in (raw.get("cited_fact_ids") or [])
                if str(fid) in fact_whitelist
            ]
            return {
                "original_hypothesis": original,
                "revision_reason": str(raw.get("revision_reason") or "证据平衡下修订"),
                "revised_hypothesis": str(raw.get("revised_hypothesis") or original),
                "what_changed": list(raw.get("what_changed") or ["LLM 深度修订"]),
                "remaining_risks": list(raw.get("remaining_risks") or ["需更多独立实验验证"]),
                "cited_fact_ids": cited,
                "revision_mode": "llm",
            }
        except Exception as exc:
            logger.warning("HypothesisRevision LLM 失败: %s", exc)
            return None

    @staticmethod
    def _rule_revise(
        original: str,
        supporting: List[Dict[str, Any]],
        counter: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        refute_claims = [c.get("claim", "") for c in counter if c.get("stance") == "refute"]
        support_titles = [s.get("source_title", "") for s in supporting[:2] if s.get("source_title")]

        what_changed: List[str] = []
        remaining_risks: List[str] = []
        revised = original

        if refute_claims:
            limitation = refute_claims[0][:120]
            revised = (
                f"{original.rstrip('。')}；但在以下条件下仍需谨慎验证：{limitation}"
            )
            what_changed.append("加入反对证据指出的限制条件")
            remaining_risks.extend(refute_claims[:3])
        elif counter:
            remaining_risks.append("存在中性/弱反对证据，假设边界需进一步界定")

        if support_titles and "基于" not in revised[:20]:
            revised = f"基于 {support_titles[0]} 等文献证据，{revised}"
            what_changed.append("补充支持文献来源表述")

        if not what_changed:
            what_changed.append("证据平衡下维持原假设表述")

        return {
            "original_hypothesis": original,
            "revision_reason": " ; ".join(refute_claims[:2]) if refute_claims else "支持证据占主导，微调表述",
            "revised_hypothesis": revised,
            "what_changed": what_changed,
            "remaining_risks": remaining_risks or ["需更多独立实验验证"],
            "revision_mode": "rule",
        }
