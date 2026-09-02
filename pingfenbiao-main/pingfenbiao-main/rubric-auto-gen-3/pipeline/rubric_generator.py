"""
科学调研报告评分表生成器 — 核心模块。

专为科学调研综述 (Scientific Literature Review) 设计的评分表生成器。

与通用版本 (v5) 的关键区别：
  - IA 维度侧重概念定义、技术分类、方法描述、局限性识别
  - SR 维度是核心（62%权重），Critical 占比 25%，聚焦深度推理分析
  - Synth 维度以 Standard 为主，但核心结构项可为 Mandatory
  - 使用 LLM 过滤领域通用术语，替代硬编码白名单，实现跨领域泛用性
  - SR 维度弱动词检查更严格，Synth 维度跳过弱动词检查

流程（3阶段 + 去重）：
  Stage 1: 轻量知识提取 + 概念泛化
    1a. 解析 Query 子问题
    1b. 从每篇源文档提取关键知识点
    1c. 概念泛化：将论文特有术语转换为领域通用概念
  Stage 2: 质量驱动生成
    使用科学调研专用的 Prompt 生成三个维度的评分项
  Stage 3: 轻量校准 + LLM 去重 + OCR 操作化
    3a. 规则检查，发现问题直接删除（维度特异性校准）
    3b. LLM 审核去重
    3c. SR Critical 后备提升
    3d. OCR 可观测性操作化（judgment_mode / required_elements / LLM rewrite）
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.rubric_observability import (
    enrich_item_observability,
    extract_elements_from_question,
    has_explain_or_define,
    is_naked_explain_define,
    item_passes_observability,
)

from .source_parser import SourceDocument
from .llm_utils import call_llm_json, call_llm
from .rubric_utils import (
    build_rubric_key,
    infer_competency_category,
    normalize_importance,
    role_from_importance,
    weight_from_importance,
    normalize_question_text,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  固定维度参数（科学调研专用）
# ═══════════════════════════════════════════════════════════════════════════

DIMENSION_CONFIG = {
    "information_acquisition": {
        "weight_pct": 0.23,
        "item_range": (12, 16),
        "name": "Information Acquisition",
        "role_dist": {"critical": 0.15, "mandatory": 0.50, "standard": 0.35},
    },
    "scientific_reasoning": {
        "weight_pct": 0.62,
        "item_range": (28, 38),
        "name": "Scientific Reasoning",
        "role_dist": {"critical": 0.25, "mandatory": 0.50, "standard": 0.25},
    },
    "report_synthesis": {
        "weight_pct": 0.15,
        "item_range": (10, 14),
        "name": "Report Synthesis",
        "role_dist": {"critical": 0.0, "mandatory": 0.0, "standard": 1.0},
    },
}

# 源文档截断字符数
SOURCE_TEXT_MAX_CHARS = 15000

# LLM 生成参数
GENERATION_TEMPERATURE = 0.3
GENERATION_MAX_TOKENS = 32768


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1a — Query 子问题解析
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_SUBQUESTIONS = """\
You are an expert at decomposing complex research queries into verifiable sub-questions.

**Research Query**:
---
{query}
---

**Task**: Decompose this query into distinct, verifiable sub-questions.
Each sub-question should be a concrete requirement that a scientific literature review must address.

**Rules**:
1. Each sub-question must be specific and objectively answerable (Yes/No)
2. Preserve all numerical constraints, time ranges, and specific entities
3. Do not merge distinct requirements into one
4. Numbered lists in the query often indicate separate sub-questions
5. Focus on what the review must investigate or analyze, not general background

Output as JSON array of strings, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1b — 轻量知识提取
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_EXTRACT_KEY_POINTS = """\
You are a senior scientific literature analysis expert. Extract key knowledge points from the provided document.

**Task Context**:
The user is writing a scientific literature review to answer:
---
{query}
---

**Source Document**: {source_id}
**File**: {file_name}

**Document Content** (may be truncated):
---
{text}
---

**Extraction Requirements**:
Extract as a JSON array. Each element must include:

1. **category**: One of ["definition", "mechanism", "data_finding", "methodology", "limitation", "comparison", "claim"]
2. **statement**: A complete, precise description of the knowledge point extracted from the document.
3. **importance**: "critical" | "mandatory" | "standard"
   - critical = Core innovation, key theoretical result, fundamental mechanism
   - mandatory = Important definition, method description, key experimental evidence
   - standard = Supplementary information, background context
4. **paper_specific_terms**: A list of paper-specific terms, method names, abbreviations, or
   theorem references used in the statement that are unique to this paper and would NOT be
   understood by a general domain expert without reading this specific paper.
   Example: ["[METHOD_A]", "[THEOREM_3]", "[ABBREVIATION]"]
   If none, use an empty list [].

Output as JSON array directly, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1c — 概念泛化
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_GENERALIZE_CONCEPTS = """\
You are an expert at abstracting specific research findings into domain-general concepts.

**Research Question**:
---
{query}
---

**Extracted Knowledge Points** (from all source documents):
{key_points_json}

**Task**: For each knowledge point, produce a "generalized_concept" that:
1. Captures the same underlying principle, mechanism, or finding
2. Uses domain-general terminology instead of paper-specific names
3. Would be meaningful and interpretable even if the reader has NOT read the specific source papers
4. Retains enough specificity to be useful for generating evaluation criteria

**Examples of generalization** (scientific literature review context):
- "[METHOD_A] uses dimension-wise trimming" -> "robust methods achieve robustness by trimming or clipping extreme values"
- "[METHOD_B] provides theoretical guarantees against arbitrary failures" -> "median-based approaches provide theoretical robustness guarantees against arbitrary data corruption"
- "[TECHNIQUE] injects calibrated noise for privacy protection" -> "privacy-preserving mechanisms inject calibrated noise to provide formal guarantees"

**Output Format**: Return the same JSON array but with an additional "generalized_concept" field
added to each element. Preserve all original fields.

Output as JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1c 补充 — 领域通用术语过滤（LLM 驱动）
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_FILTER_DOMAIN_TERMS = """\
Given the following research context and a list of extracted terms, determine which terms are **domain-general** (well-known to any expert in the broader field) and which are **paper-specific** (unique to the specific papers being analyzed).

**Research Question**:
{query}

**Extracted Terms**:
{terms_list}

**Classification Rules**:
1. **Domain-general (REMOVE from forbidden list)**: Terms that any PhD student in the broader research area would recognize without reading these specific papers. This includes:
   - Common algorithms, architectures, and techniques in the field
   - Standard metrics, datasets, benchmarks
   - Fundamental mathematical/statistical/scientific concepts
   - Widely-used abbreviations and nomenclature
   - General analysis terms (convergence, robustness, significance, etc.)

2. **Paper-specific (KEEP in forbidden list)**: Terms that are:
   - Novel method names coined by the authors
   - Specific theorem or equation references
   - Specific parameter settings tied to the paper's contribution
   - Novel combinations of known techniques with a new name
   - Proper nouns referring to specific systems/models/datasets introduced in these papers

When uncertain, lean toward REMOVING the term (prefer keeping it as a usable concept).

**Output**: Return a JSON array containing ONLY the paper-specific terms that should remain in the forbidden list.

Output as JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Few-shot 示例（科学调研专用）
# ═══════════════════════════════════════════════════════════════════════════

FEWSHOT_IA = '''
GOOD items (from human-designed rubrics for scientific literature reviews):
- "Does the report accurately define the core concept of [CENTRAL_CONCEPT] by specifying its objective, key components, and how it differs from related approaches?"
- "Does the report explain the formal definition of [KEY_TECHNIQUE] and its role within the broader [DOMAIN] framework?"
- "Does the report distinguish between [CATEGORY_A] and [CATEGORY_B] as two fundamentally different approaches with distinct assumptions and applicability?"
- "Does the report classify the main categories of [METHOD_TYPE] (e.g., [SUBTYPE_1] vs. [SUBTYPE_2]) and explain their respective characteristics?"
- "Does the report identify the key limitations of [APPROACH] when applied under [CONDITION]?"
- "Does the report define what constitutes [PROPERTY] and explain why this property is particularly important for [APPLICATION]?"

BAD items (NEVER do this):
- "Does the report mention relevant concepts?" (vague, "relevant" is undefined)
- "Does the report provide sufficient background?" ("sufficient" is subjective)
- "Does the report state the definition of [PAPER_SPECIFIC_METHOD]?" (paper-specific method name — should use domain-general language)
- "Does the report describe the [PAPER_SPECIFIC_MECHANISM]?" (paper-specific mechanism)
- "Does the report define [OVERLY_GENERAL_TOPIC]?" (too general — assumes the reader doesn't know the basics)
'''

FEWSHOT_SR = '''
GOOD items (from human-designed rubrics for scientific literature reviews — emphasizing deep analysis):
- "Does the report analyze why [CONDITION_X] fundamentally undermines the effectiveness of traditional [APPROACH_TYPE] methods?"
- "Does the report explain the intrinsic tension between [MECHANISM_A] and [MECHANISM_B], demonstrating why these two mechanisms interfere with each other?"
- "Does the report compare the vulnerability profiles of different methods under combined scenarios ([SCENARIO_1] + [SCENARIO_2])?"
- "Does the report evaluate the scalability limitations of current [METHOD_CLASS] approaches when the [SCALING_FACTOR] exceeds practical thresholds?"
- "Does the report analyze the conditions under which a method provides complete versus partial effectiveness, and discuss the gap?"
- "Does the report explain the causal chain linking [FACTOR_A] to the degradation of [PROPERTY_B]?"
- "Does the report assess the trade-offs between [METRIC_1] and [METRIC_2] in the context of [CONDITION]?"
- "Does the report derive the relationship between [PARAMETER] and the [OUTCOME] that determines feasibility?"
- "Does the report discuss the fundamental limitations of current [METHOD_CLASS] against sophisticated [CHALLENGE_TYPE]?"
- "Does the report explain the scientific logic behind why [METHOD_A] fails to maintain its guarantee when [ADVERSARIAL_CONDITION]?"

BAD items (NEVER do this — these are too shallow for SR dimension):
- "Does the report mention that [CONDITION] is a challenge?" (mere mention — not analysis)
- "Does the report list the main types of [METHOD]?" (listing is not reasoning)
- "Does the report include a comparison table of different methods?" (presence of table != analytical comparison)
- "Does the report describe how [TECHNIQUE] works?" (description is not analysis)
- "Does the report state that [METHOD] is effective?" (restating a conclusion is not demonstrating understanding)
- "Does the report note the limitations of existing approaches?" (vague, not testing specific analysis)
- "Does the report discuss relevant limitations?" (vague, undefined)
- "Does the report cover the key findings from the literature?" (content-driven, not reasoning-driven)
'''

FEWSHOT_SYNTH = '''
GOOD items (from human-designed rubrics for scientific literature reviews — all Standard, 1 point):
- "Does the report structure the review with clearly delineated sections including introduction, methodology overview, comparative analysis, and future directions?"
- "Does the report provide a hierarchical classification or taxonomy of the reviewed methods (e.g., as a table or classification diagram)?"
- "Does the report include a structured comparison table summarizing the key properties, strengths, and limitations of different approaches?"
- "Does the report identify specific deep research directions or open problems, going beyond generic suggestions?"
- "Does the report discuss recent research trends (2024/2025) in the field, demonstrating awareness of the latest developments?"
- "Does the report follow a logical progression from problem definition to method categorization to critical evaluation?"
- "Does the report summarize consensus findings across the reviewed literature where such consensus exists?"
- "Does the report maintain a consistent academic writing style with proper use of domain terminology?"
- "Does the report cite sources appropriately throughout the text, mapping claims to their supporting references?"
- "Does the report provide an abstract or executive summary that accurately reflects the review's scope and conclusions?"

BAD items:
- "Does the report have good structure?" (vague, not judgeable)
- "Does the report write well?" (subjective)
- "Does the report provide sufficient detail?" ("sufficient" undefined)
- "Does the report comprehensively cover all aspects?" ("comprehensively" subjective)
'''


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 2 — 科学调研专用质量驱动生成 Prompt
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_GENERATE_IA = """\
You are an expert evaluator of scientific literature reviews. Generate high-quality rubric items for the **Information Acquisition (IA)** dimension.

