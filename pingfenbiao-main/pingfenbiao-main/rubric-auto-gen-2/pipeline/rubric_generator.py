"""
数据分析报告评分表生成核心模块。

基于 rubric_generator_v5 架构，全面重写为数据分析专用版本。

核心设计变更：
  - DIMENSION_CONFIG：IA 20%, SR 65%（28-38项）, Synth 15%
  - SR 维度引入主题前缀标签（Trend analysis, Factor analysis 等）
  - IA 侧重数据字段识别、参数提取、数据质量
  - Synth 侧重可视化、数据追溯、结论严谨性
  - 使用 LLM 过滤领域通用术语（替代硬编码白名单）
  - 放宽 SR 维度弱动词限制
  - 概念泛化 + LLM 术语过滤实现跨领域泛用性

流程（3阶段 + 去重）：
  Stage 1: 轻量知识提取（不泛化）
    1a. 解析 Query 子问题
    1b. 从每篇源文档提取关键知识点
    -- 跳过概念泛化 --
  Stage 2: 数据分析专用质量驱动生成
    IA: 数据字段识别 / 参数提取 / 数据质量
    SR: 主题前缀标签 / 高阶认知动词 / 数据证据
    Synth: 可视化 / 数据追溯 / 结论严谨性
  Stage 3: 轻量校准 + LLM 去重 + OCR 操作化
    3a. 规则检查（LLM 过滤后的 forbidden_terms + 弱动词对 SR 放宽 + 角色硬约束）
    3b. LLM 审核去重（20% 删除上限保护）
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
#  固定维度参数（数据分析专用）
# ═══════════════════════════════════════════════════════════════════════════

DIMENSION_CONFIG = {
    "information_acquisition": {
        "weight_pct": 0.20,
        "item_range": (10, 14),
        "name": "Information Acquisition",
        "role_dist": {"critical": 0.10, "mandatory": 0.55, "standard": 0.35},
    },
    "scientific_reasoning": {
        "weight_pct": 0.65,
        "item_range": (28, 38),  # 样例33项，目标上限38以补偿校准删除
        "name": "Scientific Reasoning",
        "role_dist": {"critical": 0.25, "mandatory": 0.50, "standard": 0.25},
    },
    "report_synthesis": {
        "weight_pct": 0.15,
        "item_range": (10, 14),
        "name": "Report Synthesis",
        "role_dist": {"critical": 0.0, "mandatory": 0.40, "standard": 0.60},
    },
}

# 源文档截断字符数
SOURCE_TEXT_MAX_CHARS = 15000

# LLM 生成参数
GENERATION_TEMPERATURE = 0.3
GENERATION_MAX_TOKENS = 16384

# 数据分析报告允许的 SR 维度弱动词（数据报告常用）
SR_ALLOWED_WEAK_VERBS = [
    "observe", "indicate", "note", "report", "state", "record",
    "measure", "document", "show",
]


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1a -- Query 子问题解析
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_PARSE_SUBQUESTIONS = """\
You are an expert at decomposing complex data analysis queries into verifiable sub-questions.

**Data Analysis Query**:
---
{query}
---

**Task**: Decompose this query into distinct, verifiable sub-questions.
Each sub-question should be a concrete analytical requirement that a data analysis report must address.

**Rules**:
1. Each sub-question must be specific and objectively answerable (Yes/No)
2. Preserve all numerical constraints, parameter ranges, and specific variables
3. Do not merge distinct requirements into one
4. Consider: data exploration, statistical testing, parameter sensitivity, convergence behavior, comparative analysis

Output as JSON array of strings, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1b -- 轻量知识提取（数据分析专用）
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_EXTRACT_KEY_POINTS = """\
You are a senior data analysis expert. Extract key data facts and analytical findings from the provided source document.

**Task Context**:
The user is writing a data analysis report to answer:
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

1. **category**: One of ["data_field", "parameter", "constraint", "finding", "methodology", "comparison", "anomaly"]
   - data_field: Column/field definitions, physical meanings, units, ranges
   - parameter: Algorithm configurations, hyperparameters, experimental settings
   - constraint: Variable constraints, boundary conditions, assumptions
   - finding: Key numerical results, statistical outcomes, convergence observations
   - methodology: Analysis methods, algorithms, evaluation metrics used
   - comparison: Comparative results between methods/configurations
   - anomaly: Missing values, outliers, data quality issues, unexpected patterns
2. **statement**: A complete, precise description of the data fact or finding. Use DOMAIN-GENERAL language rather than source-specific notation where possible (e.g., "the heterogeneity parameter alpha" rather than just "alpha=0.1").
3. **importance**: "critical" | "mandatory" | "standard"
   - critical = Core experimental result, primary conclusion, key parameter type
   - mandatory = Important data definition, method setting, key evidence
   - standard = Supplementary information, secondary statistics, background detail
4. **paper_specific_terms**: A list of source-specific terms, abbreviations, or notation that are unique to the specific source files and would NOT be understood by a general domain expert. These will be generalized later.
   Example: ["[METHOD_A]", "[THEOREM_3]", "[ABBREVIATION]"]
   If none, use an empty list [].

Output as JSON array directly, no other text.
"""


