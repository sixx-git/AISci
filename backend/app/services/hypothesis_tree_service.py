"""假设树 — 多分支评分、剪枝、选择最优路径（借 AI Scientist v2 思想，轻量 BFTS）"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EVIDENCE_SCORE = {"high": 1.0, "medium": 0.65, "low": 0.35}


class HypothesisTreeService:
    """对候选假设构建分支树，按证据+对齐+可测性评分，剪枝保留最优。"""

    def build_and_prune(
        self,
        hypotheses: List[Dict[str, Any]],
        alignments: Optional[List[Dict[str, Any]]] = None,
        literature_facts: Optional[List[Dict[str, Any]]] = None,
        max_branches: int = 3,
    ) -> Dict[str, Any]:
        alignments = alignments or []
        facts = literature_facts or []
        fact_ids = {f.get("fact_id") for f in facts if f.get("fact_id")}

        branches: List[Dict[str, Any]] = []
        for i, h in enumerate(hypotheses):
            if h.get("off_topic"):
                continue
            align = alignments[i] if i < len(alignments) else {}
            branch = self._score_branch(i, h, align, fact_ids)
            branches.append(branch)

        if not branches:
            branches = [
                self._score_branch(i, h, alignments[i] if i < len(alignments) else {}, fact_ids)
                for i, h in enumerate(hypotheses[:max_branches])
            ]

        branches.sort(key=lambda b: b["composite_score"], reverse=True)
        kept = branches[:max_branches]
        pruned = branches[max_branches:]
        winner = kept[0] if kept else None

        quality_trend = [
            {"round": 0, "branch_id": b["branch_id"], "score": b["composite_score"], "label": b["label"][:40]}
            for b in sorted(branches, key=lambda x: x["composite_score"], reverse=True)
        ]

        selected_index = winner["index"] if winner else 0
        selected_hypothesis = hypotheses[selected_index] if selected_index < len(hypotheses) else hypotheses[0]

        return {
            "tree_id": str(uuid.uuid4()),
            "branches": kept,
            "pruned_branches": [{"branch_id": p["branch_id"], "index": p["index"], "composite_score": p["composite_score"]} for p in pruned],
            "selected_branch_id": winner["branch_id"] if winner else None,
            "selected_hypothesis_index": selected_index,
            "selected_hypothesis": selected_hypothesis,
            "quality_trend": quality_trend,
            "iteration_summary": self._build_iteration_summary(kept, pruned, winner),
            "evidence_coverage": self._evidence_coverage(selected_hypothesis, fact_ids),
            "pilot_feedback_applied": False,
        }

    def apply_pilot_feedback(
        self,
        tree: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]],
        hypotheses: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """P2-7: 将沙箱 pilot 实测分融合进假设树分支评分。"""
        if not tree or not small_validation:
            return tree

        sb = small_validation.get("sandbox_execution") or {}
        actual = (small_validation.get("results") or {}).get("actual_results") or {}
        has_pilot = bool(sb) or bool(actual.get("modeling_result"))
        if not has_pilot:
            return tree

        success = bool(sb.get("success")) if sb else bool(actual.get("modeling_result"))
        metrics = sb.get("metrics") if sb else {}
        if not metrics and actual.get("summary_statistics"):
            metrics = {"summary": actual.get("summary_statistics")}

        pilot_score = 8.5 if success else 3.5
        if sb.get("return_code") not in (None, 0) and not success:
            pilot_score = 2.5

        selected_id = tree.get("selected_branch_id")
        branches = list(tree.get("branches") or [])
        for branch in branches:
            is_selected = branch.get("branch_id") == selected_id
            if is_selected:
                branch["pilot_score"] = pilot_score
                branch["pilot_metrics"] = metrics
                branch["pilot_success"] = success
                branch["composite_score"] = round(
                    float(branch.get("composite_score", 5)) * 0.65 + pilot_score * 0.35,
                    2,
                )
                branch["status"] = "pilot_validated" if success else "pilot_failed"
            else:
                branch["pilot_score"] = None
                branch["pilot_status"] = "not_executed"
                branch["composite_score"] = round(
                    float(branch.get("composite_score", 5)) * 0.92,
                    2,
                )

        branches.sort(key=lambda b: b.get("composite_score", 0), reverse=True)
        tree["branches"] = branches
        if branches:
            tree["selected_branch_id"] = branches[0].get("branch_id")
            tree["selected_hypothesis_index"] = branches[0].get("index", 0)
            if hypotheses and 0 <= tree["selected_hypothesis_index"] < len(hypotheses):
                tree["selected_hypothesis"] = hypotheses[tree["selected_hypothesis_index"]]

        summary = tree.get("iteration_summary") or ""
        tree["iteration_summary"] = (
            f"{summary} 已融合 pilot 实测（success={success}, pilot_score={pilot_score}）。"
        ).strip()
        tree["pilot_feedback_applied"] = True
        tree["quality_trend"] = list(tree.get("quality_trend") or []) + [
            {"round": 1, "branch_id": selected_id, "score": pilot_score, "label": "pilot_sandbox"}
        ]
        return tree

    def _score_branch(
        self,
        index: int,
        hypo: Dict[str, Any],
        alignment: Dict[str, Any],
        fact_ids: set,
    ) -> Dict[str, Any]:
        fact_refs = hypo.get("supporting_fact_ids") or []
        valid_facts = [fid for fid in fact_refs if fid in fact_ids]
        evidence_level = hypo.get("evidence_level", "medium")
        evidence_score = EVIDENCE_SCORE.get(str(evidence_level).lower(), 0.5)
        evidence_score *= min(1.0, 0.5 + 0.15 * len(valid_facts))

        align_score = float(alignment.get("alignment_score") or hypo.get("alignment_score") or 70) / 100.0
        if alignment.get("off_topic") or hypo.get("off_topic"):
            align_score *= 0.3

        testability = 0.7
        if hypo.get("validation_target") and hypo.get("expected_measurable_effect"):
            testability = 0.9
        elif hypo.get("testability"):
            testability = 0.75

        data_refs = len(hypo.get("dataset_field_refs") or []) + len(hypo.get("data_evidence_ids") or [])
        data_score = min(1.0, 0.4 + 0.1 * data_refs)

        composite = round(
            0.35 * evidence_score + 0.30 * align_score + 0.20 * testability + 0.15 * data_score,
            4,
        ) * 10

        label = hypo.get("hypothesis") or f"branch_{index}"
        return {
            "branch_id": f"branch_{index}_{uuid.uuid4().hex[:6]}",
            "index": index,
            "label": label,
            "hypothesis": label,
            "evidence_level": evidence_level,
            "supporting_fact_count": len(valid_facts),
            "alignment_score": round(align_score * 100, 1),
            "scores": {
                "evidence": round(evidence_score * 10, 2),
                "alignment": round(align_score * 10, 2),
                "testability": round(testability * 10, 2),
                "data": round(data_score * 10, 2),
            },
            "composite_score": round(composite, 2),
            "status": "candidate",
        }

    @staticmethod
    def _evidence_coverage(hypo: Dict[str, Any], fact_ids: set) -> Dict[str, Any]:
        refs = hypo.get("supporting_fact_ids") or []
        valid = [r for r in refs if r in fact_ids]
        return {
            "total_fact_refs": len(refs),
            "verified_fact_refs": len(valid),
            "coverage_ratio": round(len(valid) / max(len(refs), 1), 2),
            "has_data_evidence": bool(hypo.get("dataset_field_refs") or hypo.get("data_evidence_ids")),
        }

    @staticmethod
    def _build_iteration_summary(
        kept: List[Dict[str, Any]],
        pruned: List[Dict[str, Any]],
        winner: Optional[Dict[str, Any]],
    ) -> str:
        if not winner:
            return "无有效假设分支。"
        parts = [
            f"共评估 {len(kept) + len(pruned)} 条分支，保留 Top-{len(kept)}。",
            f"选中分支 composite={winner['composite_score']}，证据 {winner['supporting_fact_count']} 条已验证 fact。",
        ]
        if pruned:
            parts.append(f"剪枝 {len(pruned)} 条低分分支（最高剪枝分 {pruned[0]['composite_score']:.1f}）。")
        return " ".join(parts)


def get_hypothesis_tree_service() -> HypothesisTreeService:
    return HypothesisTreeService()