## CORE PRINCIPLE
You are generating a DOMAIN-LEVEL QUALITY STANDARD for evaluating scientific literature reviews in this research domain. The source documents inform your understanding of what concepts a good review should cover — but each rubric item must be GENERALIZABLE to any literature review in this domain, NOT tied to specific source documents.

Each item should evaluate: "Does a good literature review in this domain accurately acquire and precisely define the core concepts of this field?"

In scientific literature reviews, precise concept definition is foundational — the review must demonstrate accurate understanding of domain terminology, proper classification of methods/techniques, and clear identification of known limitations.

## RESEARCH QUESTION
---
{query}
---

## SUB-QUESTIONS the review must address:
{sub_questions}

## AVAILABLE SOURCES
{source_ids}

## GENERALIZED KNOWLEDGE POINTS
The following are key concepts (already generalized from source documents) that a good review should cover:
{generalized_points}

## FORBIDDEN TERMS (paper-specific — do NOT use in any rubric item)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_ia}

## GENERATION RULES

1. **CONCEPT PRECISION FOCUS**: Each item evaluates whether the review has accurately acquired and precisely defined domain knowledge. Scientific reviews require terminological precision — test whether the review defines core concepts correctly (not just mentions them).

2. **DOMAIN-GENERAL LANGUAGE**: Use generalized concepts from above. Do NOT use paper-specific method names, abbreviations, or proper nouns unique to single sources. You MAY use domain-general technical terms that any domain expert would recognize (e.g., names of well-established methods, standard metrics, or widely-used frameworks).

3. **NO GENERAL BACKGROUND**: Do NOT ask about general domain background that any researcher would already know (e.g., "Does the report define machine learning?"). Focus on specialized concepts directly relevant to the research question.

4. **MULTI-SOURCE ITEMS (at least 30%)**: At least 30% of IA items should reference multiple sources (source_ids with 2+ sources). These items test whether the review compares, contrasts, or synthesizes definitions/concepts across different papers. Example: "Does the report distinguish how [SOURCE_A] and [SOURCE_B] define [CONCEPT] differently?"

5. **COVERAGE REQUIREMENTS**: Generate items covering:
   - Core concept definitions relevant to the research question (2-3 items)
   - Technical classification and categorization of methods/techniques (3-4 items)
   - Key method/technique principle descriptions (3-4 items)
   - Known limitations and boundary conditions of approaches (2-3 items)
   - Important distinctions between related concepts (2-3 items)

   **MINIMUM COVERAGE (6 sub-topics required)**: The generated items must collectively cover at least 6 of the following sub-topics. Before finalizing, verify your coverage and add items for any missing sub-topics:
   1. Core concept definitions directly relevant to the research question (e.g., [CENTRAL_CONCEPT], [KEY_FRAMEWORK], [PRIMARY_MECHANISM])
   2. Method/technique classification (major categories of approaches, paradigm distinctions, methodology taxonomy)
   3. Key parameters, variables, and their effects (important configuration parameters, scaling factors, constraint conditions)
   4. Known limitations and boundary conditions (assumptions, applicability constraints, failure modes of approaches)
   5. Important distinctions between related concepts (overlapping terminology, competing frameworks, fine-grained differences)
   6. Foundational principles and theoretical foundations (core theoretical results, fundamental assumptions, mathematical formulations)

5. **COGNITIVE HIERARCHY — MANDATORY VERB DIVERSITY**: IA tests concept acquisition at the remember/understand level. You MUST distribute verbs across the following categories (do NOT overuse any single verb):
   
   **Category A — Concept Definition (~25%)**: define, precisely define, accurately define
     Example: "Does the report define X as...?"
   
   **Category B — Identification (~25%)**: identify, recognize, pinpoint
     Example: "Does the report identify the key limitation that...?"
   
   **Category C — Classification (~25%)**: classify, categorize, distinguish, differentiate
     Example: "Does the report classify X into at least two categories based on...?"
   
   **Category D — Principle Explanation (~25%)**: explain, describe
     Example: "Does the report explain the principle by which...?"
   
   **IMPORTANT**: No single verb should appear in more than 30% of items. If you find yourself using "explain" repeatedly, switch to "identify", "classify", or "define".
   
   **FORBIDDEN weak verbs**: mention, list, include, contain, have, cover, present, provide.
   
   **DIMENSION BOUNDARY — DO NOT TEST**: mechanism analysis, comparative evaluation, or analytical reasoning. Those belong to SR.

6. **PRECISION OVER PRESENCE**: Each item should test whether the review provides a PRECISE definition/explanation, not merely whether a topic appears in the text.
   - BAD (mere presence): "Does the report mention [CENTRAL_TECHNIQUE]?"
   - GOOD (precision test): "Does the report accurately define [CENTRAL_TECHNIQUE] by specifying its formal objective, key components, and how it differs from related approaches?"

7. **source_ids SEMANTICS**: source_ids indicate which source documents informed this rubric item's design. They do NOT mean the review must cite those specific sources. Use [] (empty) for items that evaluate general domain knowledge.

8. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.

9. **START WITH "Does the report"**: All items must start with "Does the report".

10. **NO VAGUE WORDS**: Do not use words like "sufficient", "relevant", "comprehensive", "adequate", "proper", "appropriate", "good", "effective" without concrete operational criteria.

11. **OBSERVABLE CHECKLIST (OCR) — MANDATORY for define/explain**:
   - NEVER bare "Does the report explain X?" or "Does the report define X?"
   - ALWAYS use ONE of: (a) "..., i.e., <single verifiable proposition>"; (b) "..., that <specific fact>"; (c) `required_elements` listing 2-4 checkable propositions
   - Provide `required_elements`: 2-4 short, independently checkable propositions (domain-general, not paper-specific).
   - Prefer `state that` / `identify that` over bare `explain` when testing concept acquisition.

12. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items): Foundational definitions that are prerequisite to understanding the entire domain (e.g., core formal definitions, fundamental taxonomy).
- Mandatory ({mandatory_target} items): Important concept distinctions, method classifications, key principle explanations, notable limitations.
- Standard ({standard_target} items): Secondary concept definitions, scope descriptions, supplementary classifications.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1"] or ["S1","S2"], "importance": "critical|mandatory|standard", "competency_category": "definition|evidence|methodology|limitation|comparison", "required_elements": ["observable proposition A", "observable proposition B"], "judgment_mode": "binary|checklist"}}

Output JSON array only, no other text.
"""

PROMPT_OPERATIONALIZE = """\
You are an expert rubric engineer for **scientific literature reviews**. Rewrite rubric items so each is **objectively scorable** (no subjective "adequately explain").

## RULES
1. Replace bare explain/define with either:
   - "Does the report state that ..., i.e., <one verifiable fact>?" (judgment_mode: binary), OR
   - checklist with `required_elements` (2-4 propositions, judgment_mode: checklist)
2. required_elements: 2-4 short English propositions; each independently verifiable from review text.
3. Keep domain-general language; do NOT add paper-specific names/numbers from sources.
4. Preserve importance, source_ids, competency_category.
5. Do NOT change items that already contain i.e./that/including checklist structure.

## ITEMS TO REWRITE
{items_json}

Output JSON array with same length and order. Each object:
{{"question": "...", "source_ids": [...], "importance": "...", "competency_category": "...", "required_elements": [...], "judgment_mode": "binary|checklist"}}

Output JSON only.
"""

PROMPT_GENERATE_SR = """\
You are an expert evaluator of scientific literature reviews. Generate high-quality rubric items for the **Scientific Reasoning (SR)** dimension.

