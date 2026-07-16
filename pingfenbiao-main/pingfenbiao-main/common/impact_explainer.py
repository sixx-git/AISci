"""
偏差解释模块（增强版）— BiasExplanationSkill

解释影响力预测中的偏差来源，增加更多维度：
  - 领域热度偏差
  - 期刊/会议声誉偏差
  - 作者声望偏差
  - 发表时间偏差
  - 机构偏差
  - 语言/地域偏差
  - 性别偏差（基于作者姓名推断，仅供参考）

不只给出一个分数，还要说明：
  1. 影响判断的因素
  2. 这些因素是否可能带来不公平或不稳定的评价
  3. 如何校准这些偏差
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


def _get_client(api_key: str):
    key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
    return OpenAI(
        api_key=key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


# ---------------------------------------------------------------------------
# 增强版 System prompt
# ---------------------------------------------------------------------------
_EXPLAINER_SYSTEM_PROMPT = """You are a scientific-impact bias analyst.

## Task
Analyze the prediction output for potential biases and unfairness. You must identify:
1. Which factors influenced the prediction
2. Whether these factors could lead to unfair or unstable evaluations
3. How the calibration mitigates these biases
4. What residual risks remain

## Input
You will receive:
- Original prediction scores
- Calibrated scores with adjustments
- Citation graph features
- Early impact predictions
- Paper text features
- Bias direction analysis

## Bias Dimensions to Analyze

### 1. Venue Bias (期刊/会议声誉偏差)
- High-prestige venues may inflate scores through halo effect
- Lesser-known venues may undervalue genuinely good work
- Preprints may be unfairly penalized

### 2. Author Bias (作者声望偏差)
- Famous authors may receive inflated scores
- Early-career researchers may be undervalued
- Famous institutions may create implicit bias

### 3. Field Bias (领域热度偏差)
- Hot fields (AI, biomedicine) naturally attract more citations
- Niche fields may have lower citation ceilings
- Interdisciplinary work may be undercounted

### 4. Temporal Bias (发表时间偏差)
- Very new papers haven't had time to accumulate citations
- Very old papers may be undervalued due to citation decay
- Seasonal effects in publication

### 5. Language/Region Bias (语言/地域偏差)
- Non-English papers may be under-cited
- Non-Western institutions may face implicit bias
- Regional citation practices vary

### 6. Gender Bias (性别偏差)
- Gender imbalances in STEM may create structural bias
- Note: gender inference from names is imperfect and should be flagged as uncertain

### 7. Methodological Bias (方法论偏差)
- Quantitative fields may be overvalued vs qualitative
- Experimental vs theoretical work may be treated differently
- Replication studies may be undervalued

## Output Format
Respond with a JSON object containing:

