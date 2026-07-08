"""红蓝对抗（正方/反方）轻量包装 — 基于现有 Ensemble 评审，不侵入假设生成与小样验证。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.prompt_loader import get_prompt_loader
from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)

VALID_MODES = ("single_group", "multi_group", "off")

PRO_RESEARCH_AGENTS = [
    "文献事实归纳",
    "假设生成与演绎",
    "证据链绑定 (supporting_fact_ids)",
    "问题对齐与可验证性标注",
]


class ProConAdversarialService:
    """
    将现有对抗审查包装为红蓝对抗：
    - 正方（Pro）：多智能体研究组 — 映射 hypothesis_generation 输出
    - 反方（Con）：轻量单智能体 — 基于文献事实轮流质疑
    - multi_group：多假设并行，组间互为攻防
    """

    def enhance_review(
        self,
        review_result: Dict[str, Any],
        *,
        hypotheses: List[Dict[str, Any]],
        literature_facts: List[Dict[str, Any]],
        research_question: str = "",
        mode: str = "single_group",
        max_con_rounds: int = 2,
        enable_evolution: bool = True,
    ) -> Dict[str, Any]:
        if mode == "off" or not hypotheses:
            return review_result

        mode = mode if mode in VALID_MODES else "single_group"
        primary_idx = review_result.get("primary_index")
        if primary_idx is None:
            ensemble = (review_result.get("skill_outputs") or {}).get("ensemble_review") or {}
            primary_idx = ensemble.get("target_hypothesis_index", 0)
        try:
            primary_idx = int(primary_idx)
        except (TypeError, ValueError):
            primary_idx = 0
        primary_idx = min(max(0, primary_idx), len(hypotheses) - 1)

        skill_outputs = dict(review_result.get("skill_outputs") or {})
        pro_con: Dict[str, Any] = {
            "mode": mode,
            "pro_side": self._build_pro_side(hypotheses, literature_facts),
            "con_side": {},
            "cross_group_attacks": [],
            "evolution": {},
        }

        if mode == "multi_group" and len(hypotheses) >= 2:
            cross = self._run_multi_group(hypotheses, literature_facts, research_question)
            pro_con["cross_group_attacks"] = cross
            pro_con["con_side"] = {"type": "multi_group_cross_challenge", "rounds": cross}
            survival = self._survival_scores(cross, len(hypotheses))
            pro_con["group_survival_scores"] = survival
            best_idx = max(range(len(survival)), key=lambda i: survival[i])
            if best_idx != primary_idx:
                pro_con["primary_index_override"] = {
                    "from": primary_idx,
                    "to": best_idx,
                    "reason": "多研究组红蓝对抗后生存分最高",
                }
                primary_idx = best_idx
                review_result["primary_index"] = best_idx
        else:
            target = hypotheses[primary_idx]
            con_rounds = self._run_single_group_con(
                target,
                literature_facts,
                research_question,
                max_rounds=max(1, min(max_con_rounds, 4)),
            )
            pro_con["con_side"] = {
                "type": "single_agent_rotating",
                "target_hypothesis_index": primary_idx,
                "rounds": con_rounds,
            }
            if enable_evolution and con_rounds:
                evolution = self._synthesize_evolution(
                    target, con_rounds, literature_facts, research_question
                )
                pro_con["evolution"] = evolution

        self._merge_into_ensemble(skill_outputs, pro_con, primary_idx)
        skill_outputs["pro_con_adversarial"] = pro_con
        review_result["skill_outputs"] = skill_outputs
        review_result["adversarial_mode"] = mode
        return review_result

    @staticmethod
    def _build_pro_side(
        hypotheses: List[Dict[str, Any]],
        literature_facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        fact_map = {
            str(f.get("fact_id") or f.get("id") or ""): f
            for f in literature_facts
            if isinstance(f, dict)
        }
        groups = []
        for i, h in enumerate(hypotheses):
            if not isinstance(h, dict):
                continue
            refs = h.get("supporting_fact_ids") or []
            anchors = []
            for fid in refs[:8]:
                fact = fact_map.get(str(fid)) or {}
                anchors.append({
                    "fact_id": fid,
                    "summary": (fact.get("statement") or fact.get("content") or fact.get("text") or "")[:200],
                })
            groups.append({
                "group_index": i,
                "hypothesis": h.get("hypothesis", ""),
                "rationale": h.get("rationale", ""),
                "evidence_level": h.get("evidence_level", ""),
                "literature_anchors": anchors,
                "validation_target": h.get("validation_target", ""),
            })
        return {
            "role": "正方（多智能体研究组）",
            "agents": PRO_RESEARCH_AGENTS,
            "research_groups": groups,
        }

    def _run_single_group_con(
        self,
        hypothesis: Dict[str, Any],
        facts: List[Dict[str, Any]],
        research_question: str,
        max_rounds: int,
    ) -> List[Dict[str, Any]]:
        rounds: List[Dict[str, Any]] = []
        prior: List[Dict[str, Any]] = []
        for rnd in range(1, max_rounds + 1):
            try:
                payload = self._con_challenge_round(
                    hypothesis, facts, research_question, prior, round_num=rnd
                )
                rounds.append({"round": rnd, **payload})
                prior.extend(payload.get("challenges") or [])
            except Exception as exc:
                logger.warning(f"反方质疑第 {rnd} 轮失败: {exc}")
                rounds.append({"round": rnd, "error": str(exc), "challenges": []})
                break
        return rounds

    def _run_multi_group(
        self,
        hypotheses: List[Dict[str, Any]],
        facts: List[Dict[str, Any]],
        research_question: str,
    ) -> List[Dict[str, Any]]:
        attacks: List[Dict[str, Any]] = []
        for i, defender in enumerate(hypotheses):
            if not isinstance(defender, dict):
                continue
            for j, attacker_group in enumerate(hypotheses):
                if i == j or not isinstance(attacker_group, dict):
                    continue
                attacker_label = f"研究组 {j}"
                try:
                    payload = self._con_challenge_round(
                        defender,
                        facts,
                        research_question,
                        prior=[],
                        round_num=1,
                        attacker_context=f"你代表{attacker_label}，从竞争研究视角攻击对方假设的薄弱点。",
                    )
                    attacks.append({
                        "defender_index": i,
                        "attacker_index": j,
                        "attacker_label": attacker_label,
                        **payload,
                    })
                except Exception as exc:
                    logger.warning(f"组间攻防 {j}→{i} 失败: {exc}")
                    attacks.append({
                        "defender_index": i,
                        "attacker_index": j,
                        "error": str(exc),
                        "challenges": [],
                    })
        return attacks

    def _con_challenge_round(
        self,
        hypothesis: Dict[str, Any],
        facts: List[Dict[str, Any]],
        research_question: str,
        prior: List[Dict[str, Any]],
        round_num: int,
        attacker_context: str = "",
    ) -> Dict[str, Any]:
        hypothesis_block = self._format_hypothesis(hypothesis)
        facts_block = self._format_facts(facts)
        prior_block = ""
        if prior:
            lines = []
            for c in prior[:6]:
                if isinstance(c, dict):
                    lines.append(f"- [{c.get('attack_type', '?')}] {c.get('statement', '')}")
            prior_block = "已提出质疑（请勿重复，可深化或补充新角度）：\n" + "\n".join(lines)

        prompt_loader = get_prompt_loader()
        prompt = prompt_loader.render_template(
            "pro_con_con_challenge",
            {
                "research_question": research_question or "（未指定）",
                "hypothesis_block": hypothesis_block,
                "facts_block": facts_block,
                "prior_challenges_block": prior_block or "（首轮质疑，无历史）",
            },
        )
        if attacker_context:
            prompt = attacker_context + "\n\n" + prompt

        schema = {
            "round_summary": "摘要",
            "challenges": [{
                "target_aspect": "方面",
                "attack_type": "evidence_gap",
                "severity": "medium",
                "statement": "质疑",
                "counter_evidence_fact_ids": ["fact_1"],
                "suggested_fix": "修订建议",
            }],
            "acknowledged_strengths": ["优势"],
            "overall_threat_level": "medium",
        }
        result = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            prompt_version="pro_con_con_challenge",
        )
        if not isinstance(result, dict):
            return {"round_summary": "", "challenges": [], "overall_threat_level": "low"}
        result["round"] = round_num
        result["challenges"] = self._validate_challenges(result.get("challenges") or [], facts)
        return result

    def _synthesize_evolution(
        self,
        hypothesis: Dict[str, Any],
        con_rounds: List[Dict[str, Any]],
        facts: List[Dict[str, Any]],
        research_question: str,
    ) -> Dict[str, Any]:
        all_challenges: List[Dict[str, Any]] = []
        for r in con_rounds:
            all_challenges.extend(r.get("challenges") or [])

        if not all_challenges:
            return {"status": "no_challenges", "revision_points": []}

        challenge_lines = "\n".join(
            f"- [{c.get('severity')}] {c.get('statement')} (fix: {c.get('suggested_fix', '')})"
            for c in all_challenges[:8]
            if isinstance(c, dict)
        )
        prompt_loader = get_prompt_loader()
        prompt = prompt_loader.render_template(
            "pro_con_evolution",
            {
                "research_question": research_question or "（未指定）",
                "hypothesis": hypothesis.get("hypothesis", ""),
                "challenges_block": challenge_lines or "（无有效质疑）",
            },
        )
        schema = {
            "evolved_rationale": "整合反方质疑后的理论依据",
            "revision_points": ["修订要点1"],
            "hypothesis_patch": "",
            "remaining_risks": ["残留风险"],
        }
        try:
            evo = qwen_structured_chat(prompt=prompt, schema_example=schema, prompt_version="pro_con_evolution")
            if isinstance(evo, dict):
                evo["status"] = "completed"
                evo["con_rounds_used"] = len(con_rounds)
                return evo
        except Exception as exc:
            logger.warning(f"假设进化合成失败: {exc}")
        return {
            "status": "fallback",
            "revision_points": [c.get("suggested_fix", "") for c in all_challenges[:5] if isinstance(c, dict)],
        }

    @staticmethod
    def _merge_into_ensemble(
        skill_outputs: Dict[str, Any],
        pro_con: Dict[str, Any],
        primary_idx: int,
    ) -> None:
        ensemble = dict(skill_outputs.get("ensemble_review") or {})
        con_weaknesses: List[str] = []

        for rnd in (pro_con.get("con_side") or {}).get("rounds") or []:
            if not isinstance(rnd, dict):
                continue
            for c in rnd.get("challenges") or []:
                if isinstance(c, dict) and c.get("statement"):
                    con_weaknesses.append(f"[反方] {c['statement']}")

        for atk in pro_con.get("cross_group_attacks") or []:
            if not isinstance(atk, dict) or atk.get("defender_index") != primary_idx:
                continue
            for c in atk.get("challenges") or []:
                if isinstance(c, dict) and c.get("statement"):
                    label = atk.get("attacker_label") or "竞争组"
                    con_weaknesses.append(f"[{label}] {c['statement']}")

        evolution = pro_con.get("evolution") or {}
        revisions = list(evolution.get("revision_points") or [])

        existing_w = list(ensemble.get("weaknesses") or [])
        merged_w = existing_w + [w for w in con_weaknesses if w not in existing_w]
        ensemble["weaknesses"] = merged_w[:10]

        existing_r = list(ensemble.get("revision_suggestions") or [])
        merged_r = existing_r + [r for r in revisions if r and r not in existing_r]
        ensemble["revision_suggestions"] = merged_r[:8]

        members = list(ensemble.get("ensemble_reviews") or [])
        threat = "medium"
        con_side = pro_con.get("con_side") or {}
        rounds = con_side.get("rounds") or []
        if rounds and isinstance(rounds[-1], dict):
            threat = rounds[-1].get("overall_threat_level") or threat
        threat_score = {"high": 4.5, "medium": 6.0, "low": 7.5}.get(str(threat).lower(), 6.0)
        members.append({
            "reviewer_id": "con_challenger",
            "type": "pro_con_adversarial",
            "weight": 0.10,
            "overall_score": threat_score,
            "role": "反方质疑智能体",
        })
        ensemble["ensemble_reviews"] = members
        ensemble["pro_con_adversarial"] = True
        ensemble["target_hypothesis_index"] = primary_idx
        skill_outputs["ensemble_review"] = ensemble

    @staticmethod
    def _survival_scores(cross_attacks: List[Dict[str, Any]], n: int) -> List[float]:
        scores = [10.0] * n
        severity_penalty = {"high": 2.0, "medium": 1.0, "low": 0.4}
        for atk in cross_attacks:
            if not isinstance(atk, dict):
                continue
            idx = atk.get("defender_index")
            if idx is None or not (0 <= int(idx) < n):
                continue
            idx = int(idx)
            for c in atk.get("challenges") or []:
                if isinstance(c, dict):
                    sev = str(c.get("severity") or "medium").lower()
                    scores[idx] -= severity_penalty.get(sev, 1.0)
        return [round(max(0.0, s), 2) for s in scores]

    @staticmethod
    def _format_hypothesis(h: Dict[str, Any]) -> str:
        parts = [f"假设: {h.get('hypothesis', '')}"]
        if h.get("rationale"):
            parts.append(f"依据: {h['rationale']}")
        if h.get("supporting_fact_ids"):
            parts.append(f"支持 fact_ids: {', '.join(str(x) for x in h['supporting_fact_ids'][:8])}")
        if h.get("risk"):
            parts.append(f"已知风险: {h['risk']}")
        return "\n".join(parts)

    @staticmethod
    def _format_facts(facts: List[Dict[str, Any]], limit: int = 40) -> str:
        lines = []
        for f in facts[:limit]:
            if not isinstance(f, dict):
                continue
            fid = f.get("fact_id") or f.get("id") or "?"
            text = f.get("statement") or f.get("content") or f.get("text") or ""
            lines.append(f"- {fid}: {str(text)[:300]}")
        return "\n".join(lines) if lines else "（无可用文献事实）"

    @staticmethod
    def _validate_challenges(
        challenges: List[Any],
        facts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        valid_ids = {
            str(f.get("fact_id") or f.get("id") or "")
            for f in facts
            if isinstance(f, dict)
        }
        out: List[Dict[str, Any]] = []
        for c in challenges:
            if not isinstance(c, dict):
                continue
            refs = [str(x) for x in (c.get("counter_evidence_fact_ids") or []) if str(x) in valid_ids]
            c = dict(c)
            c["counter_evidence_fact_ids"] = refs
            out.append(c)
        return out


def get_pro_con_adversarial_service() -> ProConAdversarialService:
    return ProConAdversarialService()
