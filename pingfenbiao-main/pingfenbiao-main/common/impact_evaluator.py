"""
LLM 影响力评估模块 — 基于论文元数据进行科学影响力评估（满分 30 分）。

评估维度：
  1. 学术传播度 (0-10): 引用数、发表年限、引用增速
  2. 发表平台质量 (0-8): 期刊/会议等级（CCF 等效锚定）
  3. 作者影响力 (0-7): 作者学术声誉、机构实力
  4. 研究网络位置 (0-5): 合作者网络广度、跨机构合作
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

PROMPT_IMPACT_EVALUATION = """\
You are an academic impact evaluator. Evaluate the following paper's scientific influence based on its metadata.

## Step 1: Data Verification (CRITICAL — do this BEFORE scoring)

The metadata below comes from OpenAlex API and may be INCOMPLETE or OUTDATED. You MUST use your own knowledge to verify and supplement it:

- **Venue check**: OpenAlex reports: "{host_venue}" (type: {work_type}). If this says "preprint" but you know this paper was actually accepted/published at a peer-reviewed venue (e.g., ICML, NeurIPS, Nature), use the ACTUAL venue.
- **Author check**: OpenAlex reports institutions as: "{institutions_summary}". If institution info is missing but you recognize the authors, fill in the correct affiliations.
- **Citation check**: OpenAlex reports {cited_by_count} citations. Consider whether this count seems consistent with the paper's known impact. If suspiciously low for a well-known paper, note this discrepancy.
- **Open access check**: OpenAlex reports: {open_access}.

Output your corrections (if any) in the "corrections" field below.

## Paper Metadata (OpenAlex Raw Data)
- Title: {title}
- Venue: {host_venue}
- Publication Year: {publication_year}
- Publication Date: {publication_date}
- Type: {work_type}
- Citation Count: {cited_by_count}
- References Count: {referenced_works_count}
- Open Access: {open_access}
- Authors: {authors_summary}
- Institutions: {institutions_summary}
- Fields: {concepts}

## Step 2: Scoring (Total 30 points)

Use "CCF Computer Science ranking equivalence" as your judgment anchor across ALL disciplines:
- CCF-A equivalent top venue (NeurIPS, Nature, ICML, NEJM, Science): Full marks for venue dimension
- CCF-B equivalent solid venue: ~70% of full marks
- CCF-C equivalent or respectable venue: ~40% of full marks
- Unranked or minor venue: ~20% of full marks
- Preprint only (no peer review): ~25% of full marks

### Dimension 1: Academic Reach (0-10 points)
Evaluate citation impact considering publication age.
- {publication_year} paper with {cited_by_count} citations.
- If published < 2 years ago: low citations is normal — weight recency potential higher.
- If published > 5 years ago with < 10 citations: likely limited reach.
- Rapid citation growth (high velocity) is a strong positive signal.

### Dimension 2: Publication Venue Quality (0-8 points)
Use your VERIFIED venue (from Step 1), NOT the raw OpenAlex data.
State what CCF equivalent level this venue is, then score:
- CCF-A equivalent → 8 points
- CCF-B equivalent → 5-6 points
- CCF-C equivalent → 3-4 points
- Unranked → 2 points
- Preprint only → 1-2 points

### Dimension 3: Author Influence (0-7 points)
Use your VERIFIED author/institution data (from Step 1).
Authors and institutions:
{authors_detail}

Evaluate:
- Are authors well-established in their field? (prior publications, h-index)
- Are they from reputable/top institutions?
- CCF-A level senior author → 7; CCF-B level → 5; early career/unknown → 3; student → 1

### Dimension 4: Research Network Position (0-5 points)
- Number of collaborators and institutional diversity
- Cross-institution or cross-country collaboration
- Any highly-cited co-authors among the team
- Large diverse international team → 5; multi-institution → 3; single author → 1

## Calibration Examples
- "Nature, 2023, 800 citations, MIT + Oxford authors" → total ~28/30
- "CCF-B conference, 2022, 45 citations, mid-tier university" → total ~16/30
- "Unknown workshop, 2024, 3 citations, single student author" → total ~6/30
- "Top medical journal, 2021, 1200 citations, multi-national team" → total ~27/30
- "ICML 2024 Oral preprint on OpenAlex but actually accepted → venue should be scored as CCF-A (8/8), NOT as preprint (2/8)"

