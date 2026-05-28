"""
假设新颖性审查 Skill
参考能力：AI Scientist reviewer + novelty assessment
——根据已检索文献判断假设是否已有类似研究，
输出 novelty_score / similar_work / risk。
"""
import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)


class HypothesisNoveltyReviewSkill(BaseSkill):
    """假设新颖性审查 Skill

    输入:
      - hypothesis: str                 待审查假设
      - retrieved_papers: List[dict]    检索到的相关论文（含 title/abstract）
      - facts: List[dict]              文献事实列表

    输出 (SkillResult.data):
      - novelty_score: float             0.0-10.0，越低越不新颖
      - similar_work: List[dict]         与假设高度相似的工作
      - novelty_risk: str               low / medium / high
      - assessment: str                 整体评估
      - suggestions: List[str]          改进建议
    """

    name = "HypothesisNoveltyReview"
    description = "根据已检索文献判断假设是否已有类似研究，量化新颖性风险"
    source_reference = "AI Scientist (arxiv:2408.06292) — novelty assessment 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)

        hypothesis = input_data.get("hypothesis", "")
        papers = input_data.get("retrieved_papers", [])
        facts = input_data.get("facts", [])

        if not hypothesis:
            result.add_error("缺少 hypothesis")
            return result

        if not papers:
            result.add_warning("无可用于对比的文献，无法量化新颖性")
            result.data = {
                "novelty_score": 7.0,
                "similar_work": [],
                "novelty_risk": "medium",
                "assessment": "缺少足够文献进行新颖性对比，默认中性评分。",
                "suggestions": ["建议先导入相关领域文献后重新审查"],
            }
            return result

        try:
            papers_text = self._format_papers(papers)
            facts_text = self._format_facts(facts)

            prompt = (
                "你是一位科研假设新颖性审查专家。请根据以下信息判断假设的新颖性风险。\n\n"
                f"## 待审查假设\n{hypothesis}\n\n"
                f"## 已检索参考文献（{len(papers)} 篇）\n{papers_text}\n\n"
                f"## 文献事实\n{facts_text}\n\n"
                "请输出结构化 JSON 评估。similar_work 中仅列出与假设高度相似（重叠度 > 60%）的文献。"
            )

            schema = {
                "novelty_score": 7.0,
                "similar_work": [
                    {
                        "title": "相似论文标题",
                        "similarity": "高度重叠描述",
                        "overlap_ratio": 0.75,
                    }
                ],
                "novelty_risk": "medium",
                "assessment": "整体评估说明",
                "suggestions": ["改进建议1", "改进建议2"],
            }

            llm_result = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema,
                prompt_version="hypothesis_novelty_review",
            )

            result.data = {
                "novelty_score": float(llm_result.get("novelty_score", 7.0)),
                "similar_work": llm_result.get("similar_work", []),
                "novelty_risk": str(llm_result.get("novelty_risk", "medium")),
                "assessment": str(llm_result.get("assessment", "")),
                "suggestions": llm_result.get("suggestions", []),
            }
            result.metadata = {
                "papers_count": len(papers),
                "facts_count": len(facts),
                "reviewer": "qwen",
            }

            risk = str(result.data["novelty_risk"]).lower()
            if risk == "high":
                result.add_warning("新颖性风险 HIGH — 假设与已有工作高度重叠")

            return result

        except Exception as e:
            logger.exception(f"HypothesisNoveltyReviewSkill 异常: {e}")
            result.add_error(f"新颖性审查异常: {e}")
            return result

    @staticmethod
    def _format_papers(papers: List[dict]) -> str:
        lines = []
        for i, p in enumerate(papers, 1):
            lines.append(
                f"[{i}] {p.get('title', 'N/A')}\n"
                f"    Authors: {p.get('authors', 'N/A')}\n"
                f"    Abstract: {p.get('abstract', 'N/A')[:300]}..."
            )
        return "\n".join(lines) if lines else "无可用文献"

    @staticmethod
    def _format_facts(facts: List[dict]) -> str:
        lines = []
        for f in facts[:20]:
            lines.append(
                f"- [{f.get('fact_id', '?')}] {f.get('content', '')[:200]}"
            )
        return "\n".join(lines) if lines else "无可用事实"