PROMPT_GENERALIZE_CONCEPTS = """\
You are an expert at abstracting specific data findings into domain-general concepts.

**Data Analysis Query**:
---
{query}
---

**Extracted Data Facts** (from all source documents):
{key_points_json}

**Task**: For each data fact, produce a "generalized_concept" that:
1. Captures the same underlying analytical principle or requirement
2. Uses domain-general terminology instead of source-specific names or abbreviations
3. Would be meaningful even if the reader has NOT read the specific source files
4. Retains enough specificity to be useful for generating evaluation criteria

**Examples of generalization**:
- "[SPECIFIC_VALUE] means extreme [PROPERTY]" -> "extreme [PROPERTY] settings where experimental units have highly skewed distributions"
- "[METHOD_A] uses [PARAM]=[VALUE] as [COMPONENT]" -> "the [COMPONENT] coefficient controls the degree of [BEHAVIOR] constraint"
- "[METRIC] fluctuates < [THRESHOLD] over [N] iterations" -> "[STABILIZATION_CRITERION] is identified when the primary evaluation metric stabilizes within a defined threshold over consecutive iterations"

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
   - Common optimization algorithms (Adam, SGD, RMSProp, etc.)
   - Standard neural network architectures (Transformer, LSTM, CNN, etc.)
   - Well-known techniques (fine-tuning, quantization, dropout, regularization, etc.)
   - Standard metrics (accuracy, F1, BLEU, perplexity, AUC, etc.)
   - Common datasets or benchmarks
   - Fundamental mathematical/statistical concepts (variance, gradient, convergence, etc.)
   - Widely-used abbreviations in the field
   - General analysis terms (sensitivity, robustness, convergence rate, etc.)

2. **Paper-specific (KEEP in forbidden list)**: Terms that are:
   - Novel method names coined by the authors
   - Specific theorem or equation references (e.g., "Theorem 3", "Eq. (7)")
   - Specific parameter settings tied to the paper's contribution (e.g., "epsilon=0.1")
   - Novel combinations of known techniques with a new name
   - Proper nouns referring to specific systems/models/datasets introduced in these papers

When uncertain, lean toward REMOVING the term (prefer keeping it as a usable concept).

**Output**: Return a JSON array containing ONLY the paper-specific terms that should remain in the forbidden list.

Output as JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Few-shot 示例（数据分析领域专用）
# ═══════════════════════════════════════════════════════════════════════════

FEWSHOT_IA = '''
GOOD items (domain-general, applicable to any data analysis report in the field):
- "Does the report identify the dataset characteristics, including the number of classes and the data distribution properties?"
- "Does the report state the method configuration parameters (e.g., learning rate, batch size, number of iterations) used in the experiments?"
- "Does the report indicate whether the dataset contains missing values, anomalies, or distribution skews?"
- "Does the report describe the valid ranges and physical constraints for key variables in the dataset?"
- "Does the report describe the evaluation metrics used to assess model performance?"
- "Does the report identify the data distribution characteristics (e.g., class imbalance ratio, feature skewness)?"
- "Does the report identify the hyperparameters explored during sensitivity analysis?"
- "Does the report distinguish between training data and evaluation data partitions?"

BAD items (NEVER do this -- these are source-specific or vague):
- "Does the report mention relevant data?" (vague, "relevant" is undefined)
- "Does the report state that alpha=0.1?" (source-specific, not generalizable)
- "Does the report describe the dataset?" (too vague, not judgeable)
- "Does the report include data analysis?" (trivially true for any data analysis report)
'''

FEWSHOT_SR = '''
GOOD items (domain-general, with topic prefix labels, demonstrating VERB DIVERSITY):

Trend analysis:
- "Trend analysis: Does the report identify the convergence/stabilization point based on appropriate criteria (e.g., metric fluctuation below a threshold over consecutive iterations)?"
- "Trend analysis: Does the report analyze why some configurations fail to converge before the maximum iterations?"
- "Trend analysis: Does the report demonstrate that the convergence speed differs across method configurations?"

Factor analysis:
- "Factor analysis: Does the report quantify the performance degradation as the key experimental factor increases, using appropriate comparison metrics?"
- "Factor analysis: Does the report explain why increasing factor X leads to higher variance among experimental units?"
- "Factor analysis: Does the report trace the causal chain from input factor changes to observed outcome differences?"

Method comparison:
- "Method comparison: Does the report compare the performance of different methods using consistent evaluation metrics?"
- "Method comparison: Does the report infer why one method outperforms another under specific experimental conditions?"

Statistical rigor:
- "Statistical rigor: Does the report apply appropriate statistical tests to validate the significance of observed differences?"
- "Statistical rigor: Does the report confirm that performance differences are not merely due to random variation?"

Error/Variance analysis:
- "Error/Variance analysis: Does the report decompose the total error into components (e.g., bias, variance, noise) and trace each to its source?"
- "Error/Variance analysis: Does the report derive the contribution of unit-level variance to the overall model error?"

Sensitivity analysis:
- "Sensitivity analysis: Does the report quantify how changes in key hyperparameters affect the final model performance?"
- "Sensitivity analysis: Does the report identify the parameter ranges where performance changes sharply (tipping points)?"

Data quality validation:
- "Data quality validation: Does the report verify that all metric values fall within physically valid ranges?"
- "Data quality validation: Does the report detect data quality issues (missing entries, out-of-range values, duplicate records)?"

Theoretical grounding:
- "Theoretical grounding: Does the report connect the empirical observation of performance degradation under extreme conditions to the underlying theoretical framework?"
- "Theoretical grounding: Does the report explain the mechanism behind why a particular method modification improves performance?"
- "Theoretical grounding: Does the report evaluate the performance under extreme scenarios and connect observations to theoretical predictions?"

BAD items (NEVER do this):
- "Does the report discuss relevant analysis?" (vague, undefined)
- "Trend analysis: Does the report show that [METHOD_A] converges at iteration 89?" (source-specific)
- "Does the report mention the results?" (weak verb, too vague)
- "Trend analysis: Does the report analyze the trend?" (vague, not judgeable)
'''

FEWSHOT_SYNTH = '''
GOOD items (from human-designed data analysis rubrics):
- "Does the report include line charts or trend plots showing the trajectory of key metrics over training iterations?"
- "Does the report include comparison bar charts or tables that clearly display performance differences across methods?"
- "Does the report ensure that every key numerical claim in the conclusions can be traced back to specific data points or figures in the analysis section?"
- "Does the report avoid over-generalization by explicitly stating the conditions under which its conclusions hold (e.g., 'for learning rates in [1e-5, 1e-3]')?"
- "Does the report acknowledge the limitations of the analysis (e.g., limited number of trials, specific dataset characteristics)?"
- "Does the report follow a logical structure: experimental setup -> data exploration -> performance comparison -> theoretical explanation -> conclusions?"
- "Does the report use correct domain terminology precisely and consistently?"
- "Does the report discuss the sensitivity of results to hyperparameter choices and identify the most influential parameters?"
- "Is each figure and table clearly labeled with a descriptive title, axis labels, units, and a legend where applicable?"
- "Does the report provide a summary table of all experimental configurations and their corresponding results?"

Challenging items (reports may NOT satisfy these -- this is expected and desired):
- "Does the report derive the theoretical convergence rate and compare it with the empirical convergence observed in the data?"
- "Does the report identify potential confounding variables that could explain the observed performance differences?"
- "Does the report discuss the computational cost (time, memory, communication) of each method in addition to accuracy?"

NEGATIVE PENALTY items (detect BAD behaviors -- give FULL score if report does NOT do the bad thing):
- "Does the report falsely claim convergence when the training loss has not actually stabilized?"
- "Does the report misattribute performance differences to method design when they are actually caused by different hyperparameter settings?"
- "Does the report report results as significant without performing any statistical test?"

BAD items:
- "Does the report have good structure?" (vague, not judgeable)
- "Does the report write well?" (subjective)
- "Does the report provide sufficient detail?" ("sufficient" undefined)
'''


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 2 -- 数据分析专用质量驱动生成 Prompt
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_GENERATE_IA = """\
You are an expert data analysis report evaluator. Generate high-quality rubric items for the **Information Acquisition (IA)** dimension.

## CORE PRINCIPLE
You are generating a DOMAIN-LEVEL QUALITY STANDARD for evaluating data analysis reports in this research domain. The source documents (literature, datasets, metadata) inform your understanding of what knowledge a good report in this domain should demonstrate — but the rubric items themselves must be GENERALIZABLE to any report in this domain, NOT tied to specific source files or specific experimental values.

Each item should evaluate: "Does a good data analysis report in this domain properly identify and describe the key data characteristics, evaluation metrics, and experimental parameters important to this field?"

## DATA ANALYSIS QUERY
---
{query}
---

## SUB-QUESTIONS the report must address:
{sub_questions}

## AVAILABLE SOURCES (knowledge references, NOT required citations)
{source_ids}

## GENERALIZED DOMAIN KNOWLEDGE
The following are domain concepts generalized from the source documents. Use these to understand what knowledge is important in this domain:
{generalized_points}

## FORBIDDEN TERMS (source-specific — do NOT use in rubric items)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_ia}

## GENERATION RULES