## Output Format
Return ONLY a JSON object (no markdown, no code fences):
{{
  "corrections": [
    {{"field": "venue", "raw": "preprint", "corrected": "ICML 2024 Oral", "reason": "..."}}
  ],
  "academic_reach": {{"score": X, "max": 10, "reason": "..."}},
  "venue_quality": {{"score": X, "max": 8, "equivalent_ccf": "A/B/C/Unranked/Preprint", "reason": "...", "based_on": "raw_or_corrected"}},
  "author_influence": {{"score": X, "max": 7, "reason": "...", "based_on": "raw_or_corrected"}},
  "network_position": {{"score": X, "max": 5, "reason": "..."}},
  "total_score": X,
  "impact_level": "High|Medium|Low|Very Low"
}}
"""


def evaluate_impact(
    metadata: dict[str, Any],
    llm_client,
    model: str = "deepseek-v4-flash",
    temperature: float = 0.3,
) -> Optional[dict[str, Any]]:
    """调用 LLM 评估论文影响力。

    Args:
        metadata: fetch_work_by_doi/fetch_work_by_title 返回的元数据字典
        llm_client: OpenAI 兼容客户端实例（Config.get_client()）
        model: 模型名称
        temperature: 生成温度

    Returns:
        影响力评估结果字典，或 None（调用失败时）。
    """
    prompt = _build_prompt(metadata)

    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2500,
        )
        text = resp.choices[0].message.content.strip()

        # 清理 markdown 代码块
        text = text.strip()
        # 去掉首尾的 ``` 代码围栏
        while text.startswith("```"):
            text = text[3:].lstrip()
            if text.startswith("json"):
                text = text[4:].lstrip()
            break
        while text.endswith("```"):
            text = text[:-3].rstrip()
            break
        text = text.strip()

        # 尝试提取 JSON 对象（处理前后有非 JSON 文本的情况）
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]

        result = json.loads(text.strip())
        _validate_result(result)
        return result

    except json.JSONDecodeError as e:
        logger.warning("Impact evaluation JSON parse failed: %s", e)
        logger.warning("Raw text (first 500 chars): %s", repr(text[:500]))
        return None
    except Exception as e:
        logger.error("Impact evaluation failed: %s", e)
        return None


def _build_prompt(metadata: dict[str, Any]) -> str:
    """构建 prompt，填充元数据。"""
    authors = metadata.get("authors", [])
    authors_summary = "; ".join(
        f"{a.get('name', 'Unknown')} ({', '.join(a.get('institutions', []))})"
        for a in authors[:5]
    )
    if not authors_summary:
        authors_summary = "Unknown authors"

    authors_detail = ""
    for i, a in enumerate(authors[:5]):
        insts = a.get("institutions", [])
        inst_str = ", ".join(insts) if insts else "Unknown institution"
        authors_detail += f"{i+1}. {a.get('name', 'Unknown')} — {inst_str}\n"

    institutions = metadata.get("institutions", [])
    institutions_summary = "; ".join(institutions[:5]) if institutions else "Unknown"

    concepts = metadata.get("concepts", [])
    concepts_str = ", ".join(concepts[:6]) if concepts else "General"

    return PROMPT_IMPACT_EVALUATION.format(
        title=metadata.get("title", "Unknown"),
        host_venue=metadata.get("host_venue", "Unknown"),
        publication_year=metadata.get("publication_year", "Unknown"),
        publication_date=metadata.get("publication_date", "Unknown"),
        work_type=metadata.get("type", "Unknown"),
        cited_by_count=metadata.get("cited_by_count", 0),
        referenced_works_count=metadata.get("referenced_works_count", 0),
        open_access="Yes" if metadata.get("open_access") else "No",
        authors_summary=authors_summary,
        authors_detail=authors_detail or "No detailed author information available.",
        institutions_summary=institutions_summary,
        concepts=concepts_str,
    )


def _validate_result(result: dict[str, Any]) -> None:
    """验证 LLM 返回的结构，修正异常值。"""
    # 处理 corrections 字段
    if "corrections" not in result or not isinstance(result["corrections"], list):
        result["corrections"] = []

    dim_limits = {
        "academic_reach": 10,
        "venue_quality": 8,
        "author_influence": 7,
        "network_position": 5,
    }

    for dim, max_val in dim_limits.items():
        if dim not in result:
            result[dim] = {"score": 0, "max": max_val, "reason": "Not evaluated"}
        else:
            entry = result[dim]
            if not isinstance(entry, dict):
                result[dim] = {"score": 0, "max": max_val, "reason": "Invalid format"}
            else:
                score = int(entry.get("score", 0))
                score = max(0, min(score, max_val))  # clamp
                entry["score"] = score
                entry["max"] = max_val
                # 保留 based_on 字段（标记评分依据是原始数据还是校验后数据）
                if "based_on" not in entry:
                    entry["based_on"] = "raw"

    total = sum(result[dim]["score"] for dim in dim_limits)
    result["total_score"] = min(total, 30)  # 总分上限 30

    if "impact_level" not in result:
        if total >= 22:
            result["impact_level"] = "High"
        elif total >= 14:
            result["impact_level"] = "Medium"
        elif total >= 7:
            result["impact_level"] = "Low"
        else:
            result["impact_level"] = "Very Low"