## CORE PRINCIPLE
You are generating a DOMAIN-LEVEL QUALITY STANDARD for evaluating scientific literature reviews in this research domain. This is the MOST IMPORTANT dimension (62% weight). The source documents inform your understanding of what constitutes a good review in this domain — but each rubric item must be GENERALIZABLE to any literature review in this domain, NOT tied to specific source documents or specific findings.

Each item should evaluate: "Does a good literature review in this domain demonstrate the analytical depth to [analyze/explain/compare/evaluate] [domain-relevant method or phenomenon]?"

You are testing the review's DEPTH OF ANALYTICAL REASONING — whether it demonstrates deep understanding through mechanism analysis, cross-method comparison, bottleneck identification, and logical argumentation. Each item must test whether the review goes beyond surface-level description to provide genuine scientific insight.

## CRITICAL DESIGN NOTES
- This dimension targets **28-38 items** (the largest of all dimensions)
- **Critical items should constitute ~25%** — assign Critical to items testing the deepest analysis
- Items should NOT have topic prefix labels (e.g., no "[Mechanism Analysis]" prefix)
- **NO ANSWER LEAKAGE**: NEVER reveal the answer or conclusion in the question. BAD: "Does the report explain why noise fundamentally hinders anomaly detection?" (reveals that noise hinders detection). GOOD: "Does the report evaluate whether the addition of noise to model updates creates challenges for anomaly detection mechanisms?" (does not reveal the answer). The rubric item should test whether the report DERIVES the answer, not whether it STATES a pre-given conclusion.
- **NO "identify" IN CRITICAL/MANDATORY ITEMS**: Use strong analytical verbs (analyze, evaluate, explain, derive, argue, compare, demonstrate) instead of "identify" or "describe" for Critical and Mandatory items. "identify" is acceptable for Standard items only.

## RESEARCH QUESTION
---
{query}
---

## SUB-QUESTIONS:
{sub_questions}

## AVAILABLE SOURCES
{source_ids}

## GENERALIZED KNOWLEDGE POINTS
{generalized_points}

## FORBIDDEN TERMS (paper-specific — do NOT use in any rubric item)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_sr}

## ANALYSIS FOCUS AREAS (by priority — ensure coverage across all areas):

1. **Mechanism Analysis** (highest priority — ~30% of items): Test whether the review analyzes WHY and HOW methods work at a deep level.
   - Analyze the internal working principles of key methods
   - Explain causal chains and dependency relationships
   - Demonstrate understanding of failure modes and their root causes

2. **Cross-method Comparison** (~25% of items): Test whether the review provides rigorous comparative analysis.
   - Compare strengths and weaknesses across different approaches
   - Evaluate trade-offs between competing methods
   - Assess applicability of methods to different scenarios/conditions

3. **Bottleneck / Limitation Analysis** (~20% of items): Test whether the review identifies fundamental constraints.
   - Analyze scalability limitations and their causes
   - Identify theoretical or practical bottlenecks
   - Evaluate conditions under which methods break down

4. **Strategy Reasoning** (~15% of items): Test whether the review explains the logic behind design choices and method decisions.
   - Analyze the scientific logic behind proposed strategies or approaches
   - Evaluate the reasoning behind design decisions and trade-offs
   - Assess the interplay between competing approaches or paradigms

5. **Effect Quantification** (~10% of items): Test whether the review provides quantitative analysis.
   - Analyze how method effectiveness varies with parameters
   - Evaluate experimental validation of theoretical claims
   - Compare quantitative results across studies

## GENERATION RULES

1. **REASONING OVER DESCRIPTION**: Every item must test ANALYTICAL REASONING, not surface-level description. The review must demonstrate "why" and "how", not just "what".

2. **COGNITIVE HIERARCHY — MANDATORY VERB DIVERSITY**: SR tests analytical reasoning at the analyze/evaluate level. You MUST distribute verbs across the following categories. Do NOT let any single verb exceed 25% of items.

   **Category A — Mechanism Analysis (~25%)**: analyze why, analyze the mechanism, analyze how
     Tests: Internal working principles, causal chains, failure mode root causes
     Example: "Does the report analyze why norm-based robust methods fail against [ADVERSARIAL_CONDITION]?"

   **Category B — Comparative Evaluation (~20%)**: compare, contrast, evaluate trade-offs
     Tests: Rigorous cross-method comparison with explicit criteria, scenario-based evaluation
     Example: "Does the report compare [APPROACH_A] versus [APPROACH_B], evaluating which preserves [DESIRABLE_PROPERTY] better?"

   **Category C — Principle Explanation (~15%)**: explain the scientific logic, explain why, explain how
     Tests: Deep understanding of WHY methods work, not just WHAT they do
     Example: "Does the report explain the scientific logic behind why [TECHNIQUE] can identify [TARGET_PROPERTY]?"

   **Category D — Critical Assessment (~15%)**: evaluate effectiveness, assess limitations, assess applicability
     Tests: Judgment of method quality, boundary conditions, scalability constraints
     Example: "Does the report evaluate the scalability limitations of [METHOD_CLASS] in real-world deployments?"

   **Category E — Argumentation & Synthesis (~15%)**: argue, justify, critique, synthesize
     Tests: Logical argument construction, critical perspective, integration of multiple findings
     Example: "Does the report argue that no single approach can provide universal effectiveness, and justify this claim by analyzing the fundamental trade-off between competing objectives?"

   **Category F — Quantitative/Formal Reasoning (~10%)**: derive, quantify, demonstrate
     Tests: Mathematical/formal reasoning, parameter sensitivity, quantitative relationships
     Example: "Does the report derive or demonstrate the quantitative relationship between [PARAMETER] and [OUTCOME] in [CONTEXT]?"

   **IMPORTANT**: Before finalizing, count your verb distribution. If "analyze" appears in more than 30% of items, replace some with "evaluate", "compare", "argue", or "derive".

   **STRICTLY FORBIDDEN weak verbs** (items using these will be deleted):
   mention, list, include, contain, have, describe, state, cover, present, provide.

   **DIMENSION BOUNDARY — DO NOT TEST**: mere concept definitions, simple classifications, or structural completeness. Those belong to IA and Synth.

3. **TEST UNDERSTANDING, NOT PRESENCE**: Each item should reveal whether the review author truly understands a concept through their analysis.
   - BAD (presence check): "Does the report describe the [METHOD]?"
   - GOOD (understanding test): "Does the report analyze the conditions under which [METHOD] loses its effectiveness guarantee, and explain the underlying cause?"
   - BAD (restating): "Does the report state that [TECHNIQUE] adds noise?"
   - GOOD (analysis): "Does the report explain the fundamental trade-off between [PARAMETER_A] allocation and [PROPERTY_B], analyzing how this trade-off manifests in practice?"

4. **REQUIRE REASONING CHAINS**: At least 8 items must require the review to demonstrate a multi-step reasoning chain (e.g., "analyze why X leads to Y, which in turn causes Z").

5. **CROSS-SOURCE ANALYSIS**: At least 40% of items should have multiple source_ids, requiring the review to synthesize analysis across multiple documents.

6. **DOMAIN-GENERAL LANGUAGE**: Use generalized concepts. You MAY use domain-general technical names that any domain expert would recognize (e.g., names of well-established methods, standard metrics, or widely-used frameworks). Do NOT use paper-specific abbreviations or method names unique to single papers.

7. **NO TOPIC PREFIX LABELS**: Do not add category labels like "[Mechanism Analysis]" before items. Items should start directly with "Does the report...".

8. **source_ids SEMANTICS**: source_ids indicate which source documents informed this rubric item's design. They do NOT mean the review must cite those specific sources. Use [] (empty) for items that evaluate general analytical capabilities.

9. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No. Specify concrete analytical requirements.

10. **START WITH "Does the report"**: All items must start with "Does the report".

11. **NO VAGUE WORDS**: Do not use words like "sufficient", "relevant", "comprehensive", "adequate", "proper", "appropriate" without concrete operational criteria.

12. **OBSERVABLE CHECKLIST (OCR)**: Prefer analyze/evaluate/derive over bare "explain". Any explain/define MUST include i.e./that/checklist OR `required_elements` (2-3 verifiable propositions). Mechanism items: separate condition P, mechanism M, outcome Q as elements.

13. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items, ~25%): The deepest analytical items — core mechanism failure analysis, fundamental bottleneck explanations, critical cross-method comparisons. Assign Critical to items testing DEEPEST analytical reasoning: mechanism derivation, theoretical limitation proof, fundamental trade-off quantification. Use strong verbs: analyze, derive, argue, prove, demonstrate.
- Mandatory ({mandatory_target} items, ~50%): Important mechanism explanations, comparative analysis, bottleneck identification, strategy reasoning.
- Standard ({standard_target} items, ~25%): Secondary associations, supplementary quantitative analysis, forward-looking reasoning.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1","S2"] or ["S1"], "importance": "critical|mandatory|standard", "competency_category": "mechanism|comparison|limitation|synthesis", "required_elements": ["..."], "judgment_mode": "binary|checklist"}}

Output JSON array only, no other text.
"""

PROMPT_GENERATE_SYNTH = """\
You are an expert evaluator of scientific literature reviews. Generate rubric items for the **Report Synthesis (Synth)** dimension.

## CORE PRINCIPLE
You are evaluating the STRUCTURAL COMPLETENESS and ACADEMIC RIGOR of the literature review as a standalone academic document. This dimension focuses on the review's organization, taxonomy construction, temporal awareness, logical flow, and research gap identification.

**SPECIAL: ALL items in this dimension are Standard (1 point each).** There are NO Critical or Mandatory items. This dimension evaluates structural completeness, not analytical depth (which is captured in SR).

## RESEARCH QUESTION
---
{query}
---

## SUB-QUESTIONS:
{sub_questions}

## AVAILABLE SOURCES
{source_ids}

## GENERALIZED KNOWLEDGE POINTS
{generalized_points}

