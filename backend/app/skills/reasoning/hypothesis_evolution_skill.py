"""
假设演化 Skill（借鉴 Co-Scientist EvolutionAgent）
——红蓝对抗后对排名靠前假设做 simplify / out_of_box，仅产出候选，不覆盖主假设。
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Sequence

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

STRATEGY_LABELS = {
    "simplify": "简化可行",
    "out_of_box": "跳出固有思维",
}


def _settings_tuple():
    from app.core.config import get_settings

    s = get_settings()
    enabled = bool(getattr(s, "HYPOTHESIS_EVOLUTION_ENABLED", True))
    top_k = int(getattr(s, "HYPOTHESIS_EVOLUTION_TOP_K", 5) or 5)
    raw = str(getattr(s, "HYPOTHESIS_EVOLUTION_STRATEGIES", "simplify,out_of_box") or "")
    strategies = [x.strip() for x in raw.split(",") if x.strip()]
    if not strategies:
        strategies = ["simplify", "out_of_box"]
    return enabled, max(1, min(top_k, 8)), strategies


def _hypothesis_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("hypothesis") or item.get("statement") or "").strip()
    return str(item or "").strip()


def _review_score(rev: Dict[str, Any]) -> float:
    try:
        return float(rev.get("overall_score") if rev.get("overall_score") is not None else 0)
    except (TypeError, ValueError):
        return 0.0


def _top_review_indices(reviews: Sequence[Dict[str, Any]], primary_index: int, top_k: int) -> List[int]:
    indexed = [(i, r) for i, r in enumerate(reviews) if isinstance(r, dict) and _hypothesis_text(r)]
    indexed.sort(key=lambda pair: _review_score(pair[1]), reverse=True)
    ordered = [i for i, _ in indexed[:top_k]]
    if primary_index not in ordered and 0 <= primary_index < len(reviews):
        ordered = [primary_index] + [i for i in ordered if i != primary_index]
        ordered = ordered[:top_k]
    return ordered


def _revision_hints(pro_con_evolution: Optional[Dict[str, Any]]) -> str:
    evo = pro_con_evolution or {}
    parts: List[str] = []
    for p in evo.get("revision_points") or []:
        if str(p).strip():
            parts.append(f"- {str(p).strip()}")
    patch = str(evo.get("hypothesis_patch") or "").strip()
    if patch:
        parts.append(f"- patch 提示: {patch[:300]}")
    for r in evo.get("remaining_risks") or []:
        if str(r).strip():
            parts.append(f"- 残留风险: {str(r).strip()}")
    return "\n".join(parts[:10]) if parts else "（无）"


def _run_strategy_llm(
    *,
    template_name: str,
    variables: Dict[str, Any],
    schema: Dict[str, Any],
    prompt_version: str,
) -> Dict[str, Any]:
    from app.services.prompt_loader import get_prompt_loader
    from app.services.qwen_client import qwen_structured_chat

    prompt = get_prompt_loader().render_template(template_name, variables)
    raw = qwen_structured_chat(
        prompt=prompt,
        schema_example=schema,
        temperature=0.35,
        prompt_version=prompt_version,
    )
    return raw if isinstance(raw, dict) else {}


def evolve_hypothesis_candidates(
    *,
    research_question: str,
    reviews: List[Dict[str, Any]],
    primary_index: int = 0,
    pro_con_evolution: Optional[Dict[str, Any]] = None,
    strategies: Optional[List[str]] = None,
    top_k: Optional[int] = None,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """同步生成演化候选；不修改传入的 reviews（内部 deepcopy 只读）。"""
    cfg_enabled, cfg_top_k, cfg_strategies = _settings_tuple()
    if enabled is None:
        enabled = cfg_enabled
    top_k = int(top_k if top_k is not None else cfg_top_k)
    strategies = list(strategies if strategies is not None else cfg_strategies)

    reviews_snap = copy.deepcopy(reviews or [])
    out: Dict[str, Any] = {
        "enabled": bool(enabled),
        "strategies_used": [],
        "candidates": [],
        "default_unchanged": True,
        "selected_candidate_id": None,
    }
    if not enabled:
        out["skipped"] = True
        out["reason"] = "HYPOTHESIS_EVOLUTION_ENABLED=false"
        return out
    if not reviews_snap:
        out["skipped"] = True
        out["reason"] = "无评审假设"
        return out

    try:
        primary_index = int(primary_index)
    except (TypeError, ValueError):
        primary_index = 0
    primary_index = min(max(0, primary_index), len(reviews_snap) - 1)
    primary_text = _hypothesis_text(reviews_snap[primary_index])
    if not primary_text:
        out["skipped"] = True
        out["reason"] = "主假设文本为空"
        return out

    top_indices = _top_review_indices(reviews_snap, primary_index, top_k)
    hints = _revision_hints(pro_con_evolution)
    review_ctx = (
        f"overall_score={_review_score(reviews_snap[primary_index])}; "
        f"suggestions={', '.join(str(s) for s in (reviews_snap[primary_index].get('suggestions') or [])[:3])}"
    )
    candidates: List[Dict[str, Any]] = []
    used: List[str] = []

    if "simplify" in strategies:
        try:
            raw = _run_strategy_llm(
                template_name="hypothesis_evolution_simplify",
                variables={
                    "research_question": research_question or "（未指定）",
                    "hypothesis": primary_text,
                    "review_context": review_ctx,
                    "revision_hints": hints,
                },
                schema={
                    "hypothesis": "简化后的一句话核心假设",
                    "rationale": "说明",
                    "parent_indices": [primary_index],
                },
                prompt_version="hypothesis_evolution_simplify_v1",
            )
            hyp = str(raw.get("hypothesis") or "").strip()
            if hyp:
                candidates.append(
                    {
                        "candidate_id": "evo_simplify_0",
                        "strategy": "simplify",
                        "strategy_label": STRATEGY_LABELS["simplify"],
                        "hypothesis": hyp,
                        "rationale": str(raw.get("rationale") or "").strip(),
                        "parent_indices": [primary_index],
                        "source_primary_index": primary_index,
                    }
                )
                used.append("simplify")
        except Exception as exc:
            logger.warning("[假设演化] simplify 失败: %s", exc)

    if "out_of_box" in strategies:
        try:
            lines = []
            for i in top_indices:
                text = _hypothesis_text(reviews_snap[i])
                if text:
                    lines.append(f"[#{i} score={_review_score(reviews_snap[i]):.1f}] {text}")
            inspiration = "\n".join(lines) if lines else primary_text
            raw = _run_strategy_llm(
                template_name="hypothesis_evolution_out_of_box",
                variables={
                    "research_question": research_question or "（未指定）",
                    "inspiration_block": inspiration,
                    "revision_hints": hints,
                },
                schema={
                    "hypothesis": "新假设",
                    "rationale": "说明",
                    "parent_indices": top_indices[:5],
                },
                prompt_version="hypothesis_evolution_out_of_box_v1",
            )
            hyp = str(raw.get("hypothesis") or "").strip()
            parents = raw.get("parent_indices")
            if not isinstance(parents, list) or not parents:
                parents = list(top_indices)
            parents = [int(p) for p in parents if str(p).isdigit() or isinstance(p, int)]
            if hyp:
                candidates.append(
                    {
                        "candidate_id": "evo_out_of_box_0",
                        "strategy": "out_of_box",
                        "strategy_label": STRATEGY_LABELS["out_of_box"],
                        "hypothesis": hyp,
                        "rationale": str(raw.get("rationale") or "").strip(),
                        "parent_indices": parents or top_indices,
                        "source_primary_index": primary_index,
                    }
                )
                used.append("out_of_box")
        except Exception as exc:
            logger.warning("[假设演化] out_of_box 失败: %s", exc)

    out["strategies_used"] = used
    out["candidates"] = candidates
    out["primary_index"] = primary_index
    out["top_indices"] = top_indices
    logger.info(
        "[假设演化] candidates=%s strategies=%s primary=%s",
        len(candidates),
        used,
        primary_index,
    )
    return out


def attach_evolution_to_review(
    review_result: Dict[str, Any],
    evolution: Dict[str, Any],
) -> Dict[str, Any]:
    """将演化结果写入 skill_outputs，不改 reviews 文本。"""
    result = review_result
    skill_outputs = dict(result.get("skill_outputs") or {})
    skill_outputs["hypothesis_evolution"] = evolution
    result["skill_outputs"] = skill_outputs
    return result


class HypothesisEvolutionSkill(BaseSkill):
    """红蓝对抗后假设演化：simplify + out_of_box 候选池。"""

    name = "HypothesisEvolution"
    description = "对排名靠前假设做简化/跳出固有思维演化，仅产出候选不覆盖主假设"
    source_reference = "Google AI Co-Scientist EvolutionAgent (simplify / out_of_box)"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        reviews = input_data.get("reviews") or context.get("reviews") or []
        primary_index = input_data.get("primary_index", context.get("primary_index", 0))
        research_question = (
            input_data.get("research_question")
            or context.get("research_question")
            or ""
        )
        pro_con = input_data.get("pro_con_evolution") or (
            ((input_data.get("pro_con") or {}).get("evolution"))
            if isinstance(input_data.get("pro_con"), dict)
            else None
        )
        # 快照：断言调用方 reviews 不被原地修改时，调用方应自行 deepcopy；此处不改传入列表元素
        reviews_before = [_hypothesis_text(r) for r in reviews if isinstance(r, dict)]

        data = evolve_hypothesis_candidates(
            research_question=str(research_question),
            reviews=list(reviews) if isinstance(reviews, list) else [],
            primary_index=int(primary_index) if primary_index is not None else 0,
            pro_con_evolution=pro_con if isinstance(pro_con, dict) else None,
            strategies=input_data.get("strategies"),
            top_k=input_data.get("top_k"),
            enabled=input_data.get("enabled"),
        )
        result.data = data

        reviews_after = [_hypothesis_text(r) for r in reviews if isinstance(r, dict)]
        if reviews_before != reviews_after:
            result.add_warning("输入 reviews 文本在演化过程中被外部修改（本 skill 不应改写）")
        if data.get("skipped"):
            result.add_warning(str(data.get("reason") or "演化跳过"))
        return result