1. **DOMAIN-GENERAL, NOT SOURCE-SPECIFIC**: Each item must be applicable to ANY data analysis report in this domain. Do NOT require the report to cite specific source files or reproduce specific values from the input data.
   - BAD (source-specific): "Does the report identify that the dataset is [DATASET_NAME] with [PARAM]=[VALUE]?"
   - GOOD (domain-general): "Does the report identify the dataset characteristics, including the number of classes and the data distribution properties?"
   - BAD (source-specific): "Does the report state that the [COMPONENT] coefficient [PARAM] is [VALUE]?"
   - GOOD (domain-general): "Does the report identify the key method-specific hyperparameters and their configured values?"

2. **GENERALIZE SPECIFIC VALUES**: Reference parameter TYPES and RANGES, NOT specific values from the source data. Use domain-general descriptions.
   - Instead of "[PARAM]=[VALUE]", use "the [PARAM] and its impact on [PROPERTY]"
   - Instead of "[PARAM]=[VALUE]", use "the regularization coefficient and its effect on [BEHAVIOR]"
   - Instead of "[N] rounds", use "the total number of training iterations"

3. **source_ids SEMANTICS**: source_ids indicate which source documents informed this rubric item's design. Every IA item SHOULD have at least one source_id, indicating which source file a good report would consult for this information. Use [] (empty) only for items testing general domain knowledge not tied to any source file.

4. **COVERAGE REQUIREMENTS**: Generate items covering:
   - Dataset identification and data characteristics (2-3 items)
   - Experimental parameters and algorithm configurations (3-4 items)
   - Variable constraints and valid ranges (2-3 items)
   - Data quality awareness: missing values, anomalies, distribution checks (2-3 items)
   - Evaluation metrics and analysis methodology (2-3 items)

5. **COGNITIVE HIERARCHY — MANDATORY VERB DIVERSITY**: IA tests data concept acquisition at the remember/understand level. You MUST distribute verbs across the following categories (do NOT overuse any single verb — no verb should exceed 30% of items):

   **Category A — Identification (~30%)**: identify, recognize, pinpoint
     Tests: Finding specific data characteristics, parameters, metrics
     Example: "Does the report identify the primary evaluation metric and its valid range?"

   **Category B — Description (~25%)**: describe, state, indicate
     Tests: Explaining experimental setup, data characteristics
     Example: "Does the report describe the mechanism used to control [KEY_FACTOR]?"

   **Category C — Classification (~25%)**: distinguish, differentiate, classify, categorize
     Tests: Distinguishing between data types, method categories, parameter roles
     Example: "Does the report distinguish between training-dependent and training-independent experimental variables?"

   **Category D — Quality Awareness (~20%)**: check, verify, examine
     Tests: Awareness of data quality issues, constraints, anomalies
     Example: "Does the report examine the dataset for distribution skews or class imbalance?"

   **FORBIDDEN**: analyze, compare, evaluate, argue, derive — these belong to SR.
   **FORBIDDEN weak verbs**: mention, list, include, contain, have, cover, present, provide.

6. **NO TRIVIAL BACKGROUND**: Do NOT ask about general knowledge any researcher would know. Focus on domain-specific knowledge that a competent report MUST demonstrate.

7. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.

8. **START WITH "Does the report"**: All items must start with "Does the report".

9. **NO VAGUE WORDS**: Do not use words like "sufficient", "relevant", "comprehensive", "adequate", "proper", "appropriate" without concrete operational criteria.

10. **OBSERVABLE CHECKLIST (OCR) — MANDATORY for define/explain**:
   - NEVER bare "Does the report explain X?" or "Does the report define X?"
   - ALWAYS use ONE of: (a) "..., i.e., <single verifiable proposition>"; (b) "..., that <specific fact>"; (c) `required_elements` listing 2-4 checkable propositions
   - Provide `required_elements`: 2-4 short, independently checkable propositions (domain-general parameter/metric types, NOT paper-specific values).
   - Prefer `state that` / `identify that` / `describe that` over bare `explain` when testing data-field acquisition.

11. **NO OVER-GENERALIZED PHRASES**: Avoid vague placeholders like "a threshold", "key metrics", "specific conditions", "certain parameters". Instead, refer to the actual metric name, parameter name, or specific condition from the domain. BAD: "identify a threshold for convergence" → GOOD: "identify the convergence threshold (e.g., accuracy fluctuation below 0.2% over consecutive iterations)".

12. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items): Core data concepts essential for understanding the domain's analysis framework (e.g., primary evaluation metric definition, key experimental variables).
- Mandatory ({mandatory_target} items): Important data characteristics, parameter descriptions, quality checks that a competent report must cover.
- Standard ({standard_target} items): Supplementary data descriptions, secondary metrics, background statistics.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1"] or [] or ["S1","S2"], "importance": "critical|mandatory|standard", "competency_category": "definition|evidence|methodology|comparison", "required_elements": ["observable proposition A", "observable proposition B"], "judgment_mode": "binary|checklist"}}

Output JSON array only, no other text.
"""

PROMPT_OPERATIONALIZE = """\
You are an expert rubric engineer for **data analysis** reports. Rewrite rubric items so each is **objectively scorable** (no subjective "adequately explain").

## RULES
1. Replace bare explain/define with either:
   - "Does the report state that ..., i.e., <one verifiable fact>?" (judgment_mode: binary), OR
   - checklist with `required_elements` (2-4 propositions, judgment_mode: checklist)
2. required_elements: 2-4 short English propositions; each independently verifiable from report text.
3. Keep domain-general language; do NOT add paper-specific names/numbers from sources.
4. Preserve importance, source_ids, competency_category.
5. For SR items, **keep the topic prefix** (e.g., "Factor analysis: Does the report...").
6. Do NOT change items that already contain i.e./that/including checklist structure.

## ITEMS TO REWRITE
{items_json}

Output JSON array with same length and order. Each object:
{{"question": "...", "source_ids": [...], "importance": "...", "competency_category": "...", "required_elements": [...], "judgment_mode": "binary|checklist"}}

Output JSON only.
"""

PROMPT_GENERATE_SR = """\
You are an expert data analysis report evaluator. Generate high-quality rubric items for the **Scientific Reasoning (SR)** dimension.

## CORE PRINCIPLE
You are generating a DOMAIN-LEVEL QUALITY STANDARD that evaluates the analytical and reasoning capabilities expected of a high-quality data analysis report in this research domain. The source documents inform your understanding of what constitutes good analysis in this domain — but each rubric item must be GENERALIZABLE to any report in this domain, NOT tied to specific source data or specific experimental results.

Each item should evaluate: "Does a good data analysis report in this domain demonstrate the analytical capability to [analyze/quantify/compare/verify] [domain-relevant phenomenon]?"

This is the MOST IMPORTANT dimension (65% weight).

## DATA ANALYSIS QUERY
---
{query}
---

## SUB-QUESTIONS:
{sub_questions}

## AVAILABLE SOURCES (knowledge references, NOT required citations)
{source_ids}

## GENERALIZED DOMAIN KNOWLEDGE
{generalized_points}

## FORBIDDEN TERMS (source-specific — do NOT use in rubric items)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_sr}

## TOPIC PREFIX LABELS (MANDATORY)
Every SR item MUST begin with a topic prefix label followed by a colon. Use the following labels:

1. **Trend analysis** -- Issues related to: identifying convergence/stabilization points, tracking metric trajectories over time/iterations, detecting non-convergence or divergence phenomena, comparing convergence speed across configurations
2. **Factor analysis** -- Issues related to: quantifying the impact of key variables/factors on outcomes, tracing causal chains from input factors to observed effects, explaining why factor changes lead to performance shifts
3. **Method comparison** -- Issues related to: comparing performance of different methods/algorithms/configurations, advantage/disadvantage analysis, ranking justification under controlled conditions
4. **Statistical rigor** -- Issues related to: statistical method application, confidence levels, significance testing, p-values, confidence intervals, reproducibility of results
5. **Error/Variance analysis** -- Issues related to: error decomposition, variance analysis, outlier detection, residual analysis, bias-variance trade-offs
6. **Sensitivity analysis** -- Issues related to: parameter sensitivity, hyperparameter impact, robustness to configuration changes, identifying tipping points or critical thresholds
7. **Data quality validation** -- Issues related to: data completeness checks, physical constraint verification, consistency across sources, missing value handling, outlier treatment justification
8. **Theoretical grounding** -- Issues related to: connecting empirical findings to theoretical frameworks, verifying mathematical formulas or theoretical predictions, explaining mechanisms behind observed phenomena, extreme/boundary case analysis

## GENERATION RULES

1. **TOPIC PREFIX MANDATORY**: Every item MUST start with one of the 8 topic prefix labels above, followed by a colon and space. Example: "Convergence analysis: Does the report..."
   This is a HARD requirement. Items without a topic prefix will be rejected.

2. **DOMAIN-GENERAL ANALYSIS, NOT SOURCE-SPECIFIC**: Items must evaluate analytical CAPABILITIES, not whether the report reproduced specific findings from the input data.
   - BAD (source-specific): "Does the report show that accuracy drops from 90% to 45% under condition X?"
   - GOOD (domain-general): "Factor analysis: Does the report quantify the performance degradation as the key factor increases, using appropriate comparison metrics?"
   - BAD (source-specific): "Does the report identify that [METHOD_A] converges at iteration 89?"
   - GOOD (domain-general): "Trend analysis: Does the report identify the convergence/stabilization point based on appropriate criteria (e.g., fluctuation below threshold over consecutive iterations)?"

3. **GENERALIZE SPECIFIC VALUES**: Reference analysis METHODS and CAPABILITIES, NOT specific numerical results from the source data.
   - Instead of "accuracy of 93.52%", use "the final model accuracy"
   - Instead of "from iteration 89", use "the convergence point"
   - Instead of "[METHOD_A] vs [METHOD_B]", use "the compared methods" (unless these are the ONLY methods in the domain, in which case domain-general names are acceptable)

4. **COGNITIVE HIERARCHY — MANDATORY VERB DIVERSITY**: SR tests analytical reasoning for data analysis. You MUST distribute verbs across the following categories. Do NOT let any single verb exceed 20% of items.

   **Category A — Quantification & Demonstration (~20%)**: quantify, demonstrate, show
     Tests: Extracting precise numerical relationships from data, proving claims with evidence
     Example: "Factor analysis: Does the report quantify the performance degradation as the key factor increases?"

   **Category B — Mechanism Analysis (~20%)**: analyze why, analyze the mechanism, analyze how, explain why
     Tests: Root cause analysis, understanding WHY phenomena occur
     Example: "Trend analysis: Does the report analyze why some configurations fail to converge before the maximum iterations?"

   **Category C — Comparative Evaluation (~15%)**: compare, contrast, evaluate trade-offs
     Tests: Rigorous cross-configuration comparison with explicit criteria
     Example: "Method comparison: Does the report compare the methods' robustness across different conditions using consistent metrics?"

   **Category D — Data-Driven Inference (~15%)**: infer, derive, deduce, trace
     Tests: Drawing logical conclusions from observed data patterns
     Example: "Error/Variance analysis: Does the report trace the observed performance variance to its contributing factors?"

   **Category E — Verification & Validation (~15%)**: verify, validate, confirm, check
     Tests: Confirming expected patterns, validating claims against data
     Example: "Data integrity validation: Does the report verify that all metric values fall within physically valid ranges?"

   **Category F — Sensitivity & Robustness (~15%)**: assess sensitivity, identify tipping points, determine robustness
     Tests: Understanding parameter effects, boundary conditions
     Example: "Sensitivity analysis: Does the report identify the parameter ranges where performance changes sharply?"

   **IMPORTANT**: Before finalizing, count your verb distribution. If "analyze" appears in more than 25% of items, replace some with "quantify", "demonstrate", "verify", "trace", or "infer". Data analysis reports should demonstrate DATA EMPIRICISM — show me the data, not just "analyze" it.

   **DIMENSION BOUNDARY — DO NOT TEST**: mere concept definitions, parameter identification, or structural completeness. Those belong to IA and Synth.

5. **source_ids -- ASSOCIATE DATA SOURCES**: Each SR item should indicate which source documents provide the DATA or KNOWLEDGE basis for the analysis being tested. Use source_ids to show what type of data supports this evaluation:
   - Items testing analysis of experimental results (e.g., convergence, accuracy): use source_ids for the CSV data file.
   - Items testing understanding of experimental design or parameters: use source_ids for the metadata/config file.
   - Items testing understanding of variable definitions or constraints: use source_ids for the data dictionary file.
   - Items testing cross-document synthesis: use multiple source_ids.
   - Use [] (empty) ONLY for items testing purely general analytical skills not tied to any source.

6. **CRITICAL ITEMS (HARD REQUIREMENT)**: Generate exactly {critical_target} Critical items (importance="critical", 4 points each). Assign Critical to items testing the DEEPEST analytical reasoning — items that require the report to QUANTIFY, DERIVE, or PROVE key relationships from data. If you assign fewer than {critical_target} Critical items, the output WILL BE REJECTED.
   - Assign Critical to items that test: fundamental trend/factor analysis with quantification, key method mechanism derivation, core variable impact quantification, or critical data-driven inference with theoretical grounding.
   - Do NOT assign Critical to simple identification, description, or observation items.
   - Critical items should use strong verbs: quantify, derive, prove, demonstrate, trace, deduce.

7. **DERIVATION ITEMS REQUIRED**: At least 3 items must use verbs like "derive", "trace", "show that", "deduce" -- evaluating whether the report can perform causal or logical derivation from data.

8. **CROSS-SOURCE AWARENESS**: Items may reference multiple source_ids when the analysis capability being tested draws on knowledge from multiple sources. This is encouraged but NOT mandatory for every item.

9. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.

10. **NO VAGUE WORDS**: Do not use words like "sufficient", "relevant", "comprehensive", "adequate", "proper", "appropriate" without concrete operational criteria.

11. **OBSERVABLE CHECKLIST (OCR)**: Prefer quantify/compare/analyze over bare "explain". Any explain/define MUST include i.e./that/checklist OR `required_elements` (2-3 verifiable propositions). Mechanism items: separate condition P, mechanism M, outcome Q as elements. **Keep topic prefix** intact.

12. **NO CHINESE**: All items must be in English.

