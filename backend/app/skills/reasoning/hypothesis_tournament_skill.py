"""
假设锦标赛 Skill
参考能力：AI Scientist tournament selection
——对多个候选假设进行 pairwise 比较与淘汰，选出最优假设。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class HypothesisTournamentSkill(BaseSkill):
    """假设锦标赛 Skill

    输入:
      - hypotheses: List[dict]          候选假设（含 hypothesis / rationale 等）
      - research_question: str
      - facts: List[dict]
      - retrieved_papers: List[dict]

    输出 (SkillResult.data):
      - ranked_hypotheses: List[dict]   按得分降序
      - winner_index: int
      - winner_hypothesis: str
      - tournament_scores: List[float]
      - pairwise_results: List[dict]
      - selection_rationale: str
    """

    name = "HypothesisTournament"
    description = "对多个候选假设进行锦标赛式 pairwise 评审并选出最优"
    source_reference = "AI Scientist (arxiv:2408.06292) — tournament hypothesis selection"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypotheses = self._normalize_hypotheses(input_data.get("hypotheses") or [])
        research_question = (input_data.get("research_question") or "").strip()
        facts = input_data.get("facts") or []
        papers = input_data.get("retrieved_papers") or []

        if len(hypotheses) < 2:
            if len(hypotheses) == 1:
                result.data = {
                    "ranked_hypotheses": hypotheses,
                    "winner_index": 0,
                    "winner_hypothesis": hypotheses[0].get("hypothesis", ""),
                    "tournament_scores": [hypotheses[0].get("tournament_score", 7.0)],
                    "pairwise_results": [],
                    "selection_rationale": "仅 1 个候选假设，跳过锦标赛",
                }
                return result
            result.add_error("至少需要 2 个候选假设")
            return result

        try:
            scores = [0.0] * len(hypotheses)
            pairwise: List[dict] = []

            for i in range(len(hypotheses)):
                for j in range(i + 1, len(hypotheses)):
                    verdict = await self._compare_pair(
                        hypotheses[i], hypotheses[j], i, j,
                        research_question, facts, papers,
                    )
                    pairwise.append(verdict)
                    winner = verdict.get("winner_index")
                    margin = float(verdict.get("margin", 0.5))
                    if winner == i:
                        scores[i] += 1.0 + margin
                        scores[j] += margin * 0.3
                    elif winner == j:
                        scores[j] += 1.0 + margin
                        scores[i] += margin * 0.3
                    else:
                        scores[i] += 0.5
                        scores[j] += 0.5

            ranked_indices = sorted(range(len(hypotheses)), key=lambda k: scores[k], reverse=True)
            ranked = []
            for rank, idx in enumerate(ranked_indices, 1):
                item = dict(hypotheses[idx])
                item["tournament_score"] = round(scores[idx], 3)
                item["tournament_rank"] = rank
                ranked.append(item)

            winner_idx = ranked_indices[0]
            winner_text = hypotheses[winner_idx].get("hypothesis", "")

            rationale_prompt = (
                f"研究问题: {research_question}\n"
                f"胜出假设: {winner_text}\n"
                f"锦标赛得分: {scores[winner_idx]:.2f}\n"
                "请用 1-2 句话说明为何该假设胜出。"
            )
            rationale_res = qwen_structured_chat(
                prompt=rationale_prompt,
                schema_example={"selection_rationale": "胜出理由"},
                prompt_version="hypothesis_tournament_rationale",
            )

            result.data = {
                "ranked_hypotheses": ranked,
                "winner_index": winner_idx,
                "winner_hypothesis": winner_text,
                "tournament_scores": [round(s, 3) for s in scores],
                "pairwise_results": pairwise,
                "selection_rationale": str(rationale_res.get("selection_rationale", "")),
            }
            return result

        except Exception as e:
            logger.exception("HypothesisTournamentSkill 异常: %s", e)
            result.add_error(f"假设锦标赛异常: {e}")
            return result

    @staticmethod
    def _normalize_hypotheses(raw: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for i, h in enumerate(raw):
            if isinstance(h, dict):
                text = h.get("hypothesis") or h.get("text") or ""
                out.append({**h, "hypothesis": text, "_index": i})
            else:
                out.append({"hypothesis": str(h), "_index": i})
        return [h for h in out if (h.get("hypothesis") or "").strip()]

    async def _compare_pair(
        self,
        a: dict,
        b: dict,
        idx_a: int,
        idx_b: int,
        research_question: str,
        facts: List[dict],
        papers: List[dict],
    ) -> dict:
        facts_preview = "\n".join(
            f"- {f.get('content', '')[:120]}" for f in facts[:5]
        )
        papers_preview = "\n".join(
            f"- {p.get('title', '')[:100]}" for p in papers[:5]
        )
        prompt = (
            "你是科研假设评审专家。请比较两个候选假设，选出更优者。\n\n"
            f"## 研究问题\n{research_question}\n\n"
            f"## 假设 A (index={idx_a})\n{a.get('hypothesis', '')}\n"
            f"理由: {a.get('rationale', '—')}\n\n"
            f"## 假设 B (index={idx_b})\n{b.get('hypothesis', '')}\n"
            f"理由: {b.get('rationale', '—')}\n\n"
            f"## 文献事实摘要\n{facts_preview or '—'}\n\n"
            f"## 相关论文\n{papers_preview or '—'}\n\n"
            "评估维度: 新颖性、可验证性、与证据一致性、可行性。"
        )
        schema = {
            "winner_index": idx_a,
            "margin": 0.6,
            "reason": "A 在可验证性上更优",
            "scores": {"A": 8.0, "B": 6.5},
        }
        llm = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            prompt_version="hypothesis_tournament_pairwise",
        )
        winner = int(llm.get("winner_index", idx_a))
        if winner not in (idx_a, idx_b):
            winner = idx_a if float(llm.get("scores", {}).get("A", 0)) >= float(llm.get("scores", {}).get("B", 0)) else idx_b
        return {
            "pair": [idx_a, idx_b],
            "winner_index": winner,
            "margin": float(llm.get("margin", 0.5)),
            "reason": str(llm.get("reason", "")),
            "scores": llm.get("scores", {}),
        }
