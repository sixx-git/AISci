"""
影响力偏差解释模块 — 基于 LLM 影响力评估结果，生成双向偏差解释。

核心思路：
  1. 提供完整评分标准与实际打分结果给 LLM
  2. LLM 生成两种方向的解释：
     - 提升路径：如果更有影响力，需要在哪些维度改进（基于当前得分的短板）
     - 下降风险：如果影响力变差，可能是因为哪些因素（基于当前得分已暴露的弱点）
  3. 严格区分"基于真实数据"与"基于推断"的内容，确保判断依据属实
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

PROMPT_IMPACT_BIAS_EXPLANATION = """\
You are an academic impact assessment analyst specializing in systematic bias detection. Based on the following paper's metadata and its impact evaluation scores, generate a rigorous bias explanation.

## Scoring Standards (Full marks = 30)

1. Academic Reach (0-10): Citation count considering publication age.
   - 10: >1000 citations / top 1% in field
   - 8: 200-1000 citations / highly cited
   - 6: 50-200 citations / solid recognition
   - 4: 10-50 citations / early traction
   - 2: <10 citations / limited reach
   - Adjust for recency (published <2yr ago gets leniency)

2. Publication Venue Quality (0-8): Venue ranking (CCF-A/B/C equivalent).
   - 8: CCF-A equivalent top venue
   - 5-6: CCF-B equivalent solid venue
   - 3-4: CCF-C equivalent respectable venue
   - 2: Unranked
   - 1-2: Preprint only

3. Author Influence (0-7): Author reputation and institution prestige.
   - 7: Well-established senior researchers from top institutions
   - 5: Mid-career researchers with solid publications
   - 3: Early-career or less established
   - 1: Unknown authors, first publication

4. Research Network Position (0-5): Collaboration diversity and breadth.
   - 5: Large international team with top-tier collaborators
   - 3: Multi-institution collaboration
   - 1: Single author or single institution

## Actual Scoring Result

{impact_result_text}

## Paper Metadata (VERIFIED DATA)

- Title: {title}
- Venue: {host_venue}
- Publication Year: {publication_year}
- Citation Count: {cited_by_count} (from OpenAlex API)
- Open Access: {open_access}
- Authors: {authors_summary}
- Institutions: {institutions_summary}

## Task

You MUST analyze this score from TWO opposing directions: "偏高" (overestimation) and "偏低" (underestimation). For EACH dimension, explain BOTH why the score might be too HIGH and why it might be too LOW, based on the specific numerical score and the metadata.

### Section 1: Current Assessment Summary ("现状诊断")
One paragraph summarizing the score distribution, strengths, and weaknesses. Use SPECIFIC numbers from the scoring result.

### Section 2: Underestimation Bias Analysis ("偏低误差分析")
For EACH dimension, explain why this score might UNDERESTIMATE the paper's actual impact. Consider:
- Academic Reach: Is the citation count artificially low due to preprint stigma, database lag, or field-specific citation norms?
- Venue Quality: Did the scoring system miss the actual publication venue (e.g., OpenAlex shows preprint but paper was accepted at a top conference)?
- Author Influence: Did missing institutional metadata cause conservative scoring? Are the authors more influential than the score suggests?
- Network Position: Is collaboration diversity underestimated due to incomplete affiliation data?

For each dimension, provide:
- "score_may_be_low_because": specific reason the score is conservative
- "evidence": what data supports this claim
- "estimated_true_range": your best estimate of what the score SHOULD be (e.g., "6-8/10" instead of "4/10")

### Section 3: Overestimation Bias Analysis ("偏高误差分析")
For EACH dimension, explain why this score might OVERESTIMATE the paper's actual impact. Consider:
- Academic Reach: Could citations be inflated by self-citation, citation rings, or early hype? Is the citation velocity sustainable?
- Venue Quality: Could the venue's prestige be overrated? Is it a "pay-to-publish" or low-acceptance-barrier venue?
- Author Influence: Could author reputation create a "halo effect" that inflates the score beyond what THIS specific paper deserves?
- Network Position: Could "multi-institutional" collaboration be superficial (guest authors, honorary affiliations)?

