"""
反事实预演 Skill（L0 定性）
在假设评审后、实验设计前，推演可证伪场景以识别失败模式。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.services.prompt_loader import get_prompt_loader
from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

_VALID_RISK = frozenset({"low", "medium", "high"})
_MECHANISM_ONLY = "mechanism_only"


def _norm_str(val: Any, limit: int = 500) -> str:
    return str(val or "").strip()[:limit]


def _valid_fact_ids(facts: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for f in facts:
        if not isinstance(f, dict):
            continue
        fid = _norm_str(f.get("fact_id") or f.get("id"), 120)
        if fid:
            ids.add(fid)
    return ids


def filter_falsify_scenarios(
    scenarios: List[Dict[str, Any]],
    *,
    valid_fact_ids: Optional[Set[str]] = None,
    hypothesis_text: str = "",
) -> List[Dict[str, Any]]:
    """FALSIFY 过滤：保留可证伪、有依据、能指导实验的场景。"""
    kept: List[Dict[str, Any]] = []
    hypo_lower = hypothesis_text.lower()
    for raw in scenarios:
        if not isinstance(raw, dict):
            continue
        intervention = _norm_str(raw.get("intervention"))
        question = _norm_str(raw.get("question"))
        outcome = _norm_str(raw.get("predicted_outcome"))
        cheap_test = _norm_str(raw.get("cheap_test"))
        if not intervention or not question or not outcome:
            continue
        if raw.get("falsifiable") is False:
            continue
        if not cheap_test:
            continue
        risk = _norm_str(raw.get("failure_risk"), 16).lower()
        if risk not in _VALID_RISK:
            risk = "medium"
        confidence = _norm_str(raw.get("confidence"), 16).lower()
        if confidence not in _VALID_RISK:
            confidence = "medium"

        fact_ids = [
            _norm_str(x, 120)
            for x in (raw.get("evidence_fact_ids") or [])
            if _norm_str(x, 120)
        ]
        has_evidence = False
        if fact_ids:
            if _MECHANISM_ONLY in fact_ids and len(fact_ids) == 1:
                has_evidence = bool(_norm_str(raw.get("decision_impact")))
            elif valid_fact_ids:
                has_evidence = any(fid in valid_fact_ids for fid in fact_ids)
            else:
                has_evidence = True

        if not has_evidence:
            continue

        decision_impact = _norm_str(raw.get("decision_impact"))
        if not decision_impact:
            continue

        aligned = True
        if hypo_lower:
            tokens = [t for t in re.split(r"\W+", hypo_lower) if len(t) > 3][:12]
            blob = f"{intervention} {question} {outcome}".lower()
            aligned = not tokens or any(t in blob for t in tokens)
        if not aligned:
            continue

        kept.append({
            "scenario_id": _norm_str(raw.get("scenario_id"), 32) or f"cf_{len(kept) + 1}",
            "intervention": intervention,
            "question": question,
            "predicted_outcome": outcome,
            "failure_risk": risk,
            "confidence": confidence,
            "evidence_fact_ids": fact_ids[:6],
            "cheap_test": cheap_test,
            "decision_impact": decision_impact,
            "falsifiable": True,
        })
    return kept[:4]


def build_counterfactual_feedback_constraints(preview: Optional[Dict[str, Any]]) -> List[str]:
    """将预演结果转为可注入实验设计的约束文本。"""
    if not isinstance(preview, dict) or preview.get("skipped"):
        return []
    constraints: List[str] = []
    summary = _norm_str(preview.get("summary"), 300)
    if summary:
        constraints.append(f"反事实预演摘要: {summary}")
    for fp in (preview.get("failure_predictions") or [])[:4]:
        text = _norm_str(fp, 240)
        if text:
            constraints.append(f"预演失败模式: {text}")
    for sc in (preview.get("scenarios") or [])[:3]:
        if not isinstance(sc, dict):
            continue
        if sc.get("failure_risk") == "high":
            constraints.append(
                f"高风险反事实 [{sc.get('scenario_id')}]: {sc.get('question')} → "
                f"建议对照/控制: {sc.get('cheap_test')}"
            )
    for pivot in (preview.get("recommended_pivots") or [])[:2]:
        text = _norm_str(pivot, 240)
        if text:
            constraints.append(f"预演转向建议: {text}")
    if preview.get("proceed_to_iterative_experiment") is False or preview.get(
        "proceed_to_experiment_design"
    ) is False:
        constraints.append(
            "反事实预演提示: 当前假设路径存在未缓解的高风险，实验设计须增加对照组或降级验证范围。"
        )
    return constraints


class CounterfactualPreviewSkill(BaseSkill):
    """L0 定性反事实预演 Skill。"""

    name = "CounterfactualPreview"
    description = "假设评审后的定性反事实预演，识别失败模式并指导实验对照设计"
    source_reference = "Counterfactual reasoning in scientific discovery — lightweight preview layer"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hr = input_data.get("hypothesis_review") or {}
        reviews = hr.get("reviews") or []
        if not reviews:
            result.data = {"skipped": True, "reason": "no_hypothesis_review"}
            return result

        primary_idx = hr.get("primary_index")
        if primary_idx is None:
            ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
            primary_idx = ensemble.get("target_hypothesis_index", 0)
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0
        primary_idx = min(max(0, primary_idx), len(reviews) - 1)
        best = reviews[primary_idx] if isinstance(reviews[primary_idx], dict) else {}

        hypothesis = _norm_str(best.get("hypothesis"), 1200)
        if not hypothesis:
            result.data = {"skipped": True, "reason": "empty_primary_hypothesis"}
            return result

        facts = input_data.get("literature_facts") or []
        if not isinstance(facts, list):
            facts = []
        valid_ids = _valid_fact_ids(facts)

        facts_lines = []
        for f in facts[:12]:
            if not isinstance(f, dict):
                continue
            fid = _norm_str(f.get("fact_id") or f.get("id"), 80)
            content = _norm_str(f.get("content") or f.get("text"), 200)
            if fid and content:
                facts_lines.append(f"- [{fid}] {content}")
        facts_text = "\n".join(facts_lines) or "（暂无结构化文献事实，请基于假设机制做保守推演并标注 mechanism_only）"

        ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
        review_bits = []
        if ensemble.get("decision"):
            review_bits.append(f"集成决策: {ensemble.get('decision')}")
        if ensemble.get("overall") is not None:
            review_bits.append(f"综合分: {ensemble.get('overall')}")
        if best.get("evidence_sufficiency"):
            review_bits.append(f"证据充分性: {best.get('evidence_sufficiency')}")
        review_summary = "；".join(review_bits) or "—"

        rq = _norm_str(
            input_data.get("research_question")
            or context.get("research_question"),
            800,
        )

        try:
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "counterfactual_preview",
                {
                    "research_question": rq or "—",
                    "primary_hypothesis": hypothesis,
                    "hypothesis_rationale": _norm_str(best.get("rationale"), 600) or "—",
                    "literature_facts": facts_text,
                    "review_summary": review_summary,
                },
            )
            schema = {
                "prediction_tier": "qualitative",
                "scenarios": [{
                    "scenario_id": "cf_1",
                    "intervention": "...",
                    "question": "...",
                    "predicted_outcome": "...",
                    "failure_risk": "medium",
                    "confidence": "medium",
                    "evidence_fact_ids": ["fact_1"],
                    "cheap_test": "...",
                    "decision_impact": "...",
                    "falsifiable": True,
                }],
                "failure_predictions": ["..."],
                "recommended_pivots": ["..."],
                "proceed_to_experiment_design": True,
                "proceed_to_iterative_experiment": True,
                "summary": "...",
            }
            llm = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema,
                prompt_version="counterfactual_preview",
            )
        except Exception as exc:
            logger.warning("CounterfactualPreviewSkill LLM 失败: %s", exc)
            result.add_warning(str(exc))
            result.data = {"skipped": True, "reason": "llm_error", "error": str(exc)[:200]}
            return result

        raw_scenarios = list(llm.get("scenarios") or [])
        filtered = filter_falsify_scenarios(
            raw_scenarios,
            valid_fact_ids=valid_ids,
            hypothesis_text=hypothesis,
        )
        if not filtered and raw_scenarios:
            result.add_warning(
                f"FALSIFY 过滤后无有效场景（原始 {len(raw_scenarios)} 条）"
            )

        failure_predictions = [
            _norm_str(x, 240) for x in (llm.get("failure_predictions") or []) if _norm_str(x, 240)
        ][:4]
        recommended_pivots = [
            _norm_str(x, 240) for x in (llm.get("recommended_pivots") or []) if _norm_str(x, 240)
        ][:2]

        proceed = bool(
            llm.get(
                "proceed_to_iterative_experiment",
                llm.get("proceed_to_experiment_design", True),
            )
        )
        if any(s.get("failure_risk") == "high" for s in filtered) and not failure_predictions:
            proceed = False

        result.data = {
            "prediction_tier": "qualitative",
            "primary_hypothesis_index": primary_idx,
            "scenarios": filtered,
            "raw_scenario_count": len(raw_scenarios),
            "failure_predictions": failure_predictions,
            "recommended_pivots": recommended_pivots,
            "proceed_to_experiment_design": proceed,
            "proceed_to_iterative_experiment": proceed,
            "summary": _norm_str(llm.get("summary"), 500),
            "skill": self.name,
        }
        result.metadata = {"filtered_count": len(filtered), "raw_count": len(raw_scenarios)}
        return result
