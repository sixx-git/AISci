"""
假设评审智能体 (HypothesisReviewAgent)
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.skills.reasoning.hypothesis_novelty_review_skill import HypothesisNoveltyReviewSkill

logger = logging.getLogger(__name__)


class ScoreDetail(BaseModel):
    """评分详情"""
    score: int = Field(..., ge=0, le=10, description="评分 0-10")
    reason: str = Field(..., description="评分理由")
    low_score_reason: Optional[str] = Field(None, description="低分原因（如果评分<6）")


class HypothesisScores(BaseModel):
    """假设评分"""
    scientific_value: ScoreDetail = Field(..., description="科学价值评分")
    novelty: ScoreDetail = Field(..., description="创新性评分")
    testability: ScoreDetail = Field(..., description="可测试性评分")
    data_availability: ScoreDetail = Field(..., description="数据可用性评分")
    cost_risk: ScoreDetail = Field(..., description="成本风险评分")


class HypothesisReview(BaseModel):
    """单条假设评审结果"""
    hypothesis_index: int = Field(..., description="假设索引")
    hypothesis: str = Field(..., description="假设原文")
    scores: HypothesisScores = Field(..., description="各维度评分")
    overall_score: float = Field(..., ge=0, le=10, description="综合得分")
    suggestions: str = Field(..., description="修改建议")
    strengths: List[str] = Field(..., description="优势列表")
    weaknesses: List[str] = Field(..., description="劣势列表")


class HypothesisReviewResult(BaseModel):
    """假设评审结果"""
    reviews: List[HypothesisReview] = Field(..., description="评审列表，按综合得分降序排列")
    summary: str = Field(..., description="总体评价和推荐建议")
    skill_outputs: Dict[str, Any] = Field(default_factory=dict, description="Skill 执行输出")


class HypothesisCandidate(BaseModel):
    """候选假设"""
    hypothesis: str = Field(..., description="假设内容")
    rationale: Optional[str] = Field(None, description="理由")
    novelty: Optional[str] = Field(None, description="创新点")
    testability: Optional[str] = Field(None, description="可测试性")
    required_data: Optional[str] = Field(None, description="所需数据")
    possible_method: Optional[str] = Field(None, description="可能的方法")
    risk: Optional[str] = Field(None, description="风险")


class HypothesisReviewRequest(BaseModel):
    """假设评审请求"""
    hypotheses: List[HypothesisCandidate] = Field(..., description="候选假设列表")


class HypothesisReviewAgent:
    """
    假设评审智能体
    对候选假设从 5 个维度评分，给出修改建议，排序输出
    """
    
    def __init__(self):
        pass
    
    def review(
        self,
        hypotheses: List[HypothesisCandidate],
        retrieved_papers: Optional[List[Dict[str, Any]]] = None,
        literature_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> HypothesisReviewResult:
        """
        评审假设列表

        Args:
            hypotheses: 候选假设列表
            retrieved_papers: 检索到的相关论文（供新颖性审查 Skill 使用）
            literature_facts: 文献事实列表（供新颖性审查 Skill 使用）

        Returns:
            评审结果，按综合得分降序排列
        """
        try:
            logger.info(f"开始评审 {len(hypotheses)} 条假设")
            
            # 格式化假设列表
            formatted_hypotheses = self._format_hypotheses(hypotheses)
            
            # 构建提示
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "hypothesis_review",
                {"hypotheses_list": formatted_hypotheses}
            )
            
            # 定义 schema 示例
            schema_example = {
                "reviews": [
                    {
                        "hypothesis_index": 0,
                        "hypothesis": "假设原文",
                        "scores": {
                            "scientific_value": {"score": 8, "reason": "理由", "low_score_reason": None},
                            "novelty": {"score": 9, "reason": "理由", "low_score_reason": None},
                            "testability": {"score": 7, "reason": "理由", "low_score_reason": None},
                            "data_availability": {"score": 5, "reason": "理由", "low_score_reason": "原因"},
                            "cost_risk": {"score": 6, "reason": "理由", "low_score_reason": "原因"}
                        },
                        "overall_score": 7.0,
                        "suggestions": "建议",
                        "strengths": ["优势1", "优势2"],
                        "weaknesses": ["劣势1", "劣势2"]
                    }
                ],
                "summary": "总体评价"
            }
            
            # 调用 LLM
            result_dict = qwen_structured_chat(prompt=prompt, schema_example=schema_example, prompt_version="hypothesis_review")
            
            # 验证并标准化结果
            result = self._validate_and_normalize_result(result_dict, hypotheses)

            # ── 运行新颖性审查 Skill ──
            result.skill_outputs = self._run_novelty_skills_sync(
                hypotheses, retrieved_papers, literature_facts
            )

            logger.info(f"评审完成，最高综合得分: {result.reviews[0].overall_score if result.reviews else 0}")
            
            return result
            
        except Exception as e:
            logger.error(f"评审假设时出错: {e}", exc_info=True)
            raise
    
    @staticmethod
    def _run_novelty_skills_sync(
        hypotheses: list,
        retrieved_papers: Optional[list] = None,
        literature_facts: Optional[list] = None,
    ) -> Dict[str, Any]:
        import asyncio

        if not retrieved_papers:
            return {"hypothesis_novelty_review": {"success": True, "data": {}, "warnings": ["无检索文献可供新颖性对比"]}}

        async def _run():
            outputs = {}
            for i, hypo in enumerate(hypotheses):
                if isinstance(hypo, dict):
                    h_text = hypo.get("hypothesis", "")
                else:
                    h_text = getattr(hypo, "hypothesis", str(hypo))
                if not h_text:
                    continue

                try:
                    skill = HypothesisNoveltyReviewSkill()
                    skill_result = await skill.run(
                        input_data={
                            "hypothesis": h_text,
                            "retrieved_papers": retrieved_papers or [],
                            "facts": literature_facts or [],
                        },
                        context={"stage": "hypothesis_review", "hypothesis_index": i},
                    )
                    outputs[f"hypothesis_{i}"] = {
                        "success": skill_result.success,
                        "data": skill_result.data,
                        "warnings": skill_result.warnings,
                        "errors": skill_result.errors,
                    }
                except Exception as e:
                    logger.warning(f"NoveltyReviewSkill 失败 (hypothesis {i}): {e}")
                    outputs[f"hypothesis_{i}"] = {"success": False, "error": str(e)}
            return {"hypothesis_novelty_review": outputs}

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"NoveltyReviewSkill 异常: {e}")
            return {}

    def _format_hypotheses(self, hypotheses: List[HypothesisCandidate]) -> str:
        """格式化假设列表"""
        if not hypotheses:
            return "（无候选假设）"
        
        formatted = []
        for idx, hypo in enumerate(hypotheses):
            hypo_text = f"## 假设 {idx}\n"
            hypo_text += f"假设内容: {hypo.hypothesis}\n"
            
            if hypo.rationale:
                hypo_text += f"理由: {hypo.rationale}\n"
            if hypo.novelty:
                hypo_text += f"创新点: {hypo.novelty}\n"
            if hypo.testability:
                hypo_text += f"可测试性: {hypo.testability}\n"
            if hypo.required_data:
                hypo_text += f"所需数据: {hypo.required_data}\n"
            if hypo.possible_method:
                hypo_text += f"可能的方法: {hypo.possible_method}\n"
            if hypo.risk:
                hypo_text += f"风险: {hypo.risk}\n"
            
            formatted.append(hypo_text)
        
        return "\n".join(formatted)
    
    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        original_hypotheses: List[HypothesisCandidate]
    ) -> HypothesisReviewResult:
        """验证并标准化结果"""
        # 确保必要字段存在
        if "reviews" not in result_dict:
            result_dict["reviews"] = []
        
        if "summary" not in result_dict:
            result_dict["summary"] = "无总体评价"
        
        # 验证每条 review
        validated_reviews = []
        for idx, review in enumerate(result_dict["reviews"]):
            # 确保索引正确
            review["hypothesis_index"] = review.get("hypothesis_index", idx)
            
            # 确保 hypothesis 字段存在
            if "hypothesis" not in review or not review["hypothesis"]:
                if idx < len(original_hypotheses):
                    review["hypothesis"] = original_hypotheses[idx].hypothesis
            
            # 确保 scores 字段存在
            if "scores" not in review:
                review["scores"] = self._create_default_scores()
            
            # 验证每个 score
            scores = review["scores"]
            for score_key in ["scientific_value", "novelty", "testability", "data_availability", "cost_risk"]:
                if score_key not in scores:
                    scores[score_key] = {
                        "score": 5,
                        "reason": "评分缺失，默认 5 分",
                        "low_score_reason": None
                    }
                score_data = scores[score_key]
                # 确保 score 在 0-10 范围内
                if not isinstance(score_data.get("score"), int) or score_data["score"] < 0 or score_data["score"] > 10:
                    score_data["score"] = 5
                # 确保 reason 存在
                if "reason" not in score_data or not score_data["reason"]:
                    score_data["reason"] = "评分理由缺失"
            
            # 计算或验证 overall_score
            if "overall_score" not in review or not isinstance(review["overall_score"], (int, float)):
                # 计算平均分
                total_score = sum([
                    scores["scientific_value"]["score"],
                    scores["novelty"]["score"],
                    scores["testability"]["score"],
                    scores["data_availability"]["score"],
                    scores["cost_risk"]["score"]
                ])
                review["overall_score"] = round(total_score / 5.0, 1)
            else:
                review["overall_score"] = round(float(review["overall_score"]), 1)
            
            # 确保其他字段存在
            if "suggestions" not in review or not review["suggestions"]:
                review["suggestions"] = "建议：进一步明确实验方案"
            if "strengths" not in review or not isinstance(review["strengths"], list):
                review["strengths"] = []
            if "weaknesses" not in review or not isinstance(review["weaknesses"], list):
                review["weaknesses"] = []
            
            validated_reviews.append(review)
        
        # 按 overall_score 降序排序
        validated_reviews.sort(key=lambda x: x["overall_score"], reverse=True)
        
        result_dict["reviews"] = validated_reviews
        
        return HypothesisReviewResult(**result_dict)
    
    def _create_default_scores(self) -> Dict[str, Any]:
        """创建默认评分"""
        default_score = {
            "score": 5,
            "reason": "评分缺失，默认 5 分",
            "low_score_reason": None
        }
        
        return {
            "scientific_value": default_score.copy(),
            "novelty": default_score.copy(),
            "testability": default_score.copy(),
            "data_availability": default_score.copy(),
            "cost_risk": default_score.copy()
        }


# 全局单例
_agent_instance: Optional[HypothesisReviewAgent] = None


def get_hypothesis_review_agent() -> HypothesisReviewAgent:
    """获取 HypothesisReviewAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = HypothesisReviewAgent()
    return _agent_instance
