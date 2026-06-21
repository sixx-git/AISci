"""集成评审 — 多评审者聚合（借 AI Scientist Automated Reviewer）"""
from __future__ import annotations

import asyncio
import logging
import statistics
from typing import Any, Dict, List, Optional

from app.skills.mentor_review_skill import MentorReviewSkill

logger = logging.getLogger(__name__)

REVIEWER_WEIGHTS = {
    "primary_llm": 0.40,
    "mentor": 0.25,
    "novelty": 0.20,
    "evidence": 0.15,
}


class EnsembleReviewService:
    """聚合主 LLM 评审、导师评审、新颖性、证据规则Reviewer。"""

    async def run_ensemble(
        self,
        reviews: List[Dict[str, Any]],
        *,
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        research_question: str = "",
        novelty_outputs: Optional[Dict[str, Any]] = None,
        primary_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not reviews:
            return {"ensemble_reviews": [], "aggregated": {}, "decision": "Reject"}

        idx = primary_index if primary_index is not None else 0
        idx = min(idx, len(reviews) - 1)
        target_review = reviews[idx]
        target_hypo = (hypotheses or [{}])[idx] if hypotheses and idx < len(hypotheses) else {}

        ensemble_members: List[Dict[str, Any]] = []

        primary_score = float(target_review.get("overall_score") or 0)
        ensemble_members.append({
            "reviewer_id": "primary_llm",
            "type": "llm_structured",
            "weight": REVIEWER_WEIGHTS["primary_llm"],
            "overall_score": primary_score,
            "scores": self._extract_dimension_scores(target_review),
        })

        mentor_review = await self._run_mentor(target_hypo, target_review, research_question)
        raw_readiness = mentor_review.get("readiness_score")
        if raw_readiness is not None:
            mentor_score = float(raw_readiness) / 10.0
        else:
            mentor_score = primary_score
        ensemble_members.append({
            "reviewer_id": "mentor",
            "type": "mentor_simulation",
            "weight": REVIEWER_WEIGHTS["mentor"],
            "overall_score": round(mentor_score, 2),
            "review": mentor_review,
        })

        novelty_score = self._novelty_aggregate(novelty_outputs, idx)
        ensemble_members.append({
            "reviewer_id": "novelty",
            "type": "novelty_skill",
            "weight": REVIEWER_WEIGHTS["novelty"],
            "overall_score": novelty_score,
        })

        evidence_score = self._evidence_rule_score(target_hypo)
        ensemble_members.append({
            "reviewer_id": "evidence",
            "type": "rule_based",
            "weight": REVIEWER_WEIGHTS["evidence"],
            "overall_score": evidence_score,
        })

        aggregated_overall = round(
            sum(m["overall_score"] * m["weight"] for m in ensemble_members)
            / sum(m["weight"] for m in ensemble_members),
            2,
        )
        decision = "Accept" if aggregated_overall >= 6.5 else "Reject"
        disagreement = self._disagreement_flags(ensemble_members)

        weaknesses: List[str] = list(mentor_review.get("weaknesses") or [])[:3]
        weaknesses.extend((target_review.get("weaknesses") or [])[:2])

        return {
            "ensemble_reviews": ensemble_members,
            "aggregated": {
                "overall_score": aggregated_overall,
                "decision": decision,
                "consensus_score": aggregated_overall,
                "disagreement_flags": disagreement,
                "needs_human_review": bool(disagreement) or aggregated_overall < 6.0,
            },
            "decision": decision,
            "overall": aggregated_overall,
            "weaknesses": weaknesses[:6],
            "revision_suggestions": list(mentor_review.get("revision_suggestions") or [])[:5],
            "target_hypothesis_index": idx,
        }

    def run_ensemble_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_ensemble(**kwargs))

    @staticmethod
    async def _run_mentor(hypo: Dict, review: Dict, research_question: str) -> Dict[str, Any]:
        skill = MentorReviewSkill()
        content = {**hypo, "review_scores": review.get("scores"), "overall_score": review.get("overall_score")}
        try:
            result = await skill.run(
                {
                    "target_type": "hypothesis",
                    "content": content,
                    "research_question": research_question,
                    "user_notes": "",
                },
                {},
            )
            return result.data.get("review") or {}
        except Exception as exc:
            logger.warning(f"Mentor ensemble 失败: {exc}")
            return {"readiness_score": int(review.get("overall_score", 5) * 10), "weaknesses": [], "revision_suggestions": []}

    @staticmethod
    def _extract_dimension_scores(review: Dict[str, Any]) -> Dict[str, float]:
        scores = review.get("scores") or {}
        out = {}
        for k, v in scores.items():
            if isinstance(v, dict) and "score" in v:
                out[k] = float(v["score"])
            elif isinstance(v, (int, float)):
                out[k] = float(v)
        return out

    @staticmethod
    def _novelty_aggregate(novelty_outputs: Optional[Dict], index: int) -> float:
        if not novelty_outputs:
            return 6.0
        block = novelty_outputs.get("hypothesis_novelty_review") or novelty_outputs
        entry = block.get(f"hypothesis_{index}") or {}
        data = entry.get("data") or {}
        score = data.get("novelty_score") or data.get("overall_novelty")
        if score is not None:
            try:
                return float(score)
            except (TypeError, ValueError):
                pass
        return 6.5 if entry.get("success") else 5.0

    @staticmethod
    def _evidence_rule_score(hypo: Dict[str, Any]) -> float:
        level = str(hypo.get("evidence_level") or "medium").lower()
        base = {"high": 8.5, "medium": 6.5, "low": 4.0}.get(level, 5.5)
        refs = len(hypo.get("supporting_fact_ids") or [])
        base += min(1.5, refs * 0.3)
        if hypo.get("dataset_field_refs") or hypo.get("data_evidence_ids"):
            base += 0.5
        return round(min(10.0, base), 2)

    @staticmethod
    def _disagreement_flags(members: List[Dict[str, Any]]) -> List[str]:
        scores = [m["overall_score"] for m in members]
        if not scores:
            return []
        flags = []
        if max(scores) - min(scores) >= 2.5:
            flags.append("high_variance_between_reviewers")
        if statistics.stdev(scores) >= 1.5:
            flags.append("reviewer_disagreement")
        return flags


def get_ensemble_review_service() -> EnsembleReviewService:
    return EnsembleReviewService()