For each dimension, provide:
- "score_may_be_high_because": specific reason the score is inflated
- "evidence": what data supports this claim
- "risk_level": "High/Medium/Low" for how likely this overestimation is

### Section 4: Improvement Path ("提升路径") — ANCHORED TO SCORING RUBRIC
For each dimension where the score is NOT at maximum, reference the EXACT scoring rubric thresholds above:

**Academic Reach (0-10)** — reference the citation thresholds:
- If scored 4 (10-50 citations): to reach 6, need 50+ citations; to reach 8, need 200+; to reach 10, need 1000+.
- If scored 6 (50-200 citations): to reach 8, need 200+ citations; to reach 10, need 1000+.
- State: which threshold boundary is the score near? What would push it over?

**Venue Quality (0-8)** — reference the CCF ranking thresholds:
- If scored 2 (Unranked/Preprint): to reach 5-6, need CCF-B acceptance; to reach 8, need CCF-A.
- If scored 5-6 (CCF-B): to reach 8, need CCF-A acceptance.
- State: what specific venue tier is needed, and is it realistic for this paper?

**Author Influence (0-7)** — reference the tier thresholds:
- If scored 3 (Early-career): to reach 5, need mid-career with solid publication record; to reach 7, need senior from top institution.
- If scored 5 (Mid-career): to reach 7, need established senior from top institution.
- State: what specific career milestone or institutional affiliation would raise the score?

**Network Position (0-5)** — reference the collaboration thresholds:
- If scored 1 (Single institution): to reach 3, need multi-institution; to reach 5, need large international team.
- If scored 3 (Multi-institution): to reach 5, need large international team with top-tier collaborators.
- State: what specific collaboration expansion would raise the score?

For each, provide: dimension, current_score, current_rubric_tier (quote the exact rubric description), next_tier (quote the exact rubric description), gap_to_close (what specifically is needed), realistic (boolean).

### Section 5: Decline Risks ("下降风险") — ANCHORED TO SCORING RUBRIC
For each dimension, reference the EXACT scoring rubric thresholds BELOW:

- What would cause the score to DROP to the next lower tier?
- For Academic Reach: citation growth stalling, field moving on from this topic
- For Venue Quality: venue reputation declining (unlikely but possible for new venues)
- For Author Influence: authors leaving the field, institution declining
- For Network Position: team dispersing, no follow-up collaborations
- State: current tier, risk of dropping to which tier, what specific trigger would cause the drop, severity.

### Section 6: Data Reliability Statement ("依据声明")
- verified_claims: claims based on OpenAlex API data
- inferred_claims: claims based on LLM knowledge inference
- missing_data: data gaps that limit assessment accuracy