## FORBIDDEN TERMS (paper-specific — do NOT use in any rubric item)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_synth}

## GENERATION RULES

1. **IMPORTANCE RULES**: At most 2 items may be "mandatory" — assign mandatory ONLY to the most essential structural checks (e.g., overall review structure completeness, conclusion synthesis). ALL other items MUST be "standard". Do NOT assign "critical" importance to any Synth item — critical items belong exclusively to the SR dimension.

2. **STRUCTURAL COMPLETENESS**: Focus on whether the review has a complete, well-organized academic structure.

3. **DOMAIN-GENERAL LANGUAGE**: Use generalized concepts. Do NOT use paper-specific method names, model names, or abbreviations from the FORBIDDEN TERMS list above. Use domain-general category names instead (e.g., "additive methods" not "[PAPER_METHOD]", "reparameterization-based approaches" not "[PAPER_ABBREVIATION]").

4. **COVERAGE AREAS** (ensure all are represented):
   - **Review structure**: Sections, logical flow, introduction, body organization, conclusion (2-3 items)
   - **Classification/taxonomy**: Hierarchical method classification, taxonomy diagram/table (2-3 items)
   - **Comparison tools**: Structured comparison tables, feature matrices (1-2 items)
   - **Citation & source coverage**: Summary table of key papers, proper in-text citations, source attribution accuracy (2-3 items, competency_category = "citation")
   - **Temporal awareness**: Recent research trends, chronological progression, milestone identification (1-2 items)
   - **Research gaps**: Specific open problems, concrete future research directions (1-2 items)
   - **Consensus summary**: Domain consensus findings, debatable areas (1-2 items)
   - **Writing quality**: Academic tone, consistent terminology, logical coherence (1-2 items)

5. **VERB DIVERSITY — Structure + Evaluation**: Synth tests structural completeness AND evaluative judgment. Distribute verbs across:
   
   **Category A — Structural Completeness (~50%)**: include, provide, structure, organize, present, contain, have
     Tests: Presence of required sections, taxonomy diagrams, comparison tables
     Example: "Does the report include a hierarchical taxonomy of the reviewed methods?"

   **Category B — Evaluative Judgment (~30%)**: assess, evaluate, demonstrate, maintain
     Tests: Quality of structure, logical coherence, consistency, effectiveness of organization
     Example: "Does the report demonstrate a logical progression from problem characterization to method taxonomy to critical gaps?"

   **Category C — Synthesis & Awareness (~20%)**: summarize, identify, cite, trace
     Tests: Consensus awareness, temporal coverage, citation consistency, trend identification
     Example: "Does the report summarize the consensus findings across the reviewed literature where such consensus exists?"
   
   **IMPORTANT**: At least 30% of Synth items must use evaluative verbs (assess, evaluate, demonstrate) rather than purely structural verbs.

6. **NO ANALYTICAL DEPTH REQUIREMENTS**: Do NOT ask about mechanism analysis, reasoning depth, or comparative evaluation of methods — those belong to SR. Synth items test STRUCTURE, COMPLETENESS, and ORGANIZATIONAL QUALITY.

   **DIMENSION BOUNDARY — DO NOT TEST**: concept definitions (IA), mechanism analysis (SR), or method comparisons (SR).

7. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.

8. **START WITH "Does the report"** or "Is the" for grammar: Items should use these prefixes.

9. **NO VAGUE WORDS**: Do not use words like "good", "well", "sufficient", "comprehensive", "adequate" without concrete operational criteria.

10. **NO CHINESE**: All items must be in English.

11. **SOURCE-INDEPENDENT**: Most Synth items will have empty source_ids [] since they evaluate the review as a standalone document. A few items checking citation practices may reference sources.

12. **MINIMUM COVERAGE (8 sub-topics required)**: The generated items must collectively cover at least 8 of the following sub-topics. Before finalizing, verify your coverage and add items for any missing sub-topics:
    1. Review structure completeness (Abstract, Introduction, Methodology Overview, Comparative Analysis, Challenges, Future Directions)
    2. Taxonomy/classification (method taxonomy, paradigm hierarchy, approach categorization)
    3. Temporal awareness (chronological evolution of the field, key milestones)
    4. Forward-looking analysis (specific future research directions, at least 3 concrete research entry points)
    5. Comparison framework (method comparison under different conditions or scenarios)
    6. Trade-off analysis (key trade-offs identified in the field, e.g., accuracy vs. efficiency, generality vs. specificity)
    7. Consensus/limitations (areas where consensus exists, areas of ongoing debate, domain boundaries)
    8. Visual aids (taxonomy charts, comparison tables, timeline diagrams, architecture diagrams)
    9. Recent trends awareness (latest developments, emerging challenges, new paradigms)
    10. Conclusion synthesis (reiteration of key findings, open problems, unresolved debates)

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": [] or ["S1"], "importance": "standard", "competency_category": "structure|citation|visualization|language|recommendation|integrity"}}