{
  "bias_analysis": {
    "venue_bias": {
      "detected": boolean,
      "direction": "positive|negative|neutral",
      "estimated_impact": float,
      "description": "string",
      "mitigation": "string"
    },
    "author_bias": { ... },
    "field_bias": { ... },
    "temporal_bias": { ... },
    "language_region_bias": { ... },
    "gender_bias": { ... },
    "methodological_bias": { ... }
  },
  "fairness_assessment": {
    "overall_fairness_score": float,
    "max": 10,
    "confidence": "high|medium|low",
    "key_concerns": ["string"],
    "recommendations": ["string"]
  },
  "stability_analysis": {
    "prediction_stability": "high|medium|low",
    "time_sensitivity": "high|medium|low",
    "sample_size_concerns": "string",
    "robustness_notes": "string"
  },
  "calibration_effectiveness": {
    "reputation_adjustment_effectiveness": "high|medium|low",
    "quality_adjustment_effectiveness": "high|medium|low",
    "remaining_bias_risk": "high|medium|low",
    "suggested_further_calibration": ["string"]
  },
  "transparency_report": {
    "factors_influencing_judgment": [
      { "factor": "string", "weight": "high|medium|low", "source": "string", "potential_bias": "string" }
    ],
    "uncertainty_quantification": {
      "score_uncertainty_range": "string",
      "prediction_interval": "string",
      "confidence_level": "string"
    }
  }
}
"""


def explain_prediction_bias(
    impact_result: dict[str, Any],
    api_key: str = "",
    model: str = "qwen-plus",
    max_chars: int = 6000,
    temperature: float = 0.2,
) -> dict[str, Any] | None:
    """对影响力预测结果进行深度偏差分析（增强版）。

    Args:
        impact_result: evaluate_impact() 的完整输出
        api_key: DashScope API Key
        model: 模型名称
        max_chars: 用户提示最大字符数
        temperature: 生成温度

    Returns:
        偏差分析结果字典。
    """
    # 提取关键数据
    analysis_data = impact_result.get("_analysis_data", {})
    metadata = analysis_data.get("metadata", {})
    citation_graph = analysis_data.get("citation_graph", {})
    early_impact = analysis_data.get("early_impact_prediction", {})
    paper_features = analysis_data.get("paper_features", {})

    # 构建提示
    lines = ["请对以下影响力预测结果进行偏差分析。", ""]

    # 预测结果摘要
    lines.append("=== 预测结果摘要 ===")
    for key in ["d1_text_quality", "d2_reputation", "d3_future_potential", "d4_bias_fairness"]:
        if key in impact_result:
            d = impact_result[key]
            lines.append(f"{key}: {d.get('score', 0)}/{d.get('max', 10)} - {d.get('rationale', 'N/A')[:100]}")

    if "calibrated_total" in impact_result:
        ct = impact_result["calibrated_total"]
        lines.append(f"校准总分: {ct.get('score', 0)}/{ct.get('max', 30)}")
        lines.append(f"校准方法: {ct.get('method', 'N/A')}")

    if "calibration_details" in impact_result:
        cd = impact_result["calibration_details"]
        lines.append(f"原始声誉分量: {cd.get('raw_reputation_component', 'N/A')}")
        lines.append(f"原始质量分量: {cd.get('raw_quality_component', 'N/A')}")
        lines.append(f"声誉调整: {cd.get('reputation_adjustment', 'N/A')}")
        lines.append(f"质量调整: {cd.get('quality_adjustment', 'N/A')}")

    lines.append("")

    # 关键影响因素
    if "key_factors" in impact_result:
        lines.append("=== 关键影响因素 ===")
        for f in impact_result["key_factors"][:5]:
            lines.append(f"- {f.get('factor', 'N/A')}: {f.get('impact', 'N/A')} ({f.get('magnitude', 'N/A')}) - {f.get('description', 'N/A')[:80]}")
        lines.append("")

    # 风险因素
    if "risk_factors" in impact_result:
        lines.append("=== 风险因素 ===")
        for r in impact_result["risk_factors"][:5]:
            lines.append(f"- {r.get('risk', 'N/A')}: 概率{r.get('probability', 'N/A')} - {r.get('mitigation', 'N/A')[:80]}")
        lines.append("")

    # 引用网络特征
    if citation_graph:
        lines.append("=== 引用网络特征 ===")
        lines.append(f"被引次数: {citation_graph.get('network_size', {}).get('cited_by_count', 0)}")
        lines.append(f"引用速度: {citation_graph.get('citation_velocity', 0)} 次/年")
        lines.append(f"领域百分位: {citation_graph.get('field_percentile', 50)}%")
        lines.append(f"引用多样性: {citation_graph.get('diversity_score', 0)}")
        lines.append("")

    # 早期预测
    if early_impact:
        lines.append("=== 早期影响力预测 ===")
        lines.append(f"生命周期阶段: {early_impact.get('current_state', {}).get('life_stage', 'unknown')}")
        lines.append(f"预测不确定性: {early_impact.get('uncertainty', {}).get('overall_level', 'unknown')}")
        lines.append(f"置信度: {early_impact.get('confidence_level', 'unknown')}")
        lines.append("")

    # 元数据
    lines.append("=== 论文元数据 ===")
    lines.append(f"标题: {metadata.get('title', 'N/A')}")
    lines.append(f"作者: {', '.join(metadata.get('authors', [])[:5])}")
    lines.append(f"期刊: {metadata.get('journal', 'N/A')}")
    lines.append(f"发表年份: {metadata.get('publication_year', 'N/A')}")
    lines.append(f"引用数: {metadata.get('cited_by_count', 0)}")
    lines.append("")

    # 文本特征
    if paper_features:
        lines.append("=== 文本特征 ===")
        lines.append(f"综合质量分: {paper_features.get('overall_quality_score', 0)}/100")
        innov = paper_features.get("innovation", {})
        lines.append(f"创新密度: {innov.get('innovation_density', 0)}")
        lines.append(f"跨领域程度: {innov.get('cross_domain_degree', 'unknown')}")
        lines.append("")

    user_prompt = "\n".join(lines)
    if len(user_prompt) > max_chars:
        user_prompt = user_prompt[:max_chars] + "\n[内容截断...]"

    # LLM 分析
    client = _get_client(api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXPLAINER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
    except Exception as e:
        logger.error("偏差解释 LLM 调用失败: %s", e)
        return None

    return result


# ---------------------------------------------------------------------------
# 原有辅助函数（保持兼容）
# ---------------------------------------------------------------------------

HIGH_PRESTIGE_KEYWORDS = [
    "nature", "science", "cell", "ieee", "acm", "springer", "elsevier",
    "neurips", "icml", "iclr", "cvpr", "acl", "emnlp", "aaai", "ijcai",
    "物理评论快报", "自然", "科学",
]


def explain_bias_direction(meta: dict) -> str:
    """判断整体偏差方向（+ 高估 / - 低估 / ~ 中性）。"""
    score = 0
    reasons = []

    journal = (meta.get("journal") or "").lower()
    if any(k in journal for k in HIGH_PRESTIGE_KEYWORDS):
        score += 1
        reasons.append("高声誉期刊")

    cited = meta.get("cited_by_count", 0) or 0
    if cited > 1000:
        score += 1
        reasons.append("高引用数")
    elif cited < 10:
        score -= 1
        reasons.append("低引用数")

    year = meta.get("publication_year")
    if year:
        age = 2025 - year
        if age < 2:
            score -= 1
            reasons.append("新近发表")
        elif age > 10:
            score -= 0.5
            reasons.append("发表时间较长")

    authors = meta.get("authors", []) or []
    if len(authors) > 10:
        score += 0.5
        reasons.append("大团队合作")

    if score > 1:
        return f"+{score}（{'、'.join(reasons)} → 可能高估）"
    elif score < -1:
        return f"{score}（{'、'.join(reasons)} → 可能低估）"
    return f"~{score}（{'、'.join(reasons)} → 偏差较小）"


def should_boost(meta: dict) -> bool:
    """判断是否应提升评分（存在明显低估信号）。"""
    cited = meta.get("cited_by_count", 0) or 0
    year = meta.get("publication_year")
    journal = (meta.get("journal") or "").lower()

    is_new = year is not None and (2025 - year) <= 2
    is_low_cited = cited < 10
    is_lesser_known_venue = not any(k in journal for k in HIGH_PRESTIGE_KEYWORDS)

    return is_new and is_low_cited and is_lesser_known_venue
