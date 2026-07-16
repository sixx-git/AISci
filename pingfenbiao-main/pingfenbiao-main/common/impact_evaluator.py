"""
科学影响力评估模块（增强版）

整合多个技能提升预测质量：
  - PaperFeatureExtractionSkill: 从论文PDF提取结构化特征
  - CitationGraphFeatureSkill: 分析引用网络拓扑
  - EarlyImpactPredictionSkill: 预测论文未来引用趋势
  - ImpactCalibrationSkill: 区分文本质量贡献与已有声誉影响

核心设计原则：
  1. 预测不只是给出分数，还要说明影响判断的因素
  2. 明确区分"文本质量贡献"和"已有声誉影响"
  3. 量化预测的不确定性
  4. 识别可能导致不公平或不稳定评价的因素
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from openai import OpenAI

from .citation_graph import analyze_citation_graph
from .early_impact import predict_early_impact
from .impact_explainer import explain_bias_direction, should_boost
from .metadata_fetcher import fetch_work_by_doi, fetch_work_by_title, _summarize_work
from .paper_feature_extraction import extract_paper_features

logger = logging.getLogger(__name__)


def _get_client(api_key: str):
    key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
    return OpenAI(
        api_key=key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


# ---------------------------------------------------------------------------
# System prompt（增强版，加入新技能维度）
# ---------------------------------------------------------------------------
_IMPACT_SYSTEM_PROMPT = """You are a scientific-impact evaluator.

## Task
Assess the predicted scientific influence of a paper or research report. Your evaluation must go beyond a simple score — you must explain the factors influencing the judgment and identify potential sources of unfair or unstable evaluation.

## Input data (enhanced with multi-skill analysis)
You will receive:
1. **Metadata**: title, authors, journal, publication year, citations, institutions
2. **Citation Graph Features**: network size, citation velocity, field percentile, diversity, influential citers ratio
3. **Early Impact Prediction**: predicted 1/3/5-year citations, high-impact probability, growth trajectory, uncertainty level
4. **Paper Text Features**: structure quality, methodology depth, innovation signals, cross-domain degree, transparency score

## Evaluation Dimensions (30 points total, calibrated)

### D1: Intrinsic Text Quality (0-10 points, content-weighted)
Evaluate the paper's intrinsic quality based on:
- Methodological rigor and experimental design
- Novelty and originality of contributions
- Clarity of writing and logical structure
- Data transparency and reproducibility signals
- Cross-domain impact potential

**Calibration rule**: Text quality should account for 60% of the final influence assessment. A paper with excellent text quality but low current citations may still deserve a high score.

### D2: Reputation & Network Effects (0-10 points, reputation-weighted)
Evaluate external reputation signals:
- Journal/venue prestige and impact factor
- Author track record and h-index
- Institutional reputation
- Current citation count and network position
- Field percentile ranking

**Calibration rule**: Reputation should account for 40% of the final influence assessment. Over-reliance on reputation can create unfair bias against early-career researchers or novel ideas from lesser-known venues.

### D3: Future Impact Potential (0-6 points, prediction-based)
Predict the paper's future influence trajectory:
- Citation growth trajectory (explosive/rapid/steady/moderate/slow)
- High-impact probability assessment
- 1-year / 3-year / 5-year citation projections
- Uncertainty level of predictions
- Alignment with emerging research trends

**Calibration rule**: Consider the uncertainty level. For papers with very high uncertainty (newly published or few citations), be conservative. For mature papers with clear trajectories, weight predictions more heavily.

### D4: Bias & Fairness Assessment (0-4 points, transparency requirement)
Identify and quantify evaluation biases:
- **Venue bias**: Does high venue prestige inflate the score unfairly?
- **Author bias**: Does famous author reputation mask mediocre content?
- **Field bias**: Is the field naturally high-citation or low-citation?
- **Temporal bias**: Does recency or antiquity distort evaluation?
- **Language/region bias**: Are non-English or non-Western papers disadvantaged?
- **Gender/institution bias**: Potential structural inequities

For each bias identified, note:
  - Direction: + (overestimates) or - (underestimates)
  - Magnitude: estimated point impact
  - Mitigation: how the calibration adjusts for this bias

## Output Format
Respond with a JSON object (no markdown code fences) containing exactly these fields:

