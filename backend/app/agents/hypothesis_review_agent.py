"""
假设评审智能体 (HypothesisReviewAgent)
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)


HYPOTHESIS_REVIEW_PROMPT_TEMPLATE = """你是一位专业的科研评审专家，擅长从多个维度评估科学假设。

## 任务要求
对输入的候选假设列表进行评审，每条假设从以下 5 个维度评分（0-10 分）：

1. scientific_value (科学价值)：该假设对推动领域发展的重要性
2. novelty (创新性)：该假设与现有研究的区别和创新点
3. testability (可测试性)：该假设通过实验/分析验证的可行性
4. data_availability (数据可用性)：验证该假设所需数据的可获得性
5. cost_risk (成本风险)：验证该假设的成本、时间和风险程度

## 重要原则
- 评分理由必须具体，结合假设内容进行分析
- 指出低分原因（如果某项评分<6分）
- 给出修改建议
- 按综合得分（加权或平均分）从高到低排序

## 评分标准
- 9-10 分：优秀，非常突出
- 7-8 分：良好，有较好表现
- 5-6 分：一般，有明显不足
- 0-4 分：较差，存在严重问题

## 输入信息
候选假设列表：
{hypotheses_list}

## 输出格式要求
请严格按照以下 JSON 格式输出，不要添加额外解释或 markdown 标记：
{{
  "reviews": [
    {{
      "hypothesis_index": 0,
      "hypothesis": "假设原文",
      "scores": {{
        "scientific_value": {{
          "score": 8,
          "reason": "该假设针对领域核心问题，具有重要理论意义",
          "low_score_reason": null
        }},
        "novelty": {{
          "score": 9,
          "reason": "提出了全新的研究视角，未在现有文献中发现",
          "low_score_reason": null
        }},
        "testability": {{
          "score": 7,
          "reason": "可以通过对照实验验证，但需要较大样本量",
          "low_score_reason": null
        }},
        "data_availability": {{
          "score": 5,
          "reason": "需要特定数据集，获取难度中等",
          "low_score_reason": "数据获取成本较高，可能需要合作"
        }},
        "cost_risk": {{
          "score": 6,
          "reason": "需要专业设备和较长时间，风险中等",
          "low_score_reason": "实验周期可能超预期"
        }}
      }},
      "overall_score": 7.0,
      "suggestions": "建议1：先进行小规模预实验验证可行性；建议2：寻找公开数据集或合作获取数据；建议3：考虑简化实验设计降低风险",
      "strengths": ["创新性强", "科学价值高"],
      "weaknesses": ["数据获取困难", "成本风险较高"]
    }}
  ],
  "summary": "对所有假设的总体评价和推荐建议"
}}
"""


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
        hypotheses: List[HypothesisCandidate]
    ) -> HypothesisReviewResult:
        """
        评审假设列表
        
        Args:
            hypotheses: 候选假设列表
            
        Returns:
            评审结果，按综合得分降序排列
        """
        try:
            logger.info(f"开始评审 {len(hypotheses)} 条假设")
            
            # 格式化假设列表
            formatted_hypotheses = self._format_hypotheses(hypotheses)
            
            # 构建提示
            prompt = HYPOTHESIS_REVIEW_PROMPT_TEMPLATE.format(
                hypotheses_list=formatted_hypotheses
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
            result_dict = qwen_structured_chat(prompt=prompt, schema_example=schema_example)
            
            # 验证并标准化结果
            result = self._validate_and_normalize_result(result_dict, hypotheses)
            
            logger.info(f"评审完成，最高综合得分: {result.reviews[0].overall_score if result.reviews else 0}")
            
            return result
            
        except Exception as e:
            logger.error(f"评审假设时出错: {e}", exc_info=True)
            raise
    
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