## TOPIC DISTRIBUTION GUIDELINES
Ensure items are distributed across the 8 topics. **These are HARD REQUIREMENTS, not suggestions:**
- Trend analysis: 4-5 items (REQUIRED)
- Factor analysis: 4-5 items (REQUIRED)
- Method comparison: 4-5 items (REQUIRED)
- Statistical rigor: 3-4 items (REQUIRED)
- Error/Variance analysis: 3-4 items (REQUIRED)
- Sensitivity analysis: 3-4 items (REQUIRED)
- Data quality validation: 3-4 items (REQUIRED)
- **Theoretical grounding: 4-5 items (MANDATORY — this topic connects empirical data to theory and is ESSENTIAL for a high-quality data analysis report. Generate items that test: mechanism explanation, formula/theoretical prediction verification, extreme/boundary case analysis, and connecting observations to theoretical frameworks. Missing this topic will cause the output to be REJECTED.)**
- Additional cross-topic items as needed to reach {target_count} total

## DATA-DRIVEN REASONING REQUIRED
At least 40% of SR items must directly evaluate whether the report uses DATA EVIDENCE to support its analytical claims. This means:
- Items should test whether the report QUANTIFIES findings (not just "analyzes" or "discusses")
- Items should test whether the report TRACES causal chains from data observations to conclusions
- Items should test whether the report VALIDATES claims against actual data points
- BAD (vague reasoning): "Does the report analyze the trend?"
- GOOD (data-driven): "Does the report quantify the convergence point based on metric fluctuation below a threshold over consecutive iterations?"

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items): Deepest analytical reasoning items that test fundamental understanding of key phenomena. Assign to items that QUANTIFY or DERIVE key relationships from data, not items that merely describe observations. Distribute across the most important topics, especially Theoretical grounding, Factor analysis, and Method comparison.
- Mandatory ({mandatory_target} items): Core analytical comparisons, important quantitative demonstrations, essential data-driven arguments.
- Standard ({standard_target} items): Supplementary observations, secondary comparisons, additional data checks.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "[Topic prefix]: Does the report...?", "source_ids": ["S1","S2"] or ["S1"] or [], "importance": "critical|mandatory|standard", "competency_category": "mechanism|comparison|limitation|synthesis", "required_elements": ["..."], "judgment_mode": "binary|checklist"}}

CRITICAL: The "question" field MUST start with one of the 8 topic prefix labels followed by ": ".
Output JSON array only, no other text.
"""

PROMPT_GENERATE_SYNTH = """\
You are an expert data analysis report evaluator. Generate high-quality rubric items for the **Report Synthesis (Synth)** dimension.

## CORE PRINCIPLE
You are generating a DOMAIN-LEVEL QUALITY STANDARD for the structure, clarity, and integrity of data analysis reports in this research domain. The rubric items must be GENERALIZABLE to any report in this domain, NOT tied to specific source documents or specific experimental results.

## DATA ANALYSIS QUERY
---
{query}
---

## SUB-QUESTIONS:
{sub_questions}

## AVAILABLE SOURCES
{source_ids}

## EXTRACTED DATA FACTS
{generalized_points}

## FORBIDDEN TERMS (source-specific — do NOT use in rubric items)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_synth}

## GENERATION RULES

1. **QUALITY-DRIVEN -- NOT CONTENT-DRIVEN**: You are evaluating whether the report is a WELL-WRITTEN DATA ANALYSIS REPORT, not whether it covered every data point. Do NOT ask whether the report "states" or "includes" a specific finding. Instead, evaluate visualization quality, traceability, logical structure, and claim precision.
   - IMPORTANT: Use DOMAIN-GENERAL descriptions in rubric items. Instead of specific method names (e.g., "FedAvg", "DoRA"), use general terms like "the baseline aggregation algorithm", "the compared methods", or "the parameter-efficient method". Instead of specific variable names (e.g., "Global_Accuracy"), use "the primary accuracy metric" or "the key performance metric".

1b. **VERB DIVERSITY — Structure + Evaluation**: Distribute verbs across:
   
   **Structural (~50%)**: include, provide, contain, present
     Tests: Presence of required elements (charts, tables, summaries)
   
   **Evaluative (~30%)**: demonstrate, maintain, ensure, assess
     Tests: Quality of structure, logical coherence, consistency
     Example: "Does the report demonstrate a logical progression from data exploration to performance comparison to conclusions?"
   
   **Critical (~20%)**: avoid, falsely claim, misattribute, over-generalize
     Tests: Negative penalty — detecting BAD analytical behaviors
     Example: "Does the report falsely claim convergence when the training loss has not actually stabilized?"

   **IMPORTANT**: At least 25% of Synth items must use evaluative verbs, not just structural verbs.
2. **VISUALIZATION QUALITY (at least 3 items required)**:
   - Check for appropriate chart types (line charts for trends, bar charts for comparisons, scatter plots for correlations)
   - Check that trend charts display key metrics (e.g., accuracy, loss) over training iterations
   - Check for method comparison visualizations
   - Check for proper labeling (axis labels, units, legends, titles)
   - Check that figures directly support the textual claims
3. **DATA TRACEABILITY**: Check that key numerical claims in the conclusions can be traced back to specific data points, tables, or figures in the analysis section.
4. **CONCLUSION RIGOR**: Check that the report avoids over-generalization, states conditions/limitations, and does not claim more than the data supports.
5. **NO CRITICAL ITEMS**: For data analysis Synth, set critical_target=0. The highest importance is Mandatory.
6. **LOGICAL STRUCTURE**: Check for a logical flow: experimental setup -> data exploration -> performance comparison -> theoretical explanation -> conclusions.
7. **DOMAIN TERMINOLOGY**: Check for correct and consistent use of domain terms.
8. **EXECUTIVE SUMMARY**: Check whether the report provides a concise summary of key findings at the beginning.
9. **REFERENCE CITATION**: Check whether the report properly cites relevant literature when discussing theoretical foundations or comparing with prior work.
10. **FUTURE DIRECTIONS**: Check whether the report identifies potential improvements or next steps based on the analysis.
11. **SENSITIVITY DISCUSSION**: Check whether the report discusses the robustness of findings to parameter changes.
9. **CHALLENGING ITEMS REQUIRED**: At least 1-2 items should evaluate aspects that a GOOD report may still NOT satisfy -- these create differentiation between adequate and excellent reports.
10. **NEGATIVE PENALTY ITEMS (2-3 required)**: These evaluate whether the report CORRECTLY AVOIDS bad behaviors. Give FULL score if the report does NOT do the bad thing.
    - FALSE CLAIMS: "Does the report falsely claim convergence when the training loss has not actually stabilized?"
    - MISATTRIBUTION: "Does the report attribute performance differences to method design when they are caused by different hyperparameter settings?"
    - UNSUPPORTED SIGNIFICANCE: "Does the report report results as significant without performing any statistical test?"
11. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.
12. **NO VAGUE WORDS**: Do not use words like "good", "well", "sufficient", "relevant", "comprehensive", "adequate" without concrete operational criteria.
13. **START WITH "Does the report"** (or "Is the" for grammar): Items should use these prefixes.
14. **source_ids**: Synth items evaluating data traceability or figure/table references should have source_ids. Items evaluating general structure, language, or logical flow may use [].
15. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items): NONE for data analysis Synth. Use Mandatory for the most important structural items.
- Mandatory ({mandatory_target} items, MIN 4): Visualization quality, data traceability, conclusion rigor, logical structure, negative penalty items. At least 4 Mandatory items are REQUIRED.
- Standard ({standard_target} items): Language quality, domain terminology, formatting details, sensitivity discussion.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1"] or [], "importance": "mandatory|standard", "competency_category": "structure|citation|visualization|language|recommendation|integrity"}}

Output JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 3b -- LLM 去重 Prompt
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_DEDUPLICATE = """\
You are an expert rubric evaluator. Review ALL rubric items below and identify redundant/duplicate items that test essentially the same thing.

**Data Analysis Query**:
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
      "reason": "Both check whether the report identifies the convergence metric",
      "keep": "[information_acquisition#0]",
      "remove": ["[scientific_reasoning#5]"]
    }}
  ]
}}

Rules:
1. Two items are redundant if they test essentially the same concept, even if worded differently.
2. If items test different aspects (e.g., one tests data identification, another tests convergence analysis), they are NOT redundant.
3. For each redundant group, specify which item to KEEP (prefer the clearer, more specific one).
4. If no redundancies exist, return {{"redundant_groups": []}}.
5. Only flag truly redundant items -- do NOT flag items that are complementary or test different facets.
6. Items with different topic prefixes in SR are generally NOT redundant (e.g., "Trend analysis: ..." and "Factor analysis: ..." test different things).

Output JSON only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 3a -- 轻量校准规则（数据分析专用修改）
# ═══════════════════════════════════════════════════════════════════════════

# 模糊词列表
VAGUE_WORDS = [
    "sufficient", "relevant", "comprehensive", "adequate", "proper",
    "appropriate", "good", "effective", "thorough", "detailed",
    "in-depth", "high-quality", "well-structured", "well-written",
    "properly", "effectively", "appropriately", "comprehensively",
    "adequately", "sufficiently", "relevantly",
]

# 弱动词列表（用于 IA 和 Synth 维度）
WEAK_VERBS_STRICT = [
    "mention", "list", "include", "contain", "have", "discuss",
    "cover", "present", "provide",
]


# ═══════════════════════════════════════════════════════════════════════════
#  主类 -- 数据分析评分表生成器
# ═══════════════════════════════════════════════════════════════════════════

class RubricGenerator:
    """数据分析报告评分表生成器。"""

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
    ) -> Dict[str, Any]:
        """主入口：3阶段生成评分表（数据分析专用）。"""
        logger.info("=" * 60)
        logger.info("Starting Data Analysis Rubric Generation")
        logger.info("=" * 60)

        source_ids = [s.source_id for s in sources]

        # ── Stage 1: 轻量知识提取 + 概念泛化 ──
        logger.info("\n[Stage 1a] Parsing query sub-questions...")
        sub_questions = self._parse_sub_questions(query)

        logger.info("\n[Stage 1b] Extracting key data facts from sources...")
        raw_key_points = self._extract_key_points(sources, query)

        # 数据分析任务也进行概念泛化，将特定参数泛化为领域通用概念
        logger.info("\n[Stage 1c] Generalizing source-specific terms to domain concepts...")
        generalized_points, forbidden_terms = self._generalize_concepts(raw_key_points, query)

        # ── Stage 2: 数据分析专用质量驱动生成 ──
        logger.info("\n[Stage 2] Generating rubric items (data analysis)...")

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
        )

        # ── Stage 3a: 轻量校准（数据分析专用：放宽 SR 弱动词） ──
        logger.info("\n[Stage 3a] Light calibration (data analysis mode)...")
        ia_items = self._light_calibrate(ia_items, "information_acquisition",
                                         forbidden_terms=forbidden_terms)
        sr_items = self._light_calibrate(sr_items, "scientific_reasoning",
                                          forbidden_terms=forbidden_terms,
                                          all_dimension_items={"information_acquisition": ia_items})
        synth_items = self._light_calibrate(synth_items, "report_synthesis",
                                             forbidden_terms=forbidden_terms,
                                             all_dimension_items={
                                                 "information_acquisition": ia_items,
                                                 "scientific_reasoning": sr_items,
                                             })

        # ── Stage 3a+: Synth source_ids 补全 ──
        # Synth 维度的 source_ids 覆盖率通常很低，通过关键词匹配补全
        synth_items = self._fill_synth_source_ids(synth_items, source_ids)

        # ── Stage 3b: LLM 去重 ──
        logger.info("\n[Stage 3b] LLM deduplication...")
        ia_items, sr_items, synth_items = self._llm_deduplicate(
            ia_items, sr_items, synth_items, query
        )

        # ── Stage 3c: Critical 后备提升（确保 SR 维度有足够 Critical 项） ──
        sr_config = DIMENSION_CONFIG["scientific_reasoning"]
        target_critical = max(1, round(sr_config["item_range"][1] * sr_config["role_dist"]["critical"]))
        current_critical = sum(1 for it in sr_items if normalize_importance(it.get("importance", "")) == "critical")
        if current_critical < target_critical:
            needed = target_critical - current_critical
            # 按 weight + question_length 排序，选出最高质量的非 Critical 项提升
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
        result = self._assemble(query, sources, ia_items, sr_items, synth_items)
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
                system="You are an expert at decomposing data analysis queries. Output JSON array only.",
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
    #  Stage 1b: 轻量知识提取（数据分析专用）
    # ─────────────────────────────────────────────────────────────────────

    def _extract_key_points(
        self, sources: List[SourceDocument], query: str
    ) -> List[Dict[str, Any]]:
        """从每篇源文档提取关键数据事实。返回所有文档的合并列表。"""
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
                        "You are a data analysis expert. "
                        "Extract key data facts. Output JSON array only."
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

        logger.info(f"  Total: {len(all_points)} data facts from {len(sources)} sources")
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

        # 提取所有源特有术语作为禁止列表
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
                    "You are an expert at abstracting specific data findings into "
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
    #  Stage 2: 数据分析专用质量驱动生成
    # ─────────────────────────────────────────────────────────────────────

    def _generate_dimension(
        self,
        dimension_id: str,
        query: str,
        sub_questions: List[str],
        generalized_points: List[Dict[str, Any]],
        forbidden_terms: List[str],
        sources: List[SourceDocument],
    ) -> List[Dict[str, Any]]:
        """生成单个维度的评分项。"""
        config = DIMENSION_CONFIG[dimension_id]
        # Use weighted upper bound (70% upper, 30% lower) to allow calibration removals
        # while still generating enough high-quality items
        target_count = int(config["item_range"][0] * 0.3 + config["item_range"][1] * 0.7)
        source_ids = [s.source_id for s in sources]

        # 计算 role 分布
        role_dist = config["role_dist"]
        c_target = max(0, round(target_count * role_dist["critical"]))
        m_target = max(2, round(target_count * role_dist["mandatory"]))
        s_target = max(1, target_count - c_target - m_target)

        # 格式化子问题
        sub_q_text = "\n".join(
            f"  {i+1}. {q}" for i, q in enumerate(sub_questions)
        ) if sub_questions else "  (No sub-questions parsed)"

        # 格式化知识点
        gen_summary = self._format_key_points(generalized_points)

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
            forbidden_terms=", ".join(forbidden_terms) if forbidden_terms else "[]",
            fewshot_ia=fewshot if dimension_id == "information_acquisition" else "",
            fewshot_sr=fewshot if dimension_id == "scientific_reasoning" else "",
            fewshot_synth=fewshot if dimension_id == "report_synthesis" else "",
            target_count=target_count,
            critical_target=c_target,
            mandatory_target=m_target,
            standard_target=s_target,
        )

        system = (
            "You are an expert data analysis rubric standards designer. "
            "Generate high-quality rubric items for evaluating data analysis reports. "
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

    def _format_key_points(
        self, points: List[Dict[str, Any]]
    ) -> str:
        """将知识点格式化为文本，用于传入生成 Prompt。"""
        parts = []
        for i, p in enumerate(points, 1):
            source = p.get("_source_id", "?")
            cat = p.get("category", "?")
            imp = p.get("importance", "standard")
            stmt = p.get("statement", "")
            parts.append(f"  {i}. [{cat}/{imp}] Source: {source}")
            parts.append(f"     Finding: {stmt}")
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
            # SR 维度允许主题前缀开头
            sr_topic_prefixes = (
                "Trend analysis", "Factor analysis",
                "Method comparison", "Statistical rigor",
                "Error/Variance analysis", "Sensitivity analysis",
                "Data quality validation", "Theoretical grounding",
            )
            if dim_id == "scientific_reasoning":
                if not any(q.startswith(p) for p in sr_topic_prefixes) and \
                   not any(q.startswith(p) for p in valid_prefixes):
                    if q and q[0].isupper():
                        q = f"Does the report {q[0].lower()}{q[1:]}"
                    else:
                        q = f"Does the report {q}"
            else:
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

            # Synth 维度强制不使用 critical（数据分析专用规则）
            if dim_id == "report_synthesis" and imp == "critical":
                imp = "mandatory"

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
            max_ratio = 0.35 if dimension_id == "information_acquisition" else 0.20
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
                system="You rewrite data-analysis rubric items for objective scoring. Output JSON array only.",
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
    #  Stage 3: 轻量校准（数据分析专用修改）
    # ─────────────────────────────────────────────────────────────────────

    def _light_calibrate(
        self, items: List[Dict[str, Any]], dimension_id: str,
        forbidden_terms: List[str] = None,
        all_dimension_items: Dict[str, List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        轻量校准：只做规则检查，发现问题直接删除该项。

        数据分析专用修改：
          - forbidden_terms 已在 Stage 1c 通过 LLM 过滤（移除领域通用术语）
          - 对 SR 维度放宽弱动词限制（允许 observe, indicate, note 等）
          - 保留其他检查：中文、模糊词、格式、冗余、比例
          - Synth 角色硬约束：Mandatory ≥ 4
          - SR/IA Critical 自动提升：当 Critical 低于目标 80% 时提升
        """
        config = DIMENSION_CONFIG[dimension_id]
        min_count, max_count = config["item_range"]
        removed_reasons = {
            "chinese": 0, "vague": 0, "weak_verb": 0,
            "format": 0, "term": 0, "redundant": 0, "trim": 0,
        }

        # 收集其他维度的question用于冗余检查
        other_questions = []
        if all_dimension_items:
            for dim, dim_items in all_dimension_items.items():
                if dim != dimension_id:
                    for di in dim_items:
                        other_questions.append(di.get("question", "").lower())

        filtered = []
        for item in items:
            q = (item.get("question") or "").strip()
            q_lower = q.lower()

            # 1. 中文字符检查（容忍模式：清除中文但保留英文内容）
            if re.search(r'[\u4e00-\u9fff]', q):
                # 清除所有中文字符（包括"报告是否"等前缀）
                cleaned_q = re.sub(r'[\u4e00-\u9fff]', '', q)
                # 清理多余空格和标点残留
                cleaned_q = re.sub(r'\s{2,}', ' ', cleaned_q).strip()
                cleaned_q = re.sub(r'^\s*[:：]\s*', '', cleaned_q)  # 移除开头的冒号残留
                cleaned_q = re.sub(r'^\s*[.。,，;；]\s*', '', cleaned_q)  # 移除开头的标点残留
                cleaned_q = cleaned_q.strip()
                if len(cleaned_q) > 20:  # 清除中文后仍有足够长度则保留
                    q = cleaned_q
                    item["question"] = cleaned_q
                    logger.debug(f"  Cleaned Chinese characters: {q[:60]}...")
                else:
                    removed_reasons["chinese"] += 1
                    logger.debug(f"  Removed (Chinese, too short after cleaning): {q[:60]}...")
                    continue

            # 2. 模糊词检查（保留）
            if any(vw in q_lower for vw in VAGUE_WORDS):
                removed_reasons["vague"] += 1
                logger.debug(f"  Removed (vague word): {q[:60]}...")
                continue

            # 3. 弱动词检查（数据分析专用修改）
            if dimension_id == "scientific_reasoning":
                # SR 维度：放宽弱动词限制，只过滤严格的弱动词
                # 但需要排除允许的数据分析常用动词
                verb = self._extract_first_verb(q)
                if verb and verb.lower() in WEAK_VERBS_STRICT:
                    if verb.lower() not in SR_ALLOWED_WEAK_VERBS:
                        removed_reasons["weak_verb"] += 1
                        logger.debug(f"  Removed (weak verb '{verb}' in SR): {q[:60]}...")
                        continue
                # 注意：SR 维度的主题前缀部分（如 "Trend analysis: "）不是动词，
                # 需要从 "Does the report..." 部分提取动词
            elif dimension_id != "report_synthesis":
                # IA 维度：使用严格弱动词列表
                verb = self._extract_first_verb(q)
                if verb and verb.lower() in WEAK_VERBS_STRICT:
                    removed_reasons["weak_verb"] += 1
                    logger.debug(f"  Removed (weak verb '{verb}'): {q[:60]}...")
                    continue

            # 4. 格式检查（保留）
            valid_prefixes = ("Does the report", "Is the", "Are the", "Can the", "Has the report")
            sr_topic_prefixes = (
                "Trend analysis", "Factor analysis",
                "Method comparison", "Statistical rigor",
                "Error/Variance analysis", "Sensitivity analysis",
                "Data quality validation", "Theoretical grounding",
            )
            has_valid_prefix = any(q.startswith(p) for p in valid_prefixes)
            has_topic_prefix = dimension_id == "scientific_reasoning" and any(q.startswith(p) for p in sr_topic_prefixes)
            if not has_valid_prefix and not has_topic_prefix:
                removed_reasons["format"] += 1
                logger.debug(f"  Removed (format): {q[:60]}...")
                continue

            # 5. 论文特有术语检查（使用 LLM 过滤后的 forbidden_terms）
            # forbidden_terms 已在 Stage 1c 通过 LLM 过滤，移除了领域通用术语
            # Synth 维度放宽术语过滤：只过滤 camelCase/全大写缩写（领域术语检查项需要使用领域名称）
            # IA/SR 维度也只过滤真正的论文特有标识符
            if forbidden_terms:
                found_term = False
                for term in forbidden_terms:
                    term_lower = term.lower()
                    # 跳过纯数字+单位的术语
                    if re.match(r'^[\d.]+[a-z]+$', term_lower):
                        continue
                    # 只过滤真正的论文特有标识符（camelCase 或全大写缩写）
                    if len(term) >= 4 and (
                        re.search(r'[a-z][A-Z]', term)           # camelCase: AdapterH, FedAvg
                        or re.match(r'^[A-Z]{4,}$', term)       # 全大写缩写: CIFAR, BERT
                        or re.search(r'[=<>]', term)            # 含赋值符号: mu=0.01
                        or ('-' in term and any(c.isupper() for c in term))  # 连字符+大写: CIFAR-10
                    ):
                        if term_lower in q_lower:
                            removed_reasons["term"] += 1
                            logger.debug(f"  Removed (term '{term}'): {q[:60]}...")
                            found_term = True
                            break
                if found_term:
                    continue

            # 6. 跨维度冗余检查（保留）
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

            filtered.append(item)

        # 7. 维度比例检查（保留）
        if len(filtered) > max_count:
            role_order = {"critical": 0, "mandatory": 1, "standard": 2}
            filtered.sort(key=lambda x: role_order.get(normalize_importance(x.get("importance", "standard")), 3))
            excess = len(filtered) - max_count
            filtered = filtered[:max_count]
            removed_reasons["trim"] = excess

        # 8. Synth 角色硬约束：Mandatory 不少于 4 项
        if dimension_id == "report_synthesis":
            mand_count = sum(1 for it in filtered if normalize_importance(it.get("importance", "standard")) == "mandatory")
            if mand_count < 4:
                # 将最高质量的 Standard 项提升为 Mandatory
                std_items = [it for it in filtered if normalize_importance(it.get("importance", "standard")) == "standard"]
                std_items.sort(key=lambda x: len(x.get("question", "")), reverse=True)
                for it in std_items[:4 - mand_count]:
                    it["importance"] = "mandatory"
                logger.info(f"  Synth: promoted {min(4 - mand_count, len(std_items))} Standard → Mandatory")

        # 9. SR/IA Critical 自动提升：当 Critical 低于目标的 80% 时，提升最高质量的 Mandatory 项
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
            f"trim={removed_reasons['trim']})"
        )

        return filtered

    def _fill_synth_source_ids(
        self, synth_items: List[Dict], source_ids: List[str]
    ) -> List[Dict]:
        """
        Stage 3a+: 为 Synth 维度的评分项补全 source_ids。
        
        规则：通过 question 内容关键词匹配推断应关联的源文件。
        - 提到 figure/table/chart/visualization/plot → 关联数据源 (CSV 通常)
        - 提到 data/numerical/claim/traceability → 关联所有源
        - 提到 reference/citation/literature → 关联论文源
        - 其他结构性条目 → 保持空
        """
        if not source_ids:
            return synth_items

        # 源文件分类（根据 file_id 无法确定类型，使用启发式）
        # source_ids 列表如 ["S1", "S2", "S3"]
        data_keywords = [
            "figure", "table", "chart", "visualization", "plot", "graph",
            "data point", "numerical", "trace", "traceability", "value",
            "metric", "accuracy", "loss", "result", "dataset"
        ]
        all_keywords = [
            "finding", "conclusion", "claim", "evidence", "support",
            "analysis", "experiment", "summary", "key"
        ]
        ref_keywords = [
            "reference", "citation", "literature", "cite", "prior work",
            "theoretical", "foundation"
        ]

        filled = 0
        for item in synth_items:
            existing = item.get("source_ids") or []
            if existing:
                continue  # 已有 source_ids 则跳过

            q = item.get("question", "").lower()
            new_ids = []

            if any(kw in q for kw in data_keywords):
                # 数据相关：关联所有数据源
                new_ids = list(source_ids)
            elif any(kw in q for kw in all_keywords):
                # 分析相关：关联所有源
                new_ids = list(source_ids)
            elif any(kw in q for kw in ref_keywords):
                # 参考文献相关：关联论文源（通常 S1, S2 为论文）
                # 关联第一个和第二个源（排除 CSV）
                new_ids = source_ids[:min(2, len(source_ids))]
            
            if new_ids:
                item["source_ids"] = new_ids
                filled += 1

        if filled > 0:
            logger.info(f"  Synth source_ids filled: {filled}/{len(synth_items)} items")

        return synth_items

    def _llm_deduplicate(
        self, ia_items: List[Dict], sr_items: List[Dict],
        synth_items: List[Dict], query: str,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Stage 3b: LLM 去重。
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

            remove_set = set()
            for g in groups:
                items_ref = g.get("items", [])
                remove_refs = g.get("remove", [])
                for ref in remove_refs:
                    remove_set.add(ref)
                logger.info(f"  Redundant: {items_ref} -- {g.get('reason')}")

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

            ia_items = [it for i, it in enumerate(ia_items) if i not in remove_ia]
            sr_items = [it for i, it in enumerate(sr_items) if i not in remove_sr]
            synth_items = [it for i, it in enumerate(synth_items) if i not in remove_synth]

            logger.info(
                f"  LLM deduplication: removed {len(remove_set)} items "
                f"(IA: {len(ia_items)}, SR: {len(sr_items)}, Synth: {len(synth_items)})"
            )

        except Exception as e:
            logger.warning(f"  LLM deduplication failed: {e}, skipping")

        return ia_items, sr_items, synth_items

    @staticmethod
    def _extract_first_verb(question: str) -> str:
        """
        从 "Does the report VERB ..." 或 "Topic prefix: Does the report VERB ..." 格式中
        提取第一个动词。
        """
        # 先去掉主题前缀（SR 维度）
        q = question
        sr_prefixes = (
            "Trend analysis: ", "Factor analysis: ",
            "Method comparison: ", "Statistical rigor: ",
            "Error/Variance analysis: ", "Sensitivity analysis: ",
            "Data quality validation: ", "Theoretical grounding: ",
        )
        for prefix in sr_prefixes:
            if q.startswith(prefix):
                q = q[len(prefix):].strip()
                break

        # 去掉 "Does the report " 或 "Is the report "
        for prefix in ("Does the report ", "Is the report ", "Are the report "):
            if q.startswith(prefix):
                rest = q[len(prefix):].strip()
                break
        else:
            for prefix in ("Does the ", "Is the ", "Are the ", "Can the ", "Has the report "):
                if q.startswith(prefix):
                    rest = q[len(prefix):].strip()
                    break
            else:
                return ""

        # 提取第一个单词作为动词
        match = re.match(r'^([a-zA-Z]+)', rest)
        if match:
            return match.group(1)
        return ""

    # ─────────────────────────────────────────────────────────────────────
    #  组装最终输出
    # ─────────────────────────────────────────────────────────────────────

    def _assemble(
        self,
        query: str,
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
            "task_id": self.config.task_id or "data_analysis_auto_v1",
            "task_type": "data_analysis",
            "subject": self.config.subject,
            "document_heavy": len(sources) >= 5,
            "query": query,
            "input_files": input_files,
            "rubrics": {
                "total_score": total_score,
                "dimensions": dimensions,
            },
            "generation_meta": {
                "version": "da-v1-ocr",
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
        logger.info("Data Analysis Rubric Generation Complete")
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