ALL items must have importance = "standard". Output JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 3b — LLM 去重 Prompt
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_DEDUPLICATE = """\
You are an expert rubric evaluator. Review ALL rubric items below and identify redundant/duplicate items that test essentially the same thing.

**Research Question**:
---
{query}
---

**All Rubric Items** ({total_count} total):
{items_text}

**Task**: Identify pairs or groups of items that are redundant (testing the same concept with slightly different wording).

Output as JSON:
{{
  "redundant_groups": [
    {{
      "items": ["[information_acquisition#0]", "[scientific_reasoning#5]"],
      "reason": "Both check whether the report defines the same core concept with similar precision",
      "keep": "[information_acquisition#0]",
      "remove": ["[scientific_reasoning#5]"]
    }}
  ]
}}

Rules:
1. Two items are redundant if they test essentially the same concept, even if worded differently.
2. If items test different aspects (e.g., one tests definition, another tests mechanism), they are NOT redundant.
3. For each redundant group, specify which item to KEEP (prefer the clearer, more specific one).
4. If no redundancies exist, return {{"redundant_groups": []}}.
5. Only flag truly redundant items — do NOT flag items that are complementary or test different facets.

Output JSON only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  轻量校准规则
# ═══════════════════════════════════════════════════════════════════════════

# 模糊词列表
VAGUE_WORDS = [
    "sufficient", "relevant", "comprehensive", "adequate", "proper",
    "appropriate", "good", "effective", "thorough", "detailed",
    "in-depth", "high-quality", "well-structured", "well-written",
    "properly", "effectively", "appropriately", "comprehensively",
    "adequately", "sufficiently", "relevantly",
]

# 弱动词列表 — IA 和 SR 维度禁止使用
# 注意：Synth 维度允许结构性动词，不检查弱动词
WEAK_VERBS_IA = [
    "mention", "list", "include", "contain", "have",
    "cover", "present", "provide",
]

# SR 维度弱动词检查更严格 — 额外禁止 describe 和 state
WEAK_VERBS_SR = [
    "mention", "list", "include", "contain", "have",
    "describe", "state", "cover", "present", "provide",
]


# ═══════════════════════════════════════════════════════════════════════════
#  主类
# ═══════════════════════════════════════════════════════════════════════════

class RubricGenerator:
    """科学调研报告评分表生成器。"""

    def __init__(self, config):
        self.config = config
        self.client = config.get_client()

    # ─────────────────────────────────────────────────────────────────────
    #  主入口
    # ─────────────────────────────────────────────────────────────────────

    def generate(
        self,
        sources: List[SourceDocument],
        query: str,
        task_type: str = "literature_review",
    ) -> Dict[str, Any]:
        """主入口：3阶段生成评分表。"""
        logger.info("=" * 60)
        logger.info("Starting Rubric Generation — Scientific Literature Review")
        logger.info("=" * 60)

        source_ids = [s.source_id for s in sources]

        # ── Stage 1: 轻量知识提取 + 概念泛化 ──
        logger.info("\n[Stage 1a] Parsing query sub-questions...")
        sub_questions = self._parse_sub_questions(query)

        logger.info("\n[Stage 1b] Extracting key points from sources...")
        raw_key_points = self._extract_key_points(sources, query)

        logger.info("\n[Stage 1c] Generalizing concepts...")
        generalized_points, forbidden_terms = self._generalize_concepts(
            raw_key_points, query
        )

        # ── Stage 2: 科学调研专用质量驱动生成 ──
        logger.info("\n[Stage 2] Generating rubric items (scientific literature review)...")

        ia_items = self._generate_dimension(
            "information_acquisition", query, sub_questions,
            generalized_points, forbidden_terms, sources,
        )
        sr_items = self._generate_dimension(
            "scientific_reasoning", query, sub_questions,
            generalized_points, forbidden_terms, sources,
        )
        synth_items = self._generate_dimension(
            "report_synthesis", query, sub_questions,
            generalized_points, forbidden_terms, sources,
            task_type=task_type,
        )

        # ── Stage 3a: 维度特异性轻量校准 ──
        logger.info("\n[Stage 3a] Light calibration (dimension-specific rules)...")
        ia_items = self._light_calibrate(ia_items, "information_acquisition", forbidden_terms=forbidden_terms)
        sr_items = self._light_calibrate(sr_items, "scientific_reasoning", forbidden_terms=forbidden_terms, all_dimension_items={"information_acquisition": ia_items})
        synth_items = self._light_calibrate(synth_items, "report_synthesis", forbidden_terms=forbidden_terms, all_dimension_items={"information_acquisition": ia_items, "scientific_reasoning": sr_items})

        # ── Stage 3a+: Synth source_ids 补全 ──
        # 科学调研场景：Synth 维度的 source_ids 覆盖率通常很低，通过关键词匹配补全
        synth_items = self._fill_synth_source_ids(synth_items, source_ids)

        # ── Stage 3b: LLM 去重 ──
        logger.info("\n[Stage 3b] LLM deduplication...")
        ia_items, sr_items, synth_items = self._llm_deduplicate(ia_items, sr_items, synth_items, query)

        # ── Stage 3c: Critical 后备提升（确保 SR 维度有足够 Critical 项） ──
        sr_config = DIMENSION_CONFIG["scientific_reasoning"]
        target_critical = max(1, round(sr_config["item_range"][1] * sr_config["role_dist"]["critical"]))
        current_critical = sum(1 for it in sr_items if normalize_importance(it.get("importance", "")) == "critical")
        if current_critical < target_critical:
            needed = target_critical - current_critical
            # 按 question_length 排序，选出最高质量的非 Critical 项提升
            candidates = [
                it for it in sr_items
                if normalize_importance(it.get("importance", "")) != "critical"
            ]
            candidates.sort(key=lambda x: len(x.get("question", "")), reverse=True)
            for i in range(min(needed, len(candidates))):
                candidates[i]["importance"] = "critical"
                logger.info(f"  Promoted SR item to Critical: {candidates[i].get('question', '')[:60]}...")
            logger.info(f"  SR Critical promotion: {current_critical} -> {current_critical + min(needed, len(candidates))}")

        # ── Stage 3d: OCR 可观测性操作化 ──
        logger.info("\n[Stage 3d] Observability operationalization (OCR)...")
        ia_items, sr_items, synth_items = self._apply_observability_policy(
            ia_items, sr_items, synth_items,
        )

        # ── 组装 ──
        result = self._assemble(query, task_type, sources, ia_items, sr_items, synth_items)
        self._print_generation_summary(result)
        return result

    # ─────────────────────────────────────────────────────────────────────
    #  Stage 1a: Query 子问题解析
    # ─────────────────────────────────────────────────────────────────────

    def _parse_sub_questions(self, query: str) -> List[str]:
        """解析 query 为子问题列表。"""
        prompt = PROMPT_PARSE_SUBQUESTIONS.format(query=query)
        try:
            result = call_llm_json(
                self.client,
                self.config.rubric_model,
                prompt,
                system="You are an expert at decomposing queries. Output JSON array only.",
                temperature=0.2,
                max_retries=self.config.max_retries,
            )
            if isinstance(result, list):
                sub_qs = [str(q).strip() for q in result if str(q).strip()]
                logger.info(f"  Identified {len(sub_qs)} sub-questions")
                return sub_qs
        except Exception as e:
            logger.warning(f"  Sub-question parsing failed: {e}")
        return []

    # ─────────────────────────────────────────────────────────────────────
    #  Stage 1b: 轻量知识提取
    # ─────────────────────────────────────────────────────────────────────

    def _extract_key_points(
        self, sources: List[SourceDocument], query: str
    ) -> List[Dict[str, Any]]:
        """从每篇源文档提取关键知识点。返回所有文档的合并列表。"""
        all_points = []
        for source in sources:
            logger.info(f"  Extracting from {source.source_id} ({source.file_name})...")
            text = source.full_text[:SOURCE_TEXT_MAX_CHARS]
            if len(source.full_text) > SOURCE_TEXT_MAX_CHARS:
                text += f"\n\n... [truncated at {SOURCE_TEXT_MAX_CHARS} chars] ..."

            prompt = PROMPT_EXTRACT_KEY_POINTS.format(
                query=query,
                source_id=source.source_id,
                file_name=source.file_name,
                text=text,
            )
            try:
                points = call_llm_json(
                    self.client,
                    self.config.extract_model,
                    prompt,
                    system=(
                        "You are a scientific literature analysis expert. "
                        "Extract key knowledge points. Output JSON array only."
                    ),
                    temperature=0.2,
                    max_retries=self.config.max_retries,
                )
                if not isinstance(points, list):
                    points = []
                # 给每个知识点标记来源
                for p in points:
                    p["_source_id"] = source.source_id
                logger.info(f"    -> {len(points)} points extracted")
                all_points.extend(points)
            except Exception as e:
                logger.warning(f"    -> Failed: {e}")

        logger.info(f"  Total: {len(all_points)} key points from {len(sources)} sources")
        return all_points

    # ─────────────────────────────────────────────────────────────────────
    #  Stage 1c: 概念泛化
    # ─────────────────────────────────────────────────────────────────────

    def _generalize_concepts(
        self, key_points: List[Dict[str, Any]], query: str
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        将所有源文档的知识点合并后一次性泛化。
        返回 (泛化后的知识点列表, 禁止使用的术语列表)。
        """
        if not key_points:
            return [], []

        # 提取所有论文特有术语作为禁止列表
        forbidden_terms = set()
        for kp in key_points:
            terms = kp.get("paper_specific_terms", [])
            if isinstance(terms, list):
                for t in terms:
                    t = str(t).strip()
                    if t:
                        forbidden_terms.add(t)
        forbidden_terms = sorted(forbidden_terms)

        # 序列化知识点用于 LLM 调用（去掉内部字段 _source_id）
        clean_points = []
        for kp in key_points:
            clean = {
                "category": kp.get("category", ""),
                "statement": kp.get("statement", ""),
                "importance": kp.get("importance", "standard"),
                "paper_specific_terms": kp.get("paper_specific_terms", []),
            }
            clean_points.append(clean)

        # 如果太长，截断
        points_json = json.dumps(clean_points, ensure_ascii=False, indent=2)
        max_len = 40000
        if len(points_json) > max_len:
            points_json = points_json[:max_len] + "\n... [truncated] ..."

        prompt = PROMPT_GENERALIZE_CONCEPTS.format(
            query=query,
            key_points_json=points_json,
        )

        try:
            generalized = call_llm_json(
                self.client,
                self.config.rubric_model,
                prompt,
                system=(
                    "You are an expert at abstracting specific findings into "
                    "domain-general concepts. Output JSON array only."
                ),
                temperature=GENERATION_TEMPERATURE,
                max_tokens=GENERATION_MAX_TOKENS,
                max_retries=self.config.max_retries,
            )
            if isinstance(generalized, list):
                # 恢复 source_id
                for i, gp in enumerate(generalized):
                    if i < len(key_points):
                        gp["_source_id"] = key_points[i]["_source_id"]
                    else:
                        gp["_source_id"] = "unknown"
                logger.info(f"  Generalized {len(generalized)} concepts")
                logger.info(f"  Raw forbidden terms ({len(forbidden_terms)}): {forbidden_terms[:10]}{'...' if len(forbidden_terms) > 10 else ''}")

                # 用 LLM 过滤领域通用术语，只保留真正的 paper-specific 术语
                if forbidden_terms:
                    forbidden_terms = self._filter_domain_general_terms(forbidden_terms, query)
                    logger.info(f"  After LLM filtering ({len(forbidden_terms)}): {forbidden_terms[:10]}{'...' if len(forbidden_terms) > 10 else ''}")

                return generalized, forbidden_terms
        except Exception as e:
            logger.warning(f"  Concept generalization failed: {e}")

        # 回退：直接使用原始知识点
        logger.info("  Fallback: using raw key points without generalization")
        return key_points, forbidden_terms

    def _filter_domain_general_terms(
        self, raw_terms: List[str], query: str
    ) -> List[str]:
        """用 LLM 从 forbidden_terms 中筛掉领域通用术语，只保留真正的 paper-specific 术语。"""
        if not raw_terms:
            return raw_terms
        prompt = PROMPT_FILTER_DOMAIN_TERMS.format(
            query=query,
            terms_list=", ".join(f'"{t}"' for t in raw_terms),
        )
        try:
            result = call_llm_json(
                self.client,
                self.config.rubric_model,
                prompt,
                system=(
                    "You are an expert at distinguishing paper-specific terms from "
                    "domain-general terminology. Output JSON array only."
                ),
                temperature=0.1,
                max_tokens=2000,
                max_retries=self.config.max_retries,
            )
            if isinstance(result, list) and len(result) > 0:
                filtered = [str(item).strip() for item in result]
                removed = len(raw_terms) - len(filtered)
                if removed > 0:
                    logger.info(f"  Filtered {removed} domain-general terms, kept {len(filtered)} paper-specific")
                return filtered
        except Exception as e:
            logger.warning(f"  Domain term filtering failed: {e}, using raw terms")
        return raw_terms

    # ─────────────────────────────────────────────────────────────────────
    #  Stage 2: 科学调研专用质量驱动生成
    # ─────────────────────────────────────────────────────────────────────

    def _generate_dimension(
        self,
        dimension_id: str,
        query: str,
        sub_questions: List[str],
        generalized_points: List[Dict[str, Any]],
        forbidden_terms: List[str],
        sources: List[SourceDocument],
        task_type: str = "literature_review",
    ) -> List[Dict[str, Any]]:
        """生成单个维度的评分项。"""
        config = DIMENSION_CONFIG[dimension_id]
        # Use weighted upper bound (70% upper, 30% lower) to allow calibration removals
        target_count = int(config["item_range"][0] * 0.3 + config["item_range"][1] * 0.7)
        source_ids = [s.source_id for s in sources]

        # 计算 role 分布
        role_dist = config["role_dist"]
        c_target = max(1, round(target_count * role_dist["critical"]))
        m_target = max(2, round(target_count * role_dist["mandatory"]))
        s_target = max(1, target_count - c_target - m_target)

        # 格式化子问题
        sub_q_text = "\n".join(
            f"  {i+1}. {q}" for i, q in enumerate(sub_questions)
        ) if sub_questions else "  (No sub-questions parsed)"

        # 格式化泛化知识点（精简版，只保留泛化概念和来源）
        gen_summary = self._format_generalized_points(generalized_points)

        # 格式化禁止术语
        forbidden_text = (
            ", ".join(f'"{t}"' for t in forbidden_terms)
            if forbidden_terms
            else "(none identified)"
        )

        # 选择对应的 Prompt 模板
        if dimension_id == "information_acquisition":
            prompt_template = PROMPT_GENERATE_IA
            fewshot = FEWSHOT_IA
        elif dimension_id == "scientific_reasoning":
            prompt_template = PROMPT_GENERATE_SR
            fewshot = FEWSHOT_SR
        else:
            prompt_template = PROMPT_GENERATE_SYNTH
            fewshot = FEWSHOT_SYNTH

        prompt = prompt_template.format(
            query=query,
            sub_questions=sub_q_text,
            source_ids=", ".join(source_ids),
            generalized_points=gen_summary,
            forbidden_terms=forbidden_text,
            fewshot_ia=fewshot if dimension_id == "information_acquisition" else "",
            fewshot_sr=fewshot if dimension_id == "scientific_reasoning" else "",
            fewshot_synth=fewshot if dimension_id == "report_synthesis" else "",
            target_count=target_count,
            critical_target=c_target,
            mandatory_target=m_target,
            standard_target=s_target,
            task_type=task_type,
        )

        system = (
            "You are an expert rubric standards designer for scientific literature reviews. "
            "Generate high-quality rubric items based on the generalized knowledge points. "
            "All output in English. Output JSON array only."
        )

        attempts = 3 if dimension_id == "scientific_reasoning" else 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                items = call_llm_json(
                    self.client,
                    self.config.rubric_model,
                    prompt,
                    system=system,
                    temperature=GENERATION_TEMPERATURE,
                    max_tokens=GENERATION_MAX_TOKENS,
                    max_retries=self.config.max_retries,
                )
                if not isinstance(items, list):
                    items = []

                logger.info(
                    f"  {dimension_id}: Generated {len(items)} raw items"
                    f" (attempt {attempt}/{attempts})"
                )

                # 标准化处理
                normalized = self._normalize_items(items, dimension_id)
                logger.info(
                    f"  {dimension_id}: {len(normalized)} items after normalization"
                )
                if dimension_id == "scientific_reasoning" and not normalized and attempt < attempts:
                    logger.warning(
                        "  scientific_reasoning empty after attempt %s, retrying...",
                        attempt,
                    )
                    time.sleep(2 ** attempt)
                    continue
                if dimension_id == "scientific_reasoning" and not normalized:
                    raise RuntimeError(
                        "scientific_reasoning generation produced 0 items after retries"
                    )
                return normalized

            except Exception as e:
                last_error = e
                logger.error(
                    f"  {dimension_id}: Generation failed "
                    f"(attempt {attempt}/{attempts}) - {e}"
                )
                if dimension_id == "scientific_reasoning" and attempt < attempts:
                    time.sleep(2 ** attempt)
                    continue
                if dimension_id == "scientific_reasoning":
                    raise RuntimeError(
                        f"scientific_reasoning generation failed: {e}"
                    ) from e
                return []
        if last_error:
            raise RuntimeError(
                f"scientific_reasoning generation failed: {last_error}"
            ) from last_error
        return []

    def _format_generalized_points(
        self, points: List[Dict[str, Any]]
    ) -> str:
        """将泛化后的知识点格式化为文本，用于传入生成 Prompt。"""
        parts = []
        for i, p in enumerate(points, 1):
            source = p.get("_source_id", "?")
            cat = p.get("category", "?")
            imp = p.get("importance", "standard")
            stmt = p.get("statement", "")
            gen = p.get("generalized_concept", "")
            parts.append(f"  {i}. [{cat}/{imp}] Source: {source}")
            parts.append(f"     Finding: {stmt}")
            if gen:
                parts.append(f"     Generalized: {gen}")
        return "\n".join(parts)

    def _normalize_items(
        self, items: List[Dict[str, Any]], dim_id: str
    ) -> List[Dict[str, Any]]:
        """对生成的评分项进行标准化处理。"""
        normalized = []
        for item in items:
            q = (item.get("question") or "").strip()
            if not q:
                continue

            # 清理中英混杂
            for prefix in ["报告是否", "报告", "是否"]:
                if q.startswith(prefix):
                    q = q[len(prefix):].strip()
                    break

            # 标准英文前缀
            valid_prefixes = (
                "Does the report", "Is the", "Are the",
                "Can the", "Has the report",
            )
            if not any(q.startswith(p) for p in valid_prefixes):
                if q and q[0].isupper():
                    q = f"Does the report {q[0].lower()}{q[1:]}"
                else:
                    q = f"Does the report {q}"

            # 规范化问题文本
            q = normalize_question_text(q)

            # 规范化 source_ids
            sids = item.get("source_ids", [])
            if not isinstance(sids, list):
                sids = []
            sids = [
                str(s).strip()
                for s in sids
                if s and str(s).strip().lower() != "no-source"
            ]

            # 规范化 importance
            imp = normalize_importance(item.get("importance", "standard"))

            # 推断 competency_category
            cat = item.get("competency_category") or infer_competency_category(q, dim_id)

            normalized.append({
                "question": q,
                "source_ids": sids,
                "importance": imp,
                "competency_category": cat,
                "required_elements": item.get("required_elements") or extract_elements_from_question(q),
                "judgment_mode": item.get("judgment_mode", ""),
            })

        return normalized

    def _apply_observability_policy(
        self,
        ia_items: List[Dict[str, Any]],
        sr_items: List[Dict[str, Any]],
        synth_items: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """OCR：操作化裸 explain/define，过滤仍不可观测的项。"""
        ia_items = self._operationalize_dimension_items(ia_items, "information_acquisition")
        sr_items = self._operationalize_dimension_items(sr_items, "scientific_reasoning")
        synth_items = self._operationalize_dimension_items(
            synth_items, "report_synthesis", strict_explain=False,
        )
        return ia_items, sr_items, synth_items

    def _operationalize_dimension_items(
        self,
        items: List[Dict[str, Any]],
        dimension_id: str,
        *,
        strict_explain: bool = True,
    ) -> List[Dict[str, Any]]:
        if not items:
            return items

        to_rewrite: List[Dict[str, Any]] = []
        kept: List[Dict[str, Any]] = []

        for item in items:
            q = item.get("question", "")
            elems = item.get("required_elements") or []
            if strict_explain and is_naked_explain_define(q, elems):
                to_rewrite.append(item)
            elif not item_passes_observability(
                enrich_item_observability(item, dimension_id), dimension_id,
            ):
                to_rewrite.append(item)
            else:
                kept.append(enrich_item_observability(item, dimension_id))

        if to_rewrite:
            logger.info(f"  OCR rewrite queue ({dimension_id}): {len(to_rewrite)} items")
            rewritten = self._llm_operationalize_items(to_rewrite)
            for raw in rewritten:
                enriched = enrich_item_observability(raw, dimension_id)
                if item_passes_observability(enriched, dimension_id):
                    kept.append(enriched)
                else:
                    logger.debug(
                        f"  OCR dropped after rewrite: {enriched.get('question', '')[:60]}"
                    )

        if strict_explain and dimension_id in ("information_acquisition", "scientific_reasoning"):
            max_ratio = 0.35 if dimension_id == "information_acquisition" else 0.15
            explain_items = [it for it in kept if has_explain_or_define(it.get("question", ""))]
            max_n = max(1, int(len(kept) * max_ratio))
            if len(explain_items) > max_n:
                drop_ids = {id(it) for it in explain_items[max_n:]}
                kept = [it for it in kept if id(it) not in drop_ids]

        return kept

    def _llm_operationalize_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload = [
            {
                "question": it.get("question", ""),
                "source_ids": it.get("source_ids", []),
                "importance": it.get("importance", "standard"),
                "competency_category": it.get("competency_category", ""),
            }
            for it in items
        ]
        prompt = PROMPT_OPERATIONALIZE.format(
            items_json=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        try:
            result = call_llm_json(
                self.client,
                self.config.rubric_model,
                prompt,
                system="You rewrite literature-review rubric items for objective scoring. Output JSON array only.",
                temperature=0.2,
                max_retries=self.config.max_retries,
            )
            if isinstance(result, list) and len(result) == len(items):
                merged = []
                for orig, new in zip(items, result):
                    if not isinstance(new, dict):
                        merged.append(orig)
                        continue
                    merged.append({
                        **orig,
                        **{k: v for k, v in new.items() if k in (
                            "question", "source_ids", "importance",
                            "competency_category", "required_elements", "judgment_mode",
                        ) and v},
                    })
                return merged
        except Exception as e:
            logger.warning(f"  OCR LLM operationalize failed: {e}")
        return items

    # ─────────────────────────────────────────────────────────────────────
    #  Stage 3a: 维度特异性轻量校准
    # ─────────────────────────────────────────────────────────────────────

    def _light_calibrate(
        self, items: List[Dict[str, Any]], dimension_id: str,
        forbidden_terms: List[str] = None, all_dimension_items: Dict[str, List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        轻量校准：维度特异性规则检查，发现问题直接删除。
        
        科学调研版本的维度特异性规则：
        - IA: 使用 IA 弱动词列表 (mention/list/include/contain/have/cover/present/provide)
        - SR: 使用更严格的 SR 弱动词列表 (额外禁止 describe/state)
        - Synth: 跳过弱动词检查（允许结构性动词），强制所有项为 Standard
        """
        config = DIMENSION_CONFIG[dimension_id]
        min_count, max_count = config["item_range"]
        removed_reasons = {"chinese": 0, "vague": 0, "weak_verb": 0, "format": 0, "term": 0, "redundant": 0, "trim": 0, "synth_role_override": 0}

        # 收集其他维度的question用于冗余检查
        other_questions = []
        if all_dimension_items:
            for dim, dim_items in all_dimension_items.items():
                if dim != dimension_id:
                    for di in dim_items:
                        other_questions.append(di.get("question", "").lower())

        # 选择对应维度的弱动词列表
        if dimension_id == "scientific_reasoning":
            weak_verbs = WEAK_VERBS_SR
        elif dimension_id == "information_acquisition":
            weak_verbs = WEAK_VERBS_IA
        else:
            # Synth 维度不检查弱动词
            weak_verbs = []

        filtered = []
        for item in items:
            q = (item.get("question") or "").strip()
            q_lower = q.lower()

            # 1. 中文字符检查
            if re.search(r'[\u4e00-\u9fff]', q):
                removed_reasons["chinese"] += 1
                logger.debug(f"  Removed (Chinese): {q[:60]}...")
                continue

            # 2. 模糊词检查（SR 维度放宽：仅当模糊词是主要评价标准时才删除）
            if any(vw in q_lower for vw in VAGUE_WORDS):
                # SR 维度放宽：如果问题中包含具体分析要求（有 "analyze", "explain", "compare",
                # "evaluate", "derive", "demonstrate", "quantify" 等强动词），则保留
                has_strong_verb = any(
                    sv in q_lower for sv in
                    ["analyze", "explain", "compare", "evaluate", "derive",
                     "demonstrate", "quantify", "argue", "assess", "trace",
                     "contrast", "examine"]
                )
                if dimension_id == "scientific_reasoning" and has_strong_verb:
                    pass  # SR 有强动词时保留，即使含模糊词
                else:
                    removed_reasons["vague"] += 1
                    logger.debug(f"  Removed (vague word): {q[:60]}...")
                    continue

            # 3. 弱动词检查（Synth 维度跳过）
            if weak_verbs:
                verb = self._extract_first_verb(q)
                if verb and verb.lower() in weak_verbs:
                    removed_reasons["weak_verb"] += 1
                    logger.debug(f"  Removed (weak verb '{verb}'): {q[:60]}...")
                    continue

            # 4. 格式检查
            valid_prefixes = ("Does the report", "Is the", "Are the", "Can the", "Has the report")
            if not any(q.startswith(p) for p in valid_prefixes):
                removed_reasons["format"] += 1
                logger.debug(f"  Removed (format): {q[:60]}...")
                continue

            # 5. 论文特有术语检查（使用 LLM 过滤后的 forbidden_terms）
            # forbidden_terms 已在 Stage 1c 通过 LLM 过滤，移除了领域通用术语
            # 这里只检查真正的 paper-specific 术语是否被误用
            if forbidden_terms:
                found_term = False
                for term in forbidden_terms:
                    term_lower = term.lower()
                    # 跳过纯数字+单位的术语
                    if re.match(r'^[\d.]+[a-z]+$', term_lower):
                        continue
                    # 只过滤真正的论文特有标识符（camelCase 或全大写缩写）
                    if len(term) >= 4 and (
                        re.search(r'[a-z][A-Z]', term)           # camelCase
                        or re.match(r'^[A-Z]{4,}$', term)       # 全大写缩写
                        or re.search(r'[=<>]', term)            # 含赋值符号
                        or ('-' in term and any(c.isupper() for c in term))  # 连字符+大写
                    ):
                        if term_lower in q_lower:
                            removed_reasons["term"] += 1
                            logger.debug(f"  Removed (paper-specific term '{term}'): {q[:60]}...")
                            found_term = True
                            break
                if found_term:
                    continue

            # 6. 跨维度冗余检查
            if other_questions:
                core = q_lower
                for prefix in valid_prefixes:
                    if core.startswith(prefix.lower()):
                        core = core[len(prefix):].strip()
                        break
                is_redundant = False
                for other_q in other_questions:
                    other_core = other_q
                    for prefix in valid_prefixes:
                        if other_core.startswith(prefix.lower()):
                            other_core = other_core[len(prefix):].strip()
                            break
                    if len(core) > 20 and len(other_core) > 20:
                        core_words = set(re.findall(r'\b\w{4,}\b', core))
                        other_words = set(re.findall(r'\b\w{4,}\b', other_core))
                        if len(core_words) > 0 and len(other_words) > 0:
                            overlap = len(core_words & other_words) / min(len(core_words), len(other_words))
                            if overlap > 0.88:  # 88%以上的4字母以上词汇重叠才判定为冗余（提高阈值减少误删）
                                is_redundant = True
                                break
                if is_redundant:
                    removed_reasons["redundant"] += 1
                    logger.debug(f"  Removed (redundant across dimensions): {q[:60]}...")
                    continue

            # 7. Synth 维度角色约束：禁止 Critical，允许最多 2 个 Mandatory
            if dimension_id == "report_synthesis":
                imp = normalize_importance(item.get("importance", "standard"))
                if imp == "critical":
                    item["importance"] = "standard"
                    removed_reasons["synth_role_override"] += 1

            filtered.append(item)

        # 8. 维度比例检查 — 如果项数超出目标范围上限，从末尾删除多余项
        if len(filtered) > max_count:
            # 按优先级排序：先保留 critical，再 mandatory，再 standard
            role_order = {"critical": 0, "mandatory": 1, "standard": 2}
            filtered.sort(key=lambda x: role_order.get(normalize_importance(x.get("importance", "standard")), 3))
            excess = len(filtered) - max_count
            # 删除末尾的 standard 项
            filtered = filtered[:max_count]
            removed_reasons["trim"] = excess

        # 9. Synth 角色约束：Synth 全 Standard 设计，不做 Mandatory 提升
        # (保留代码但条件永假，方便未来需要时启用)
        if False and dimension_id == "report_synthesis":
            mand_count = sum(1 for it in filtered if normalize_importance(it.get("importance", "standard")) == "mandatory")
            if mand_count < 4:
                std_items = [it for it in filtered if normalize_importance(it.get("importance", "standard")) == "standard"]
                std_items.sort(key=lambda x: len(x.get("question", "")), reverse=True)
                for it in std_items[:4 - mand_count]:
                    it["importance"] = "mandatory"
                logger.info(f"  Synth: promoted {min(4 - mand_count, len(std_items))} Standard → Mandatory")

        # 10. SR/IA Critical 自动提升：当 Critical 低于目标的 80% 时，提升最高质量的 Mandatory 项
        if dimension_id in ("information_acquisition", "scientific_reasoning"):
            role_dist = config["role_dist"]
            target_critical = max(1, round(len(filtered) * role_dist["critical"]))
            current_critical = sum(1 for it in filtered if normalize_importance(it.get("importance", "standard")) == "critical")
            if current_critical < int(target_critical * 0.8):
                needed = target_critical - current_critical
                candidates = [
                    it for it in filtered
                    if normalize_importance(it.get("importance", "standard")) == "mandatory"
                ]
                candidates.sort(key=lambda x: len(x.get("question", "")), reverse=True)
                for it in candidates[:needed]:
                    it["importance"] = "critical"
                if needed > 0:
                    logger.info(f"  {dimension_id}: promoted {min(needed, len(candidates))} Mandatory → Critical")

        logger.info(
            f"  {dimension_id} calibration: {len(items)} -> {len(filtered)} items "
            f"(removed: chinese={removed_reasons['chinese']}, "
            f"vague={removed_reasons['vague']}, "
            f"weak_verb={removed_reasons['weak_verb']}, "
            f"format={removed_reasons['format']}, "
            f"term={removed_reasons['term']}, "
            f"redundant={removed_reasons['redundant']}, "
            f"synth_role_override={removed_reasons['synth_role_override']}, "
            f"trim={removed_reasons['trim']})"
        )

        return filtered

    def _llm_deduplicate(
        self, ia_items: List[Dict], sr_items: List[Dict],
        synth_items: List[Dict], query: str,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Stage 3b: LLM 去重 — 让 LLM 检查全部评分项，识别并删除重复/冗余项。
        只做删除（不修改），保留 keep 的项。
        """
        all_items = [
            {**it, "_dimension": "information_acquisition", "_idx": i}
            for i, it in enumerate(ia_items)
        ] + [
            {**it, "_dimension": "scientific_reasoning", "_idx": i}
            for i, it in enumerate(sr_items)
        ] + [
            {**it, "_dimension": "report_synthesis", "_idx": i}
            for i, it in enumerate(synth_items)
        ]

        if len(all_items) < 5:
            return ia_items, sr_items, synth_items

        items_text = "\n".join(
            f"[{it['_dimension']}#{it['_idx']}] (importance={it.get('importance','standard')}): {it['question']}"
            for it in all_items
        )

        prompt = PROMPT_DEDUPLICATE.format(
            query=query, total_count=len(all_items), items_text=items_text,
        )

        try:
            result = call_llm_json(
                self.client,
                self.config.rubric_model,
                prompt,
                system="You are a strict rubric quality evaluator. Output JSON only.",
                temperature=0.2,
                max_retries=2,
            )
            if not isinstance(result, dict) or "redundant_groups" not in result:
                return ia_items, sr_items, synth_items

            groups = result.get("redundant_groups", [])
            if not groups:
                logger.info("  LLM deduplication: no redundancies found")
                return ia_items, sr_items, synth_items

            # 收集需要删除的 (dimension, idx) 对
            remove_set = set()
            for g in groups:
                items_ref = g.get("items", [])
                remove_refs = g.get("remove", [])
                for ref in remove_refs:
                    remove_set.add(ref)
                logger.info(f"  Redundant: {items_ref} — {g.get('reason')}")

            # 解析删除引用 "[dimension_name#index]"
            import re
            remove_ia = set()
            remove_sr = set()
            remove_synth = set()
            for ref in remove_set:
                m = re.match(r'\[([a-z_]+)#(\d+)\]', str(ref))
                if m:
                    dim, idx = m.group(1), int(m.group(2))
                    if dim == "information_acquisition":
                        remove_ia.add(idx)
                    elif dim == "scientific_reasoning":
                        remove_sr.add(idx)
                    elif dim == "report_synthesis":
                        remove_synth.add(idx)

            ia_items = [it for i, it in enumerate(ia_items) if i not in remove_ia]
            sr_items = [it for i, it in enumerate(sr_items) if i not in remove_sr]
            synth_items = [it for i, it in enumerate(synth_items) if i not in remove_synth]

            # 保护机制：每个维度最多删除 20% 的项，防止过度去重
            max_remove_ia = max(1, len(ia_items) // 5)
            max_remove_sr = max(1, len(sr_items) // 5)
            max_remove_synth = max(1, len(synth_items) // 5)
            if len(remove_ia) > max_remove_ia:
                logger.info(f"  IA dedup cap: {len(remove_ia)} -> {max_remove_ia}")
                remove_ia = set(list(remove_ia)[:max_remove_ia])
            if len(remove_sr) > max_remove_sr:
                logger.info(f"  SR dedup cap: {len(remove_sr)} -> {max_remove_sr}")
                remove_sr = set(list(remove_sr)[:max_remove_sr])
            if len(remove_synth) > max_remove_synth:
                logger.info(f"  Synth dedup cap: {len(remove_synth)} -> {max_remove_synth}")
                remove_synth = set(list(remove_synth)[:max_remove_synth])

            ia_items_final = [it for i, it in enumerate(ia_items) if i not in remove_ia]
            sr_items_final = [it for i, it in enumerate(sr_items) if i not in remove_sr]
            synth_items_final = [it for i, it in enumerate(synth_items) if i not in remove_synth]

            logger.info(
                f"  LLM deduplication: removed {len(remove_set)} items "
                f"(IA: {len(ia_items_final)}, SR: {len(sr_items_final)}, Synth: {len(synth_items_final)})"
            )

            return ia_items_final, sr_items_final, synth_items_final

        except Exception as e:
            logger.warning(f"  LLM deduplication failed: {e}, skipping")

        return ia_items, sr_items, synth_items

    @staticmethod
    def _extract_first_verb(question: str) -> str:
        """
        从 "Does the report VERB ..." 格式中提取第一个动词。
        """
        # 去掉前缀 "Does the report " 或 "Is the report "
        for prefix in ("Does the report ", "Is the report ", "Are the report "):
            if question.startswith(prefix):
                rest = question[len(prefix):].strip()
                break
        else:
            # 尝试其他前缀
            for prefix in ("Does the ", "Is the ", "Are the ", "Can the ", "Has the report "):
                if question.startswith(prefix):
                    rest = question[len(prefix):].strip()
                    break
            else:
                return ""

        # 提取第一个单词作为动词
        match = re.match(r'^([a-zA-Z]+)', rest)
        if match:
            return match.group(1)
        return ""

    def _fill_synth_source_ids(
        self, synth_items: List[Dict], source_ids: List[str]
    ) -> List[Dict]:
        """
        Stage 3a+: 为 Synth 维度的评分项补全 source_ids。
        
        科学调研场景规则：通过 question 内容关键词匹配推断应关联的源文件。
        - 提到 literature/reference/citation/paper → 关联所有源
        - 提到 structure/section/taxonomy/table → 关联所有源
        - 提到 trend/timeline/chronological/recent → 关联所有源
        - 提到 future/research direction → 关联所有源
        - 其他纯格式项（heading style, abstract format）→ 保持空
        """
        if not source_ids:
            return synth_items

        # 科学调研专用的关键词分类
        lit_keywords = [
            "literature", "reference", "citation", "cite", "paper",
            "prior work", "source", "bibliography",
        ]
        struct_keywords = [
            "structure", "section", "taxonomy", "table", "comparison table",
            "classification", "hierarchy", "organiz", "layout",
        ]
        trend_keywords = [
            "trend", "timeline", "chronological", "recent",
            "latest", "development", "evolution", "progress",
        ]
        future_keywords = [
            "future", "research direction", "open problem",
            "open question", "challenge ahead",
        ]

        filled = 0
        for item in synth_items:
            existing = item.get("source_ids") or []
            if existing:
                continue  # 已有 source_ids 则跳过

            q = item.get("question", "").lower()
            new_ids = []

            if any(kw in q for kw in lit_keywords):
                new_ids = list(source_ids)
            elif any(kw in q for kw in struct_keywords):
                new_ids = list(source_ids)
            elif any(kw in q for kw in trend_keywords):
                new_ids = list(source_ids)
            elif any(kw in q for kw in future_keywords):
                new_ids = list(source_ids)

            if new_ids:
                item["source_ids"] = new_ids
                filled += 1

        if filled > 0:
            logger.info(f"  Synth source_ids filled: {filled}/{len(synth_items)} items")

        return synth_items

    # ─────────────────────────────────────────────────────────────────────
    #  组装最终输出
    # ─────────────────────────────────────────────────────────────────────

    def _assemble(
        self,
        query: str,
        task_type: str,
        sources: List[SourceDocument],
        ia_items: List[Dict[str, Any]],
        sr_items: List[Dict[str, Any]],
        synth_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """组装最终的评分表输出。"""
        all_items = []
        rid = 1

        dim_items = {
            "information_acquisition": ia_items,
            "scientific_reasoning": sr_items,
            "report_synthesis": synth_items,
        }

        for dim_id, items in dim_items.items():
            for item in items:
                q = normalize_question_text(item.get("question", ""))
                imp = normalize_importance(item.get("importance", "standard"))
                cat = item.get("competency_category") or infer_competency_category(q, dim_id)

                enriched = enrich_item_observability(item, dim_id)
                all_items.append({
                    "rubric_id": f"R{rid}",
                    "dimension_id": dim_id,
                    "question": q,
                    "source_ids": item.get("source_ids", []),
                    "importance": imp,
                    "competency_category": cat,
                    "rubric_key": build_rubric_key(dim_id, cat, q),
                    "weight": weight_from_importance(imp),
                    "judgment_mode": enriched.get("judgment_mode", "binary"),
                    "required_elements": enriched.get("required_elements", []),
                    "min_elements_full": enriched.get("min_elements_full", 1),
                    "min_elements_half": enriched.get("min_elements_half", 1),
                })
                rid += 1

        # 构建维度统计
        dimensions = []
        total_score = 0
        dimension_stats = {}

        for dim_id in ["information_acquisition", "scientific_reasoning", "report_synthesis"]:
            config = DIMENSION_CONFIG[dim_id]
            dim_items_list = [it for it in all_items if it["dimension_id"] == dim_id]
            max_score = sum(it["weight"] for it in dim_items_list)
            total_score += max_score

            roles = {"Critical": 0, "Mandatory": 0, "Standard": 0}
            for it in dim_items_list:
                role = role_from_importance(it["importance"])
                roles[role] = roles.get(role, 0) + 1

            source_linked = sum(1 for it in dim_items_list if it.get("source_ids"))
            multi_source = sum(1 for it in dim_items_list if len(it.get("source_ids", [])) >= 2)
            item_count = len(dim_items_list)

            dimension_stats[dim_id] = {
                "item_count": item_count,
                "max_score": max_score,
                "role_distribution": roles,
                "source_linked_ratio": source_linked / max(item_count, 1),
                "multi_source_ratio": multi_source / max(item_count, 1),
            }

            dimensions.append({
                "dimension_id": dim_id,
                "dimension_name": config["name"],
                "max_score": max_score,
                "items": [
                    {
                        "rubric_id": it["rubric_id"],
                        "rubric_key": it.get("rubric_key"),
                        "competency_category": it.get("competency_category"),
                        "role": role_from_importance(it["importance"]),
                        "weight": it["weight"],
                        "question": it["question"],
                        "source_ids": it["source_ids"],
                        "judgment_mode": it.get("judgment_mode", "binary"),
                        "required_elements": it.get("required_elements", []),
                        "min_elements_full": it.get("min_elements_full", 1),
                        "min_elements_half": it.get("min_elements_half", 1),
                    }
                    for it in dim_items_list
                ],
            })

        # 构建输入文件列表
        input_files = [
            {
                "file_id": s.source_id,
                "file_name": s.file_name,
                "relative_path": s.file_name,
                "file_type": s.file_type,
                "description": s.description,
            }
            for s in sources
            if s.file_type in ("csv", "md", "txt", "pdf")
        ]

        ocr_checklist = sum(
            1 for it in all_items if it.get("judgment_mode") == "checklist"
        )
        ocr_naked = sum(
            1 for it in all_items
            if is_naked_explain_define(it.get("question", ""), it.get("required_elements"))
        )

        return {
            "task_id": self.config.task_id or f"{task_type}_auto_v3",
            "task_type": task_type,
            "subject": self.config.subject,
            "document_heavy": len(sources) >= 5,
            "query": query,
            "input_files": input_files,
            "rubrics": {
                "total_score": total_score,
                "dimensions": dimensions,
            },
            "generation_meta": {
                "version": "3.0-litreview-ocr",
                "rubric_key_enabled": True,
                "capability_coverage_enabled": True,
                "ocr_enabled": True,
                "ocr_checklist_items": ocr_checklist,
                "ocr_naked_explain_remaining": ocr_naked,
                "dimension_stats": dimension_stats,
                "generation_model": self.config.rubric_model,
                "extraction_model": self.config.extract_model,
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    #  打印生成摘要
    # ─────────────────────────────────────────────────────────────────────

    def _print_generation_summary(self, result: Dict[str, Any]):
        """打印评分表生成摘要。"""
        rubrics = result.get("rubrics", {})
        dimensions = rubrics.get("dimensions", [])
        total = rubrics.get("total_score", 0)
        stats = result.get("generation_meta", {}).get("dimension_stats", {})

        logger.info(f"\n{'=' * 60}")
        logger.info("Rubric Generation Complete — Scientific Literature Review v3")
        logger.info(f"{'=' * 60}")
        logger.info(f"Total Score: {total}")

        for dim in dimensions:
            s = stats.get(dim["dimension_id"], {})
            roles = s.get("role_distribution", {})
            pct = f"{dim['max_score']/total*100:.0f}%" if total > 0 else "N/A"
            logger.info(
                f"  {dim['dimension_id']}: {dim['max_score']}pts, {pct} "
                f"({len(dim['items'])} items, "
                f"C={roles.get('Critical', 0)}, "
                f"M={roles.get('Mandatory', 0)}, "
                f"S={roles.get('Standard', 0)}, "
                f"src={s.get('source_linked_ratio', 0):.0%}, "
                f"multi={s.get('multi_source_ratio', 0):.0%})"
            )

        logger.info(f"{'=' * 60}")