{
  "d1_text_quality": { "score": int, "max": 10, "rationale": "string" },
  "d2_reputation": { "score": int, "max": 10, "rationale": "string" },
  "d3_future_potential": { "score": int, "max": 6, "rationale": "string" },
  "d4_bias_fairness": { "score": int, "max": 4, "rationale": "string" },
  "calibrated_total": { "score": float, "max": 30, "method": "string" },
  "calibration_details": {
    "raw_reputation_component": float,
    "raw_quality_component": float,
    "reputation_adjustment": float,
    "quality_adjustment": float,
    "bias_mitigation_summary": "string"
  },
  "key_factors": [
    { "factor": "string", "impact": "positive|negative|neutral", "magnitude": "high|medium|low", "description": "string" }
  ],
  "risk_factors": [
    { "risk": "string", "probability": "high|medium|low", "mitigation": "string" }
  ],
  "prediction_confidence": "high|medium|low",
  "uncertainty_sources": ["string"],
  "overall_assessment": "string (3-5 sentences)"
}

## Calibration Method
calibrated_total = (d1_text_quality.score * 0.6 + d2_reputation.score * 0.4) * (d3_future_potential.score / 6) * adjustment + d4_bias_fairness.score

Where adjustment accounts for:
- If reputation >> quality: downward adjustment (prevents halo effect)
- If quality >> reputation: upward adjustment (recognizes undervalued work)
- If uncertainty is high: conservative adjustment