## Output Format
Return ONLY a JSON object (no markdown, no code fences):
{{
  "current_assessment": "string",
  "underestimation_bias": [
    {{
      "dimension": "Academic Reach / Venue Quality / Author Influence / Network Position",
      "current_score": "X/Y",
      "score_may_be_low_because": "string: specific reason",
      "evidence": "string: supporting evidence",
      "estimated_true_range": "string: e.g., '6-8/10'"
    }}
  ],
  "overestimation_bias": [
    {{
      "dimension": "Academic Reach / Venue Quality / Author Influence / Network Position",
      "current_score": "X/Y",
      "score_may_be_high_because": "string: specific reason",
      "evidence": "string: supporting evidence",
      "risk_level": "High/Medium/Low"
    }}
  ],
  "improvement_path": [
    {{
      "dimension": "Academic Reach / Venue Quality / Author Influence / Network Position",
      "current_score": "X/Y",
      "current_rubric_tier": "string: exact rubric description for this score (e.g., '10-50 citations / early traction')",
      "next_tier": "string: exact rubric description for the next higher score (e.g., '50-200 citations / solid recognition')",
      "gap_to_close": "string: what specific change is needed to reach the next tier",
      "realistic": true/false
    }}
  ],
  "decline_risks": [
    {{
      "dimension": "Academic Reach / Venue Quality / Author Influence / Network Position",
      "current_score": "X/Y",
      "current_rubric_tier": "string: exact rubric description",
      "risk_drop_to_tier": "string: exact rubric description of the next lower tier",
      "trigger": "string: what specific event would cause the drop",
      "severity": "High/Medium/Low"
    }}
  ],
  "data_reliability": {{
    "verified_claims": ["string"],
    "inferred_claims": ["string"],
    "missing_data": ["string"]
  }}
}}"""


def explain_impact_bias(
    impact: dict[str, Any],
    metadata: dict[str, Any],
    llm_client,
    model: str = "deepseek-v4-flash",
    temperature: float = 0.3,
) -> Optional[dict[str, Any]]:
    """调用 LLM 生成影响力评估的偏差解释。

    Args:
        impact: evaluate_impact() 返回的影响力评估结果
        metadata: fetch_work_by_doi/title 返回的元数据
        llm_client: OpenAI 兼容客户端
        model: 模型名称
        temperature: 生成温度

    Returns:
        偏差解释结果字典，或 None。
    """
    prompt = _build_explanation_prompt(impact, metadata)

    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=8000,
        )
        text = resp.choices[0].message.content.strip()

        # 清理 markdown 代码块
        text = text.strip()
        while text.startswith("```"):
            text = text[3:].lstrip()
            if text.startswith("json"):
                text = text[4:].lstrip()
            break
        while text.endswith("```"):
            text = text[:-3].rstrip()
            break
        text = text.strip()

        # 尝试提取 JSON 对象
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]

        result = json.loads(text.strip())
        _validate_explanation(result)
        return result

    except json.JSONDecodeError as e:
        logger.warning("Bias explanation JSON parse failed: %s", e)
        logger.warning("Raw text (repr): %s", repr(text[:500]))
        return None
    except Exception as e:
        logger.error("Bias explanation failed: %s", e)
        return None


def _build_explanation_prompt(impact: dict[str, Any], metadata: dict[str, Any]) -> str:
    """构建偏差解释 prompt。"""
    # 将 impact 结果格式化为可读文本
    lines = []
    lines.append(f"Total Score: {impact.get('total_score', 0)}/30")
    lines.append(f"Impact Level: {impact.get('impact_level', 'Unknown')}")
    lines.append("")

    dim_names = {
        "academic_reach": "学术传播度 (Academic Reach)",
        "venue_quality": "发表平台质量 (Venue Quality)",
        "author_influence": "作者影响力 (Author Influence)",
        "network_position": "研究网络位置 (Network Position)",
    }

    for key, cn_name in dim_names.items():
        entry = impact.get(key, {})
        score = entry.get("score", 0)
        max_score = entry.get("max", 0)
        reason = entry.get("reason", "No reason provided")
        lines.append(f"{cn_name}: {score}/{max_score}")
        lines.append(f"  Reason: {reason}")
        if key == "venue_quality" and "equivalent_ccf" in entry:
            lines.append(f"  CCF Equivalent: {entry['equivalent_ccf']}")
        lines.append("")

    impact_result_text = "\n".join(lines)

    # 作者摘要
    authors = metadata.get("authors", [])
    authors_summary = "; ".join(
        f"{a.get('name', 'Unknown')} ({', '.join(a.get('institutions', []))})"
        for a in authors[:5]
    ) if authors else "Unknown"

    institutions = metadata.get("institutions", [])
    institutions_summary = "; ".join(institutions[:5]) if institutions else "Unknown (arXiv papers often lack institutional metadata)"

    return PROMPT_IMPACT_BIAS_EXPLANATION.format(
        impact_result_text=impact_result_text,
        title=metadata.get("title", "Unknown"),
        host_venue=metadata.get("host_venue", "Unknown / Preprint"),
        publication_year=metadata.get("publication_year", "Unknown"),
        cited_by_count=metadata.get("cited_by_count", 0),
        open_access="Yes" if metadata.get("open_access") else "No",
        authors_summary=authors_summary,
        institutions_summary=institutions_summary,
    )


def _validate_explanation(result: dict[str, Any]) -> None:
    """验证偏差解释结果的结构，补全缺失字段。"""
    if not isinstance(result, dict):
        raise ValueError(f"Expected dict, got {type(result).__name__}")

    # current_assessment: string
    if "current_assessment" not in result or not isinstance(result["current_assessment"], str):
        result["current_assessment"] = ""

    # list fields
    for key in ["underestimation_bias", "overestimation_bias", "improvement_path", "decline_risks"]:
        if key not in result or not isinstance(result[key], list):
            result[key] = []

    # data_reliability: dict
    if "data_reliability" not in result or not isinstance(result["data_reliability"], dict):
        result["data_reliability"] = {
            "verified_claims": [],
            "inferred_claims": [],
            "missing_data": [],
        }
    else:
        dr = result["data_reliability"]
        for key in ["verified_claims", "inferred_claims", "missing_data"]:
            if key not in dr or not isinstance(dr[key], list):
                dr[key] = []


def format_bias_explanation(explanation: dict[str, Any]) -> str:
    """将偏差解释格式化为人类可读的文本报告。"""
    lines = []
    lines.append("=" * 50)
    lines.append("影响力评估偏差解释")
    lines.append("=" * 50)

    # 现状诊断
    lines.append("\n【现状诊断】")
    lines.append(explanation.get("current_assessment", "暂无诊断"))

    # 偏低误差分析
    lines.append("\n【偏低误差分析】得分可能低估了实际影响力：")
    under = explanation.get("underestimation_bias", [])
    if under:
        for item in under:
            dim = item.get("dimension", "Unknown")
            score = item.get("current_score", "?/?")
            reason = item.get("score_may_be_low_because", "")
            evidence = item.get("evidence", "")
            est_range = item.get("estimated_true_range", "")
            lines.append(f"  • {dim} ({score})")
            lines.append(f"    原因: {reason}")
            if evidence:
                lines.append(f"    证据: {evidence}")
            if est_range:
                lines.append(f"    估计真实范围: {est_range}")
    else:
        lines.append("  未发现显著低估")

    # 偏高误差分析
    lines.append("\n【偏高误差分析】得分可能高估了实际影响力：")
    over = explanation.get("overestimation_bias", [])
    if over:
        for item in over:
            dim = item.get("dimension", "Unknown")
            score = item.get("current_score", "?/?")
            reason = item.get("score_may_be_high_because", "")
            evidence = item.get("evidence", "")
            risk = item.get("risk_level", "Medium")
            lines.append(f"  • {dim} ({score}) [风险: {risk}]")
            lines.append(f"    原因: {reason}")
            if evidence:
                lines.append(f"    证据: {evidence}")
    else:
        lines.append("  未发现显著高估")

    # 提升路径
    lines.append("\n【提升路径】如果影响力更高，需要改进：")
    improvements = explanation.get("improvement_path", [])
    if improvements:
        for item in improvements:
            dim = item.get("dimension", "Unknown")
            current = item.get("current_score", "?/?")
            potential = item.get("potential_score", "?/?")
            change = item.get("specific_change", "")
            realistic = "可行" if item.get("realistic") else "不确定"
            lines.append(f"  • {dim}: {current} → {potential} | {change} ({realistic})")
    else:
        lines.append("  暂无具体提升建议")

    # 下降风险
    lines.append("\n【下降风险】影响力可能被高估的因素：")
    risks = explanation.get("decline_risks", [])
    if risks:
        for item in risks:
            dim = item.get("dimension", "Unknown")
            score = item.get("current_score", "?/?")
            desc = item.get("risk_description", "")
            severity = item.get("severity", "Medium")
            lines.append(f"  • [{severity}] {dim} ({score}): {desc}")
    else:
        lines.append("  暂无显著风险")

    # 数据可靠性
    lines.append("\n【依据声明】")
    dr = explanation.get("data_reliability", {})
    verified = dr.get("verified_claims", [])
    inferred = dr.get("inferred_claims", [])
    missing = dr.get("missing_data", [])

    if verified:
        lines.append("  基于真实数据：")
        for c in verified:
            lines.append(f"    ✓ {c}")
    if inferred:
        lines.append("  基于推断：")
        for c in inferred:
            lines.append(f"    ~ {c}")
    if missing:
        lines.append("  缺失数据（影响评估准确性）：")
        for c in missing:
            lines.append(f"    ? {c}")

    lines.append("")
    return "\n".join(lines)