The final calibrated_total must be between 0 and 30.
"""


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def evaluate_impact(
    title: str = "",
    doi: str = "",
    pdf_text: str = "",
    api_key: str = "",
    model: str = "qwen-max",
    max_chars: int = 8000,
    temperature: float = 0.3,
) -> dict[str, Any] | None:
    """综合评估科学影响力（增强版）。

    整合多技能分析：
    1. 元数据获取（OpenAlex）
    2. 引用网络分析（CitationGraphFeatureSkill）
    3. 早期影响力预测（EarlyImpactPredictionSkill）
    4. 论文文本特征提取（PaperFeatureExtractionSkill）
    5. LLM综合评估（含校准和偏差分析）

    Args:
        title: 论文标题
        doi: DOI
        pdf_text: PDF提取的文本（用于文本特征提取）
        api_key: DashScope API Key
        model: 模型名称
        max_chars: 用户提示最大字符数
        temperature: 生成温度

    Returns:
        评估结果字典，包含分数、校准详情、偏差分析、预测信息。
    """
    # ── 1. 获取元数据 ──
    meta = None
    if doi:
        raw = fetch_work_by_doi(doi)
        if raw:
            meta = _summarize_work(raw)
    if not meta and title:
        raw = fetch_work_by_title(title)
        if raw:
            meta = _summarize_work(raw)

    if not meta:
        logger.warning("无法获取论文元数据（title=%s, doi=%s）", title, doi)
        meta = {}

    # 统一字段名（兼容新旧数据）
    meta.setdefault("title", title or "Unknown")
    meta.setdefault("cited_by_count", 0)
    meta.setdefault("publication_year", None)
    meta.setdefault("journal", meta.get("host_venue", ""))
    meta.setdefault("authors", [])
    meta.setdefault("institutions", [])
    meta.setdefault("doi", doi or "")
    meta.setdefault("openalex_id", "")

    # ── 2. 引用网络分析 ──
    citation_graph = None
    work_id = meta.get("openalex_id", "")
    if not work_id and doi:
        work_id = doi

    if work_id:
        try:
            citation_graph = analyze_citation_graph(work_id)
            logger.info("引用网络分析完成: cited_by=%d", citation_graph.get("network_size", {}).get("cited_by_count", 0) if citation_graph else 0)
        except Exception as e:
            logger.warning("引用网络分析失败: %s", e)

    # ── 3. 早期影响力预测 ──
    early_impact = None
    if meta.get("cited_by_count", 0) > 0 or (citation_graph and citation_graph.get("network_size", {}).get("cited_by_count", 0) > 0):
        try:
            cited_count = citation_graph.get("network_size", {}).get("cited_by_count", meta.get("cited_by_count", 0)) if citation_graph else meta.get("cited_by_count", 0)
            pub_year = meta.get("publication_year")
            velocity = citation_graph.get("citation_velocity", 0) if citation_graph else 0
            percentile = citation_graph.get("field_percentile", 50) if citation_graph else 50

            if pub_year:
                early_impact = predict_early_impact(
                    cited_count=cited_count,
                    publication_year=pub_year,
                    citation_velocity=velocity,
                    field_percentile=percentile,
                    venue_tier=meta.get("venue_tier", ""),
                )
                logger.info("早期影响力预测完成: 1年=%s, 高影响概率=%s",
                           early_impact.get("predictions", {}).get("1_year", {}).get("predicted_citations", "N/A"),
                           early_impact.get("high_impact_probability", {}).get("probability", "N/A"))
        except Exception as e:
            logger.warning("早期影响力预测失败: %s", e)

    # ── 4. 论文文本特征提取 ──
    paper_features = None
    if pdf_text:
        try:
            paper_features = extract_paper_features(pdf_text)
            logger.info("论文特征提取完成: 质量分=%d", paper_features.get("overall_quality_score", 0))
        except Exception as e:
            logger.warning("论文特征提取失败: %s", e)

    # ── 5. 构建增强版提示 ──
    user_prompt = _build_enhanced_prompt(meta, citation_graph, early_impact, paper_features, max_chars)

    # ── 6. LLM 评估 ──
    client = _get_client(api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _IMPACT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
    except Exception as e:
        logger.error("LLM 评估失败: %s", e)
        return None

    # ── 7. 后处理 ──
    # 确保数值在合理范围内
    for key in ["d1_text_quality", "d2_reputation", "d3_future_potential", "d4_bias_fairness"]:
        if key in result:
            result[key]["score"] = max(0, min(result[key].get("max", 10), result[key].get("score", 0)))

    # 计算校准总分（如果LLM没算好）
    calibrated = result.get("calibrated_total", {})
    if not calibrated.get("score"):
        d1 = result.get("d1_text_quality", {}).get("score", 0)
        d2 = result.get("d2_reputation", {}).get("score", 0)
        d3 = result.get("d3_future_potential", {}).get("score", 0)
        d4 = result.get("d4_bias_fairness", {}).get("score", 0)
        # 校准公式：质量60% + 声誉40%，再乘以未来潜力因子，加上偏差分
        base = d1 * 0.6 + d2 * 0.4
        future_factor = d3 / 6.0 if d3 > 0 else 0.5
        # 如果声誉显著高于质量，下调；如果质量显著高于声誉，上调
        rep_quality_diff = d2 - d1
        adjustment = 1.0
        if rep_quality_diff > 3:
            adjustment = 0.9  # 声誉光环效应，下调
        elif rep_quality_diff < -3:
            adjustment = 1.1  # 被低估的好工作，上调
        calibrated_score = round(base * future_factor * adjustment + d4, 1)
        result["calibrated_total"] = {
            "score": min(30, max(0, calibrated_score)),
            "max": 30,
            "method": "(quality*0.6 + reputation*0.4) * future_factor * adjustment + bias_score"
        }

    # ── 8. 附加分析数据 ──
    result["_analysis_data"] = {
        "citation_graph": citation_graph,
        "early_impact_prediction": early_impact,
        "paper_features": paper_features,
        "metadata": {
            "title": meta.get("title", ""),
            "authors": meta.get("authors", []),
            "journal": meta.get("journal", ""),
            "publication_year": meta.get("publication_year"),
            "cited_by_count": meta.get("cited_by_count", 0),
            "doi": meta.get("doi", ""),
        },
    }

    # ── 9. 偏差方向分析（增强版）──
    if meta:
        direction = explain_bias_direction(meta)
        result["bias_direction"] = direction
        result["should_boost"] = should_boost(meta)

    return result


def _build_enhanced_prompt(
    meta: dict[str, Any],
    citation_graph: dict[str, Any] | None,
    early_impact: dict[str, Any] | None,
    paper_features: dict[str, Any] | None,
    max_chars: int,
) -> str:
    """构建增强版评估提示。"""
    lines = ["请评估以下论文的科学影响力。", ""]

    # 基本信息
    lines.append("=== 基本信息 ===")
    lines.append(f"标题: {meta.get('title', 'N/A')}")
    lines.append(f"作者: {', '.join(meta.get('authors', [])[:5])}")
    lines.append(f"机构: {', '.join(meta.get('institutions', [])[:3])}")
    lines.append(f"期刊/会议: {meta.get('journal', 'N/A')}")
    lines.append(f"发表年份: {meta.get('publication_year', 'N/A')}")
    lines.append(f"DOI: {meta.get('doi', 'N/A')}")
    lines.append(f"当前引用数: {meta.get('cited_by_count', 0)}")
    lines.append("")

    # 引用网络分析
    if citation_graph:
        lines.append("=== 引用网络分析 ===")
        ns = citation_graph.get("network_size", {})
        lines.append(f"被引次数: {ns.get('cited_by_count', 0)}")
        lines.append(f"引用论文数: {ns.get('references_count', 0)}")
        lines.append(f"引用速度: {citation_graph.get('citation_velocity', 0)} 次/年")
        lines.append(f"领域百分位: {citation_graph.get('field_percentile', 50)}%")
        lines.append(f"引用集中度: {citation_graph.get('concentration_ratio', 0)}")
        lines.append(f"引用多样性: {citation_graph.get('diversity_score', 0)}")
        lines.append(f"高影响力引用比例: {citation_graph.get('influential_ratio', 0)}")
        lines.append(f"网络连通性: {citation_graph.get('connectivity', 0)}")
        lines.append(f"平均引用延迟: {citation_graph.get('avg_citation_delay_years', 0)} 年")
        lines.append("")

    # 早期影响力预测
    if early_impact:
        lines.append("=== 早期影响力预测 ===")
        cs = early_impact.get("current_state", {})
        lines.append(f"当前状态: {cs.get('cited_count', 0)}次引用, 年龄{cs.get('age_years', 0)}年, 阶段{cs.get('life_stage', 'unknown')}")

        preds = early_impact.get("predictions", {})
        for year in ["1_year", "3_year", "5_year"]:
            p = preds.get(year, {})
            lines.append(f"{year.replace('_', '')}预测: {p.get('predicted_citations', 'N/A')}次 ({p.get('method', '')})")
        lines.append(f"饱和估计: {preds.get('saturation_estimate', 'N/A')}次")
        lines.append(f"增长轨迹: {preds.get('growth_trajectory', 'unknown')}")

        hip = early_impact.get("high_impact_probability", {})
        lines.append(f"高影响概率: {hip.get('probability', 0)} ({hip.get('interpretation', 'unknown')})")

        unc = early_impact.get("uncertainty", {})
        lines.append(f"预测不确定性: {unc.get('overall_level', 'unknown')}")
        lines.append("")

    # 论文文本特征
    if paper_features:
        lines.append("=== 论文文本特征 ===")
        score = paper_features.get("overall_quality_score", 0)
        lines.append(f"综合文本质量分: {score}/100")

        struct = paper_features.get("structure", {})
        lines.append(f"文本长度: {struct.get('word_count', 0)}词, {struct.get('char_count', 0)}字符")
        lines.append(f"估计图表数: {struct.get('estimated_figures', 0)}图 + {struct.get('estimated_tables', 0)}表")
        lines.append(f"估计参考文献: {struct.get('estimated_references', 0)}篇")
        lines.append(f"章节完整性: Abstract={struct.get('has_abstract', False)}, Methods={struct.get('has_methods', False)}, Results={struct.get('has_results', False)}")

        content = paper_features.get("content", {})
        abs_info = content.get("abstract", {})
        lines.append(f"摘要质量: {abs_info.get('quality', 'unknown')} ({abs_info.get('length_words', 0)}词)")
        method_info = content.get("methodology", {})
        lines.append(f"方法论描述: {method_info.get('description_depth', 'unknown')} ({method_info.get('section_length_words', 0)}词)")

        innov = paper_features.get("innovation", {})
        lines.append(f"创新密度: {innov.get('innovation_density', 0)} (关键词{innov.get('innovation_keyword_count', 0)}个)")
        lines.append(f"新颖性声明: {innov.get('novelty_claims', 0)}处")
        lines.append(f"跨领域程度: {innov.get('cross_domain_degree', 'unknown')}")
        lines.append(f"贡献项数: {innov.get('contribution_items', 0)}")

        quality = paper_features.get("quality_signals", {})
        lines.append(f"透明度评分: {quality.get('transparency_score', 0)}/5")
        lines.append("")

    prompt = "\n".join(lines)

    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n[内容截断...]"

    return prompt
