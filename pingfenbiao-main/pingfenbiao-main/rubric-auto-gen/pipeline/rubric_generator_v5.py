"""
评分表生成核心模块 v5 — 轻量化、高质量、泛用性。

v5 核心设计原则：
  - 概念泛化：将论文特有术语转换为领域通用概念，保证评分项可迁移
  - 质量驱动：评估"报告是否是好的学术报告"，而非"是否复述了源文档"
  - 轻量校准：发现问题直接删项，不尝试修复（避免修复残留问题）

v5 流程（3阶段 + 去重）：
  Stage 1: 轻量知识提取 + 概念泛化
    1a. 解析 Query 子问题（保留 v4 的 Stage 0 逻辑）
    1b. 从每篇源文档提取关键知识点（简化版 v4 提取）
    1c. 概念泛化：将论文特有术语转换为领域通用概念
  Stage 2: 质量驱动生成
    使用模仿人工样例评分表风格的 Prompt 生成三个维度的评分项
  Stage 3: 轻量校准 + LLM 去重
    3a. 规则检查，发现问题直接删除该项（不调用 LLM）
    3b. LLM 审核去重：让 LLM 检查全部评分项，识别并删除重复/冗余项
"""

from __future__ import annotations

import json
import logging
import re
import sys
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
    item_aligns_with_query,
    is_survey_style_query,
    normalize_importance,
    role_from_importance,
    weight_from_importance,
    normalize_question_text,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  固定维度参数（v5 不做自适应，使用固定化比例）
# ═══════════════════════════════════════════════════════════════════════════

DIMENSION_CONFIG = {
    "information_acquisition": {
        "weight_pct": 0.25,
        "item_range": (15, 19),
        "name": "Information Acquisition",
        "role_dist": {"critical": 0.20, "mandatory": 0.55, "standard": 0.25},
    },
    "scientific_reasoning": {
        "weight_pct": 0.60,
        "item_range": (23, 30),
        "name": "Scientific Reasoning",
        "role_dist": {"critical": 0.30, "mandatory": 0.50, "standard": 0.20},
    },
    "report_synthesis": {
        "weight_pct": 0.15,
        "item_range": (10, 14),
        "name": "Report Synthesis",
        "role_dist": {"critical": 0.20, "mandatory": 0.55, "standard": 0.25},
    },
}

# 主张核查专用维度参数（对齐人工样例结构，质量优先于项数）
CLAIM_VERIFICATION_DIMENSION_CONFIG = {
    "information_acquisition": {
        "weight_pct": 0.26,
        "item_range": (12, 16),
        "name": "Information Acquisition",
        "role_dist": {"critical": 0.20, "mandatory": 0.50, "standard": 0.30},
    },
    "scientific_reasoning": {
        "weight_pct": 0.625,
        "item_range": (20, 28),
        "name": "Scientific Reasoning",
        "role_dist": {"critical": 0.35, "mandatory": 0.45, "standard": 0.20},
    },
    "report_synthesis": {
        "weight_pct": 0.115,
        "item_range": (8, 11),
        "name": "Report Synthesis",
        "role_dist": {"critical": 0.0, "mandatory": 0.40, "standard": 0.60},
    },
}


def get_dimension_config(task_type: str = "claim_verification") -> Dict[str, Dict]:
    """按任务类型返回维度配置。"""
    if task_type == "claim_verification":
        return CLAIM_VERIFICATION_DIMENSION_CONFIG
    return DIMENSION_CONFIG

# 源文档截断字符数
SOURCE_TEXT_MAX_CHARS = 15000

# LLM 生成参数
GENERATION_TEMPERATURE = 0.3
GENERATION_MAX_TOKENS = 8192

# 主张核查：SR 维度允许的补充动词（样例中 discuss/point out 用于机制识别）
SR_ALLOWED_EXTRA_VERBS = {"discuss", "point", "conclude", "refute", "distinguish"}

# 答案泄露检测模式
ANSWER_LEAK_PATTERNS = [
    r"\bwhy .+ (fail|fails|cannot|breaks down)\b",
    r"\bfundamentally fail",
    r"\bproven that\b",
    r"\bguaranteed\b",
    r"\brefutes the claim\b",
    r"\bonly holds under\b",
    r"\bcannot work\b",
    r"\bcomplete defense\b",
    r"\bscientifically refute\b",
    r"\bthereby undermining\b",
    r"\bby arguing that .+ undermin",
    r"\bfail completely against\b",
]

# Synth 负向陷阱表述（正向评估哲学，与样例一致）
NEGATIVE_SYNTH_PATTERNS = [
    r"\bomit\b", r"\bfail to\b", r"\bdoes not\b", r"\bmisattribute\b",
    r"\bcontradict\b", r"\boverclaim\b", r"\bwithout mentioning\b",
    r"\bincorrectly attribute\b",
]

# 主张核查 Synth 必备结构项（若 LLM 未生成则注入）
MANDATORY_SYNTH_TEMPLATES = [
    {
        "question": "Does the report include a structured evidence table clearly categorizing supporting, refuting, and neutral evidence?",
        "importance": "mandatory",
        "source_ids": [],
        "competency_category": "structure",
        "match_keywords": ["evidence table", "supporting", "refuting"],
    },
    {
        "question": "Is the verdict clearly stated with justification?",
        "importance": "mandatory",
        "source_ids": [],
        "competency_category": "structure",
        "match_keywords": ["verdict", "justification"],
    },
    {
        "question": "Does the report map each piece of evidence to specific sub-propositions of the claim?",
        "importance": "mandatory",
        "source_ids": [],
        "competency_category": "structure",
        "match_keywords": ["sub-proposition", "map each"],
    },
    {
        "question": "Does the report evaluate the logical self-consistency of the evidence presented across different sources?",
        "importance": "standard",
        "source_ids": [],
        "competency_category": "structure",
        "match_keywords": ["logical self-consistency", "self-consistency"],
    },
    {
        "question": "Does the report use precise hedging language and avoid unsupported superlatives (e.g., 'proven', 'guaranteed') when discussing research findings?",
        "importance": "mandatory",
        "source_ids": [],
        "competency_category": "integrity",
        "match_keywords": ["hedging", "superlative"],
    },
]

CLAIM_FOCUS_KEYWORDS = (
    "claim", "verdict", "evidence", "sub-proposition", "assertion",
    "refut", "support the claim", "validity of the claim", "over-absolut",
)

# SR claim-focused 保底项（query 中立；禁止硬编码其他任务域的脏模板）
CLAIM_SR_TEMPLATES = [
    {
        "question": "Does the report evaluate whether the central claim or thesis remains valid under the boundary conditions and assumptions discussed in the reviewed literature?",
        "importance": "critical",
        "match_keywords": ["central claim", "boundary conditions"],
    },
    {
        "question": "Does the report reconcile conflicting evidence across sources regarding the main claim or conclusion?",
        "importance": "critical",
        "match_keywords": ["reconcile conflicting", "main claim"],
    },
    {
        "question": "Does the report argue that absolute or unconditional claims overstate what the reviewed evidence actually demonstrates?",
        "importance": "critical",
        "match_keywords": ["absolute", "overstate"],
    },
    {
        "question": "Does the report evaluate whether the empirical evidence supports generalizing the main claim beyond the specific experimental settings studied?",
        "importance": "mandatory",
        "match_keywords": ["generalizing", "experimental settings"],
    },
    {
        "question": "Does the report assess limitations and scope conditions under which the main claim may not hold?",
        "importance": "mandatory",
        "match_keywords": ["scope conditions", "limitations"],
    },
]


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
Each sub-question should be a concrete requirement that a report must address.

**Rules**:
1. Each sub-question must be specific and objectively answerable (Yes/No)
2. Preserve all numerical constraints, time ranges, and specific entities
3. Do not merge distinct requirements into one
4. Numbered lists in the query often indicate separate sub-questions

Output as JSON array of strings, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1b — 轻量知识提取（简化版，无 vulnerability_chain / boundary_condition
#              / assumption_weakness）
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_EXTRACT_KEY_POINTS = """\
You are a senior academic analysis expert. Extract key knowledge points from the provided document.

**Task Context**:
The user is writing a research report to answer:
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
   - critical = Core innovation, key experimental conclusion, central claim
   - mandatory = Important definition, method description, key evidence
   - standard = Supplementary information, background context
4. **paper_specific_terms**: A list of paper-specific terms, method names, abbreviations, or
   theorem references used in the statement that are unique to this paper and would NOT be
   understood by a general domain expert without reading this specific paper.
   Example: ["[METHOD_NAME]", "Theorem 3", "[TECHNIQUE]"]
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

**Examples of generalization**:
- "[METHOD_A] adds noise to [COMPONENT]" -> "[PROTECTION_MECHANISM] can be applied at different levels of the [PIPELINE]"
- "[ATTACK_NAME] exploits [STATISTIC]" -> "adaptive attacks can exploit knowledge of defense parameters and gradient statistics"
- "[DEFENSE_NAME] uses [DETECTION_APPROACH]" -> "certain detection mechanisms may become ineffective under specific attack strategies"

**Output Format**: Return the same JSON array but with an additional "generalized_concept" field
added to each element. Preserve all original fields.

Output as JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 1c 补充 — 领域通用术语过滤
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_FILTER_DOMAIN_TERMS = """\
Given the following research context and a list of extracted terms, determine which terms are **domain-general** (well-known to any expert in the broader field) and which are **paper-specific** (unique to the specific papers being analyzed).

**Research Question**:
{query}

**Extracted Terms**:
{terms_list}

**Classification Rules**:
1. **Domain-general (REMOVE from forbidden list)**: Terms that any PhD student in the broader research area would recognize without reading these specific papers. This includes:
   - Common optimization algorithms (Adam, SGD, etc.)
   - Standard neural network architectures (Transformer, LSTM, etc.)
   - Well-known techniques (fine-tuning, quantization, dropout, etc.)
   - Standard metrics (BLEU, perplexity, accuracy, etc.)
   - Common datasets or benchmarks (MNIST, GLUE, ImageNet, etc.)
   - Fundamental mathematical/statistical concepts
   - Widely-used abbreviations in the field

2. **Paper-specific (KEEP in forbidden list)**: Terms that are:
   - Novel method names coined by the authors (e.g., "DP-BREM", "Attack-DPFL", "DoRA")
   - Specific theorem or equation references (e.g., "Theorem 3", "Eq. (7)")
   - Specific parameter settings tied to the paper's contribution (e.g., "ε=0.1")
   - Novel combinations of known techniques with a new name
   - Proper nouns referring to specific systems/models/datasets introduced in these papers

When uncertain, lean toward REMOVING the term (prefer keeping it as a usable concept).

**Output**: Return a JSON array containing ONLY the paper-specific terms that should remain in the forbidden list.

Output as JSON array only, no other text.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Few-shot 示例（从样例评分表提取）
# ═══════════════════════════════════════════════════════════════════════════

FEWSHOT_IA = '''
GOOD items (from human-designed rubrics):
- "Does the report explicitly define the key formal concept (e.g., [FORMAL_CONCEPT]) and explain how it is typically implemented in practice?"
- "Does the report explain the definition of [DATA_CHARACTERISTIC], i.e., that [DEFINITION_DETAIL]?"
- "Does the report point out the [NOTABLE_PROPERTY] of [TARGET_PHENOMENON] when [CONDITION] remains unchanged?"
- "Does the report distinguish between [CONCEPT_A] and [CONCEPT_B]?"
- "Does the report cite the description of [DEFENSE_MECHANISM] as a protective approach?"
- "Does the report compare [METHOD_A] and [METHOD_B] in terms of [EVALUATION_CRITERION]?"
- "Does the report quantify the [METRIC] (e.g., specific threshold, percentage, or count) reported in the studies?"

Challenging items (reports may NOT satisfy these — this is expected and desired):
- "Does the report identify the conditions under which [METHOD] fails or performs worse than [BASELINE]?"
- "Does the report evaluate whether the experimental settings in the reviewed studies are realistic enough to support generalization to real-world deployment?"

BAD items (NEVER do this):
- "Does the report describe the [METHOD_NAME] mechanism..." (uses paper-specific method name)
- "Does the report mention relevant concepts?" (vague, "relevant" is undefined)
- "Does the report provide sufficient background?" ("sufficient" is subjective)
'''

FEWSHOT_SR = '''
GOOD items (from human-designed rubrics):
- "Does the report analyze why [DATA_CHARACTERISTIC] reduces the ability of traditional [DETECTION_METHOD] to detect [TARGET_PHENOMENON]?"
- "Does the report explain the statistical similarity between [NOISE_SOURCE] and [PERTURBATION_TYPE], making them difficult to distinguish?"
- "Does the report derive the boundary impact of [FACTOR] on the validity of the claim?"
- "Does the report compare the vulnerability differences between [METHOD_A] and [METHOD_B] under [CONDITION]?"
- "Does the report argue that 'complete [DESIRED_OUTCOME]' is a strong assumption and the literature more often mentions 'mitigation'?"
- "Does the report evaluate the trade-off between [METRIC_A] and [METRIC_B] across different [APPROACHES]?"
- "Does the report reconcile conflicting findings between [SOURCE_A] and [SOURCE_B] regarding [TOPIC]?"

Challenging items (reports may NOT satisfy these — this is expected and desired):
- "Does the report challenge the assumption that [METHOD] guarantees [PROPERTY] under all conditions?"
- "Does the report identify counter-evidence or limitations that weaken the claim about [TOPIC]?"
- "Does the report synthesize evidence from multiple sources to argue that the claim only holds under [LIMITED_SCOPE]?"
- "Does the report scientifically refute the claim of [DESIRED_OUTCOME] by demonstrating [COUNTER_EVIDENCE]?"
- "Does the report argue that [KEY_TERM] is a strong assumption and the literature more often mentions [ALTERNATIVE_TERM]?"
- "Does the report conclude that there is currently no evidence supporting [CORE_CLAIM]?"
- "Does the report analyze how [ATTACKER] designs evasion strategies when they know [DEFENSE_PARAMETERS]?"

BAD items (NEVER do this):
- "Does the report analyze the vulnerability chain from S1: [SPECIFIC_CHAIN]..." (specific chain from one paper)
- "Does the report derive boundary conditions of [METHOD_NAME] ([SPECIFIC_CASE])..." (paper-specific conditions)
- "Does the report evaluate assumption weaknesses of Theorem 3..." (paper-specific theorem)
- "Does the report discuss relevant limitations?" (vague, undefined)
'''

FEWSHOT_SYNTH = '''
GOOD items (from human-designed rubrics):
- "Does the report include a structured evidence table clearly categorizing supporting, refuting, and neutral evidence?"
- "Is the verdict clearly stated with justification?"
- "Does the report use professional academic language without colloquial expressions or unsupported superlatives?"
- "Does the report provide a final confidence score or uncertainty quantification for the verdict?"
- "Does the report indicate future research directions?"
- "Does the report explicitly point out the over-absolutization of terms in the claim?"
- "Does the report map each piece of evidence to specific sub-propositions of the claim?"
- "Does the report clearly label the source of each evidence entry in the evidence table?"
- "Does the report evaluate the logical self-consistency of the evidence presented across different sources?"
- "Does the report discuss whether the datasets used in the reviewed studies are sufficiently diverse to support the claim?"

Challenging items (reports may NOT satisfy these — this is expected and desired):
- "Does the report derive the conditions under which [APPROACH] would fail completely rather than partially?"
- "Does the report identify implicit assumptions in the claim that are not explicitly stated in any of the reviewed sources?"
- "Does the report evaluate whether the experimental settings in the reviewed studies are realistic enough to support generalization to real-world deployment?"
- "Does the report discuss the limitations of [ANALYSIS_METHOD] in [SYSTEM_TYPE] due to [INTERFERENCE_FACTOR]?"
- "Does the report identify novel [THREAT_VECTOR] not covered in the reviewed literature?"

INTEGRITY & ACCURACY items (evaluate GOOD behaviors — give FULL score if report does this well):
- "Does the report accurately represent the strength of evidence, avoiding over-absolute claims (e.g., 'proven', 'guaranteed') when sources only show partial or conditional results?"
- "Does the report correctly attribute findings to their original sources, without conflating results across different studies or conditions?"
- "Does the report use precise hedging language when discussing findings that have limited scope or are context-dependent?"

BAD items:
- "Does the report have good structure?" (vague, not judgeable)
- "Does the report write well?" (subjective)
- "Does the report provide sufficient detail?" ("sufficient" undefined)
- "Does the report state the findings from source S1?" (content-driven, not quality-driven)
'''


# ═══════════════════════════════════════════════════════════════════════════
#  Stage 2 — 质量驱动生成 Prompt
# ═══════════════════════════════════════════════════════════════════════════

PROMPT_GENERATE_IA = """\
You are an expert scientific report evaluator. Generate high-quality rubric items for the **Information Acquisition (IA)** dimension.

## CORE PRINCIPLE
You are evaluating whether the report has acquired NECESSARY domain knowledge — NOT whether it
reproduced specific content from any particular source paper. Use domain-general concepts.

## RESEARCH QUESTION
---
{query}
---

## SUB-QUESTIONS the report must address:
{sub_questions}

## AVAILABLE SOURCES
{source_ids}

## GENERALIZED KNOWLEDGE POINTS
The following are key concepts (already generalized from source documents) that a good report should cover:
{generalized_points}

## FORBIDDEN TERMS (paper-specific — do NOT use in any rubric item)
{forbidden_terms}

## FEW-SHOT EXAMPLES
{fewshot_ia}

## GENERATION RULES

1. **QUALITY-DRIVEN — NOT CONTENT-DRIVEN**: Each item evaluates whether the report has acquired the NECESSARY ANALYTICAL KNOWLEDGE to reason about the research question. Do NOT ask whether the report "states" or "describes" a specific finding from a source. Instead, ask whether the report understands the CONCEPTS and MECHANISMS needed for analysis.
   - BAD (content-driven): "Does the report state that source S1 found X?" 
   - GOOD (quality-driven): "Does the report explain the mechanism by which X affects Y?"
2. **DOMAIN-GENERAL LANGUAGE**: Use generalized concepts from above. NEVER use paper-specific method names, abbreviations, theorem numbers, or proper nouns that only appear in one source.
3. **NO GENERAL BACKGROUND**: Do NOT ask about general domain background knowledge (e.g., "Does the report define [CORE_CONCEPT]?"). Assume the reader already knows the basics. Focus on knowledge directly relevant to answering the research question.
4. **COVERAGE GUIDANCE** (prioritize these categories, but do NOT force exact counts — quality over coverage):
   - Core definitions directly related to the claim
   - Mechanisms and how they work
   - Experimental settings and evaluation metrics (only if relevant)
   - Key findings and their implications
   - Limitations and scope boundaries
   - Cross-source comparisons and contrasts
5. **STRONG VERBS ONLY**: Use verbs like: define, explain, identify, distinguish, describe, state, point out, cite, **compare, evaluate, classify, quantify, contrast, assess**.
   **FORBIDDEN weak verbs**: mention, list, include, contain, have, discuss, cover, present, provide.
6. **SOURCE-LINKED**: Every item must have source_ids pointing to the source(s) that provide the knowledge being tested.
   **PREFER SINGLE-SOURCE (≥70%)**: Most items should reference ONE source for clarity and traceability. Multi-source items (2+ source_ids) should be ≤30% and only when cross-source synthesis is essential.
7. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.
8. **START WITH "Does the report"**: All items must start with "Does the report".
9. **NO VAGUE WORDS**: Do not use words like "sufficient", "relevant", "comprehensive", "adequate", "proper", "appropriate", "good", "effective" without concrete operational criteria.
10. **OBSERVABLE CHECKLIST (OCR) — MANDATORY for define/explain**:
   - NEVER bare "Does the report explain X?" or "Does the report define X?"
   - ALWAYS use ONE of: (a) "..., i.e., <single verifiable proposition>"; (b) "..., that <specific fact>"; (c) "..., including (A) ... (B) ... (C) ..."
   - Provide `required_elements`: 2-4 short, independently checkable propositions (domain-general, not paper-specific values).
   - Prefer `state that` / `identify that` over bare `explain` when testing factual acquisition.
11. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items): Core domain definitions, fundamental concepts required to understand the research question.
- Mandatory ({mandatory_target} items): Important mechanisms, key data findings, essential methodology details, experimental settings.
- Standard ({standard_target} items): Supplementary context, scope descriptions, secondary comparisons, evaluation metrics.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1"], "importance": "critical|mandatory|standard", "competency_category": "definition|evidence|methodology|limitation|comparison", "required_elements": ["observable proposition A", "observable proposition B"], "judgment_mode": "binary|checklist"}}

Output JSON array only, no other text.
"""

PROMPT_OPERATIONALIZE = """\
You are an expert rubric engineer. Rewrite rubric items so each is **objectively scorable** (no subjective "adequately explain").

## RULES
1. Replace bare explain/define with either:
   - "Does the report state that ..., i.e., <one verifiable fact>?" (judgment_mode: binary), OR
   - "Does the report address the following observable points?" with required_elements list (judgment_mode: checklist)
2. required_elements: 2-4 short English propositions; each must be independently verifiable from report text.
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
You are an expert scientific report evaluator. Generate high-quality rubric items for the **Scientific Reasoning (SR)** dimension.

## CORE PRINCIPLE
You are evaluating the report's ANALYSIS and REASONING capabilities — NOT whether it describes
specific mechanisms from papers. Each item should test whether the report demonstrates
understanding through analysis, comparison, derivation, or argumentation.

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

## GENERATION RULES

1. **ANALYSIS OVER RESTATEMENT**: Each item evaluates analytical thinking — why, how, under what conditions — not surface-level description.
2. **DOMAIN-GENERAL LANGUAGE**: Use generalized concepts. NEVER reference paper-specific methods, theorem numbers, or proper nouns.
3. **STRONG ANALYTICAL VERBS ONLY**: analyze, evaluate, derive, argue, compare, reconcile, refute, conclude, assess, synthesize.
   **VERB DIVERSITY REQUIRED**: No single verb may appear in more than 25% of items. Distribute across analyze/derive/argue/evaluate/compare/reconcile/refute/conclude.
   **LIMIT "explain"**: Use "explain" for at most 20% of items — prefer analyze/derive/argue for deeper reasoning.
   **FORBIDDEN weak verbs**: mention, list, include, contain, have, cover, present, provide.
4. **ARGUMENT CHAIN REQUIRED**: Build items that form a coherent claim-verification chain:
   (a) challenge the core claim or its assumptions,
   (b) analyze mechanism-level conflicts (e.g., protection vs. detectability),
   (c) derive boundary conditions under which the claim holds or fails,
   (d) reconcile or contrast cross-source evidence,
   (e) evaluate whether evidence supports/refutes the claim (without stating the answer in the question).
5. **DERIVATION ITEMS REQUIRED**: At least 3 items must use verbs like "derive", "deduce", or "trace" — evaluating logical derivation from premises to conclusions.
6. **CLAIM-FOCUSED REASONING REQUIRED**: At least 40% of items must DIRECTLY address the validity of the claim — challenging or supporting the core assertion, identifying implicit assumptions, deriving boundary conditions, or evaluating whether the claim overstates findings. Use neutral phrasing: "Does the report evaluate whether..." NOT "Does the report explain why X fails..."
7. **NO ANSWER LEAKAGE**: NEVER reveal the conclusion in the question. BAD: "Does the report explain why noise fundamentally hinders detection?" GOOD: "Does the report evaluate whether adding noise to model updates creates challenges for anomaly detection mechanisms?"
8. **NO SEQUENCE-TRACING**: Do not require the report to "trace" or "follow" a specific paper's argument order.
9. **CROSS-SOURCE ANALYSIS**: Multi-source items (2+ source_ids) should be ≤30% and only when cross-source synthesis is essential.
10. **SOURCE-LINKED**: Every item must have source_ids. Prefer single-source binding (≥70%).
11. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.
12. **START WITH "Does the report"**: All items must start with "Does the report".
13. **NO VAGUE WORDS**: Do not use words like "sufficient", "relevant", "comprehensive", "adequate", "proper", "appropriate" without concrete operational criteria.
14. **OBSERVABLE CHECKLIST (OCR)**: Prefer "Does the report evaluate whether..." over bare "explain". Any explain/define MUST include i.e./that/checklist OR `required_elements` (2-3 verifiable propositions). Mechanism items: state condition P, mechanism M, outcome Q as separate elements.
15. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items, MUST be claim-focused): Core analytical chains that directly challenge or support the claim, cross-source conflict resolution, fundamental reasoning about mechanisms, derivation of boundary conditions, refutation of over-stated claims. These are the MOST IMPORTANT items for claim verification.
- Mandatory ({mandatory_target} items): Mechanism explanations, condition analysis, comparative arguments, causal reasoning.
- Standard ({standard_target} items): Secondary associations, forward-looking reasoning, supplementary analysis.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1"], "importance": "critical|mandatory|standard", "competency_category": "mechanism|comparison|limitation|synthesis", "required_elements": ["..."], "judgment_mode": "binary|checklist"}}

Output JSON array only, no other text.
"""

PROMPT_GENERATE_SYNTH = """\
You are an expert scientific report evaluator. Generate high-quality rubric items for the **Report Synthesis (Synth)** dimension.

## CORE PRINCIPLE
You are evaluating the STRUCTURE, CLARITY, and INTEGRITY of the report itself — its writing quality,
organization, citation accuracy, and whether it avoids misrepresentation. Many items will NOT have
source_ids because they evaluate the report as a standalone document.

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

## TASK TYPE: {task_type}

## CLAIM VERIFICATION SYNTH RULES (when task_type is claim_verification)
- **NO Critical items** — Synth uses Mandatory + Standard only (Critical target = 0).
- **Mandatory ≥ 4**: evidence table, verdict+justification, evidence-to-subproposition mapping, integrity/accuracy.
- **POSITIVE FRAMING ONLY**: Check whether the report INCLUDES/DOES X well. NEVER use negative traps ("omit", "fail to", "misattribute", "does not").
- **40-60% source-linked**: Items about citation accuracy or source-specific evidence should have source_ids; structural items may have empty source_ids.

## FEW-SHOT EXAMPLES
{fewshot_synth}

## GENERATION RULES

1. **QUALITY-DRIVEN — NOT CONTENT-DRIVEN**: You are evaluating whether the report is a GOOD ACADEMIC REPORT, not whether it summarized every detail from the sources. Do NOT ask whether the report "states" or "includes" a specific finding. Instead, evaluate analytical depth, reasoning quality, and structural integrity.
   - BAD (content-driven): "Does the report state that source S1 found X?"
   - GOOD (quality-driven): "Does the report evaluate the logical consistency of evidence across sources?"
2. **STRUCTURE & CLARITY**: Evaluate whether the report is well-organized, has clear verdict/conclusions, and communicates findings effectively.
3. **EVIDENCE TABLE**: Include items checking for structured evidence tables categorizing supporting, refuting, and neutral evidence, AND whether evidence is mapped to sub-propositions.
4. **VERDICT & CONFIDENCE**: Include items checking for clear verdict statements and confidence scores.
5. **INTEGRITY & ACCURACY ITEMS (2-3 required)**: These evaluate whether the report CORRECTLY represents sources and uses precise language. Give FULL score if the report does this well.
   - CITATION ACCURACY: "Does the report accurately attribute findings to the correct sources, without conflating results across different studies?"
   - PRECISE LANGUAGE: "Does the report use hedging language and avoid unsupported superlatives (e.g., 'proven', 'guaranteed', 'completely solved') when discussing research findings?"
   - REALISTIC CLAIMS: "Does the report accurately represent the scope of evidence, avoiding over-absolute claims that go beyond what the sources demonstrate?"
   CRITICAL: These evaluate GOOD BEHAVIOR (accurate attribution, precise language, realistic claims), not missing content.
6. **PROFESSIONAL LANGUAGE**: Check for precise, academic language usage with SPECIFIC criteria (e.g., "no unsupported superlatives like 'proven' or 'guaranteed'", "no colloquial expressions", "precise use of hedging language").
7. **FUTURE DIRECTIONS**: Check if the report identifies meaningful research gaps or future directions.
8. **LOGICAL SELF-CONSISTENCY**: Check if the report evaluates whether evidence from different sources is logically consistent.
9. **CITATION ACCURACY**: Check if the report accurately represents what each source claims (not just "cites sources" but "correctly attributes findings").
10. **SOURCE-DEPENDENT & INDEPENDENT**: Many items will have empty source_ids (evaluating report quality itself). Some items should have source_ids to verify citation accuracy.
11. **CHALLENGING ITEMS REQUIRED**: At least 3-4 items should evaluate aspects that a GOOD report may still NOT satisfy — these create differentiation between adequate and excellent reports. Examples:
    - Deriving conditions under which the claim fails
    - Identifying implicit assumptions not stated in sources
    - Evaluating realism of experimental settings
    - Discussing audit limitations
12. **DATASET DIVERSITY** (if applicable): If the research question involves experimental evaluation, include at least 1 item checking whether the report evaluates dataset diversity. Skip this if the query is theoretical or non-experimental.
13. **CONCRETE & JUDGEABLE**: Each item must be objectively answerable as Yes/No.
14. **NO VAGUE WORDS**: Do not use words like "good", "well", "sufficient", "relevant", "comprehensive", "adequate" without concrete operational criteria.
15. **START WITH "Does the report"** (or "Is the" for grammar): Items should use these prefixes.
16. **NO CHINESE**: All items must be in English.

## IMPORTANCE CALIBRATION
- Critical ({critical_target} items, MAX 0 for claim_verification): For claim_verification, generate ZERO Critical items in Synth.
- Mandatory ({mandatory_target} items, MIN 4): Evidence table, verdict, sub-proposition mapping, citation/integrity checks.
- Standard ({standard_target} items): Language quality, future directions, confidence score, challenging analytical items.

NOTE: For claim_verification, Synth has NO Critical items. Use Mandatory for structural requirements and Standard for supplementary checks.

## OUTPUT FORMAT
Generate exactly {target_count} items as a JSON array. Each item:
{{"question": "Does the report...?", "source_ids": ["S1"] or [], "importance": "critical|mandatory|standard", "competency_category": "structure|citation|visualization|language|recommendation|integrity"}}

Output JSON array only, no other text.
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
      "reason": "Both check whether the report defines [KEY_CONCEPT] as a formal guarantee",
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
#  Stage 3a — 轻量校准规则（不调用 LLM）
# ═══════════════════════════════════════════════════════════════════════════

# 模糊词列表 — 包含这些词的评分项直接删除
VAGUE_WORDS = [
    "sufficient", "relevant", "comprehensive", "adequate", "proper",
    "appropriate", "good", "effective", "thorough", "detailed",
    "in-depth", "high-quality", "well-structured", "well-written",
    "properly", "effectively", "appropriately", "comprehensively",
    "adequately", "sufficiently", "relevantly",
]

# 弱动词列表 — 使用这些动词开头的评分项直接删除
WEAK_VERBS = [
    "mention", "list", "include", "contain", "have", "discuss",
    "cover", "present", "provide",
]


# ═══════════════════════════════════════════════════════════════════════════
#  主类 v5
# ═══════════════════════════════════════════════════════════════════════════

class RubricGenerator:
    """评分表生成器 v5：轻量化、高质量、泛用性。"""

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
        logger.info("Starting Rubric Generation v5")
        logger.info("=" * 60)

        source_ids = [s.source_id for s in sources]
        dim_config = get_dimension_config(task_type)

        # ── Stage 1: 轻量知识提取 + 概念泛化 ──
        logger.info("\n[Stage 1a] Parsing query sub-questions...")
        sub_questions = self._parse_sub_questions(query)

        logger.info("\n[Stage 1b] Extracting key points from sources...")
        raw_key_points = self._extract_key_points(sources, query)

        logger.info("\n[Stage 1c] Generalizing concepts...")
        generalized_points, forbidden_terms = self._generalize_concepts(
            raw_key_points, query
        )

        # ── Stage 2: 质量驱动生成 ──
        logger.info("\n[Stage 2] Generating rubric items (quality-driven)...")

        ia_items = self._generate_dimension(
            "information_acquisition", query, sub_questions,
            generalized_points, forbidden_terms, sources,
            task_type=task_type,
        )
        sr_items = self._generate_dimension(
            "scientific_reasoning", query, sub_questions,
            generalized_points, forbidden_terms, sources,
            task_type=task_type,
        )
        synth_items = self._generate_dimension(
            "report_synthesis", query, sub_questions,
            generalized_points, forbidden_terms, sources,
            task_type=task_type,
        )

        # ── Stage 3a: 轻量校准 ──
        logger.info("\n[Stage 3a] Light calibration (rule-based)...")
        ia_items = self._light_calibrate(
            ia_items, "information_acquisition", forbidden_terms=forbidden_terms,
            task_type=task_type,
        )
        sr_items = self._light_calibrate(
            sr_items, "scientific_reasoning", forbidden_terms=forbidden_terms,
            all_dimension_items={"information_acquisition": ia_items},
            task_type=task_type,
        )
        synth_items = self._light_calibrate(
            synth_items, "report_synthesis", forbidden_terms=forbidden_terms,
            all_dimension_items={
                "information_acquisition": ia_items,
                "scientific_reasoning": sr_items,
            },
            task_type=task_type,
        )

        # ── Stage 3b: LLM 去重 ──
        logger.info("\n[Stage 3b] LLM deduplication...")
        ia_items, sr_items, synth_items = self._llm_deduplicate(
            ia_items, sr_items, synth_items, query,
        )

        # ── Stage 3c: 主张核查后处理 ──
        query_warnings: List[str] = []
        if task_type == "claim_verification":
            if is_survey_style_query(query):
                query_warnings.append(
                    "query 为综述/对比型表述，与 claim_verification 单点主张核验存在潜在错位；"
                    "已按 query 域过滤模板注入，建议确认 task_type 是否应为 literature_review"
                )
                logger.warning(
                    "Survey-style query under claim_verification — "
                    "using query-aligned templates only"
                )
            logger.info("\n[Stage 3c] Claim verification quality policy...")
            ia_items, sr_items, synth_items = self._apply_claim_verification_policy(
                ia_items, sr_items, synth_items, sources, query,
                forbidden_terms=forbidden_terms,
            )

        # ── Stage 3d: OCR 可观测性操作化 ──
        logger.info("\n[Stage 3d] Observability operationalization (OCR)...")
        ia_items, sr_items, synth_items = self._apply_observability_policy(
            ia_items, sr_items, synth_items,
        )

        # ── 组装 ──
        result = self._assemble(
            query, task_type, sources, ia_items, sr_items, synth_items,
            dim_config=dim_config,
            query_warnings=query_warnings,
        )
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
                        "You are an academic analysis expert. "
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
        max_len = 24000
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

    # ─────────────────────────────────────────────────────────────────────
    #  Stage 2: 质量驱动生成
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
        dim_config = get_dimension_config(task_type)
        config = dim_config[dimension_id]
        # Use weighted upper bound (70% upper, 30% lower) to allow calibration removals
        # while still generating enough high-quality items
        target_count = int(config["item_range"][0] * 0.3 + config["item_range"][1] * 0.7)
        source_ids = [s.source_id for s in sources]

        # 计算 role 分布
        role_dist = config["role_dist"]
        c_target = max(0, round(target_count * role_dist["critical"]))
        if task_type == "claim_verification" and dimension_id == "report_synthesis":
            c_target = 0
        m_target = max(2, round(target_count * role_dist["mandatory"]))
        if task_type == "claim_verification" and dimension_id == "report_synthesis":
            m_target = max(4, m_target)
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

        effective_query = query
        if task_type == "claim_verification" and is_survey_style_query(query):
            effective_query = (
                f"{query}\n\n"
                "[TASK FRAMING: Comparative/survey query under claim verification. "
                "Treat the implicit comparative thesis as the claim to evaluate. "
                "All items MUST stay within this query domain — do NOT introduce "
                "unrelated domains (e.g., poisoning attacks, privacy defenses) "
                "unless explicitly mentioned in the query.]"
            )

        prompt = prompt_template.format(
            query=effective_query,
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
            "You are an expert rubric standards designer. "
            "Generate high-quality, domain-general rubric items based on the "
            "generalized knowledge points. "
            "All output in English. Output JSON array only."
        )

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
            )

            # 标准化处理
            normalized = self._normalize_items(items, dimension_id)
            logger.info(
                f"  {dimension_id}: {len(normalized)} items after normalization"
            )
            return normalized

        except Exception as e:
            logger.error(f"  {dimension_id}: Generation failed - {e}")
            return []

    def _filter_domain_general_terms(
        self, raw_terms: List[str], query: str
    ) -> List[str]:
        """用 LLM 从 forbidden_terms 中筛掉领域通用术语，只保留真正的 paper-specific 术语。"""
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
                temperature=0.1,  # 低温度确保一致性
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
            synth_items, "report_synthesis", strict_explain=False
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
                enrich_item_observability(item, dimension_id), dimension_id
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
                    logger.debug(f"  OCR dropped after rewrite: {enriched.get('question', '')[:60]}")

        # 限制 explain/define 占比（IA≤35%, SR≤15%）
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
                system="You rewrite rubric items for objective scoring. Output JSON array only.",
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
    #  Stage 3: 轻量校准（纯规则，不调用 LLM）
    # ─────────────────────────────────────────────────────────────────────

    def _light_calibrate(
        self, items: List[Dict[str, Any]], dimension_id: str,
        forbidden_terms: List[str] = None,
        all_dimension_items: Dict[str, List[Dict[str, Any]]] = None,
        task_type: str = "claim_verification",
    ) -> List[Dict[str, Any]]:
        """
        轻量校准：只做规则检查，发现问题直接删除该项。
        检查项：
          1. 中文字符检查
          2. 模糊词检查
          3. 弱动词检查
          4. 格式检查（不以 "Does the report" 或 "Is the" 开头）
          5. 论文特有术语检查（二次扫描，对Synth也生效）
          6. 跨维度冗余检查
          7. 维度比例检查（如果项数偏离目标范围，删除多余的项）
        """
        dim_config = get_dimension_config(task_type)
        config = dim_config[dimension_id]
        min_count, max_count = config["item_range"]
        removed_reasons = {
            "chinese": 0, "vague": 0, "weak_verb": 0, "format": 0,
            "term": 0, "redundant": 0, "trim": 0, "leak": 0, "negative_synth": 0,
        }

        # 收集其他维度的question用于冗余检查
        other_questions = []
        if all_dimension_items:
            for dim, dim_items in all_dimension_items.items():
                if dim != dimension_id:
                    # 主张核查：IA 与 SR 主题重叠但认知层次不同，不做跨维冗余删除
                    if (
                        task_type == "claim_verification"
                        and dimension_id == "scientific_reasoning"
                        and dim == "information_acquisition"
                    ):
                        continue
                    for di in dim_items:
                        other_questions.append(di.get("question", "").lower())

        filtered = []
        for item in items:
            q = (item.get("question") or "").strip()
            q_lower = q.lower()

            # 1. 中文字符检查
            if re.search(r'[\u4e00-\u9fff]', q):
                removed_reasons["chinese"] += 1
                logger.debug(f"  Removed (Chinese): {q[:60]}...")
                continue

            # 2. 模糊词检查（整词匹配，避免误删 effectively 等）
            if self._has_vague_word(q_lower):
                removed_reasons["vague"] += 1
                logger.debug(f"  Removed (vague word): {q[:60]}...")
                continue

            # 2b. 答案泄露检查（SR/Synth 严格，IA 宽松）
            if dimension_id in ("scientific_reasoning", "report_synthesis"):
                if self._has_answer_leakage(q):
                    removed_reasons["leak"] += 1
                    logger.debug(f"  Removed (answer leakage): {q[:60]}...")
                    continue

            # 2c. Synth 负向陷阱检查
            if dimension_id == "report_synthesis" and self._is_negative_synth_trap(q):
                removed_reasons["negative_synth"] += 1
                logger.debug(f"  Removed (negative synth trap): {q[:60]}...")
                continue

            # 3. 弱动词检查（Synth维度跳过——Synth项允许更广泛的动词）
            if dimension_id != "report_synthesis":
                verb = self._extract_first_verb(q)
                if verb and verb.lower() in WEAK_VERBS:
                    # IA维度允许 explain/describe（在科学语境中是合理的认知动词）
                    if dimension_id == "information_acquisition" and verb.lower() in ("explain", "describe"):
                        pass  # 允许
                    elif dimension_id == "scientific_reasoning" and verb.lower() in SR_ALLOWED_EXTRA_VERBS:
                        pass  # 主张核查 SR 允许 discuss/conclude/refute 等
                    else:
                        removed_reasons["weak_verb"] += 1
                        logger.debug(f"  Removed (weak verb '{verb}'): {q[:60]}...")
                        continue

            # 4. 格式检查
            valid_prefixes = ("Does the report", "Is the", "Are the", "Can the", "Has the report")
            if not any(q.startswith(p) for p in valid_prefixes):
                removed_reasons["format"] += 1
                logger.debug(f"  Removed (format): {q[:60]}...")
                continue

            # 5. 论文特有术语检查（二次扫描——只过滤明显的方法名/专有名词）
            # 注意：forbidden_terms 已经过 LLM 领域通用术语过滤，只包含真正的 paper-specific 术语
            if forbidden_terms:
                found_term = False
                for term in forbidden_terms:
                    term_lower = term.lower().strip()
                    if dimension_id == "report_synthesis":
                        # Synth中只过滤最严格的专有名词（全大写缩写、camelCase方法名）
                        if len(term) >= 4 and (
                            re.match(r'^[A-Z]{3,}$', term)  # 全大写缩写
                            or re.search(r'[a-z][A-Z]', term)  # camelCase方法名
                        ):
                            if term_lower in q_lower:
                                removed_reasons["term"] += 1
                                logger.debug(f"  Removed (paper-specific term '{term}'): {q[:60]}...")
                                found_term = True
                                break
                    else:
                        # IA/SR维度：过滤包含大写字母或连字符的术语（长度>=4）
                        if len(term) >= 4 and (any(c.isupper() for c in term) or '-' in term):
                            if term_lower in q_lower:
                                removed_reasons["term"] += 1
                                logger.debug(f"  Removed (paper-specific term '{term}'): {q[:60]}...")
                                found_term = True
                                break
                if found_term:
                    continue

            # 6. 跨维度冗余检查
            if other_questions:
                # 提取核心内容（去掉 "Does the report" 前缀后的部分）
                core = q_lower
                for prefix in valid_prefixes:
                    if core.startswith(prefix.lower()):
                        core = core[len(prefix):].strip()
                        break
                # 检查是否与其他维度的项核心内容高度相似
                is_redundant = False
                for other_q in other_questions:
                    other_core = other_q
                    for prefix in valid_prefixes:
                        if other_core.startswith(prefix.lower()):
                            other_core = other_core[len(prefix):].strip()
                            break
                    # 简单判断：如果核心内容包含关系明显（一个包含另一个的主要动词和对象）
                    if len(core) > 20 and len(other_core) > 20:
                        # 检查共享关键词比例
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

        # 7. Synth 维度角色硬约束
        if dimension_id == "report_synthesis":
            if task_type == "claim_verification":
                for it in filtered:
                    if normalize_importance(it.get("importance")) == "critical":
                        it["importance"] = "mandatory"
            crit_count = sum(1 for it in filtered if normalize_importance(it.get("importance")) == "critical")
            mand_count = sum(1 for it in filtered if normalize_importance(it.get("importance")) == "mandatory")
            # 如果 Critical > 2，降级多余的 Critical → Mandatory
            max_crit = 0 if task_type == "claim_verification" else 2
            if crit_count > max_crit:
                downgrade_needed = crit_count - max_crit
                for it in filtered:
                    if downgrade_needed <= 0:
                        break
                    if normalize_importance(it.get("importance")) == "critical":
                        it["importance"] = "mandatory"
                        downgrade_needed -= 1
                logger.debug(f"  Synth: downgraded critical → mandatory")
            mand_count = sum(1 for it in filtered if normalize_importance(it.get("importance")) == "mandatory")
            # 如果 Mandatory < 4 且 Standard 项足够，升级 Standard → Mandatory
            min_mand = 4 if task_type == "claim_verification" else 4
            if mand_count < min_mand:
                upgrade_needed = min_mand - mand_count
                for it in filtered:
                    if upgrade_needed <= 0:
                        break
                    if normalize_importance(it.get("importance")) == "standard":
                        it["importance"] = "mandatory"
                        upgrade_needed -= 1
                logger.debug(f"  Synth: upgraded standard → mandatory")

        # 8. 通用角色升级：如果 Critical 比例低于 role_dist 下限的 80%，从 Mandatory 升级
        if dimension_id in ("information_acquisition", "scientific_reasoning"):
            role_dist = dim_config[dimension_id]["role_dist"]
            crit_count = sum(1 for it in filtered if normalize_importance(it.get("importance")) == "critical")
            min_crit_ratio = role_dist["critical"] * 0.8
            actual_crit_ratio = crit_count / len(filtered) if filtered else 0
            if actual_crit_ratio < min_crit_ratio:
                needed = max(1, int(len(filtered) * role_dist["critical"]) - crit_count)
                upgraded = 0
                # 优先升级 claim-focused 的 Mandatory 项
                candidates = sorted(
                    filtered,
                    key=lambda it: (
                        0 if self._is_claim_focused(it.get("question", "")) else 1,
                        0 if normalize_importance(it.get("importance")) == "mandatory" else 1,
                    ),
                )
                for it in candidates:
                    if upgraded >= needed:
                        break
                    if normalize_importance(it.get("importance")) == "mandatory":
                        it["importance"] = "critical"
                        upgraded += 1
                if upgraded > 0:
                    logger.info(f"  {dimension_id}: upgraded {upgraded} mandatory → critical ({actual_crit_ratio:.0%} → {min_crit_ratio:.0%})")

        # 8b. SR Critical 上限（主张核查：避免 Critical 膨胀）
        if dimension_id == "scientific_reasoning" and task_type == "claim_verification":
            crit_count = sum(
                1 for it in filtered
                if normalize_importance(it.get("importance")) == "critical"
            )
            max_crit = max(1, int(len(filtered) * 0.40))
            if crit_count > max_crit:
                downgrade = crit_count - max_crit
                for it in reversed(filtered):
                    if downgrade <= 0:
                        break
                    if normalize_importance(it.get("importance")) == "critical":
                        if not self._is_claim_focused(it.get("question", "")):
                            it["importance"] = "mandatory"
                            downgrade -= 1
                for it in reversed(filtered):
                    if downgrade <= 0:
                        break
                    if normalize_importance(it.get("importance")) == "critical":
                        it["importance"] = "mandatory"
                        downgrade -= 1

        # 9. 维度比例检查 — 如果项数超出目标范围上限，从末尾删除多余项
        if len(filtered) > max_count:
            # 按优先级排序：先保留 critical，再 mandatory，再 standard
            role_order = {"critical": 0, "mandatory": 1, "standard": 2}
            filtered.sort(key=lambda x: role_order.get(normalize_importance(x.get("importance", "standard")), 3))
            excess = len(filtered) - max_count
            # 删除末尾的 standard 项
            filtered = filtered[:max_count]
            removed_reasons["trim"] = excess

        logger.info(
            f"  {dimension_id} calibration: {len(items)} -> {len(filtered)} items "
            f"(removed: chinese={removed_reasons['chinese']}, "
            f"vague={removed_reasons['vague']}, "
            f"weak_verb={removed_reasons['weak_verb']}, "
            f"format={removed_reasons['format']}, "
            f"term={removed_reasons['term']}, "
            f"redundant={removed_reasons['redundant']}, "
            f"leak={removed_reasons['leak']}, "
            f"negative_synth={removed_reasons['negative_synth']}, "
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

            # 保护：每个维度最多删除 20% 的项（保留至少 80%）
            max_remove_ia = int(len(ia_items) * 0.2)
            max_remove_sr = int(len(sr_items) * 0.2)
            max_remove_synth = int(len(synth_items) * 0.2)
            if len(remove_ia) > max_remove_ia:
                logger.warning(f"  LLM dedup: IA remove {len(remove_ia)} > max {max_remove_ia}, truncating")
                remove_ia = set(sorted(remove_ia)[:max_remove_ia])
            if len(remove_sr) > max_remove_sr:
                logger.warning(f"  LLM dedup: SR remove {len(remove_sr)} > max {max_remove_sr}, truncating")
                remove_sr = set(sorted(remove_sr)[:max_remove_sr])
            if len(remove_synth) > max_remove_synth:
                logger.warning(f"  LLM dedup: Synth remove {len(remove_synth)} > max {max_remove_synth}, truncating")
                remove_synth = set(sorted(remove_synth)[:max_remove_synth])

            ia_items = [it for i, it in enumerate(ia_items) if i not in remove_ia]
            sr_items = [it for i, it in enumerate(sr_items) if i not in remove_sr]
            synth_items = [it for i, it in enumerate(synth_items) if i not in remove_synth]

            logger.info(
                f"  LLM deduplication: removed {len(remove_ia) + len(remove_sr) + len(remove_synth)} items "
                f"(IA: {len(ia_items)}, SR: {len(sr_items)}, Synth: {len(synth_items)})"
            )

        except Exception as e:
            logger.warning(f"  LLM deduplication failed: {e}, skipping")

        return ia_items, sr_items, synth_items

    @staticmethod
    def _has_vague_word(q_lower: str) -> bool:
        return any(
            re.search(rf"\b{re.escape(vw)}\b", q_lower) for vw in VAGUE_WORDS
        )

    @staticmethod
    def _has_answer_leakage(question: str) -> bool:
        q_lower = question.lower()
        return any(re.search(p, q_lower) for p in ANSWER_LEAK_PATTERNS)

    @staticmethod
    def _is_negative_synth_trap(question: str) -> bool:
        q_lower = question.lower()
        return any(re.search(p, q_lower) for p in NEGATIVE_SYNTH_PATTERNS)

    @staticmethod
    def _is_claim_focused(question: str) -> bool:
        q_lower = question.lower()
        return any(kw in q_lower for kw in CLAIM_FOCUS_KEYWORDS)

    @staticmethod
    def _cap_multi_source(items: List[Dict[str, Any]], max_ratio: float) -> List[Dict[str, Any]]:
        if not items:
            return items
        multi_indices = [
            i for i, it in enumerate(items)
            if len(it.get("source_ids") or []) >= 2
        ]
        max_multi = max(0, int(len(items) * max_ratio))
        if len(multi_indices) <= max_multi:
            return items
        for i in multi_indices[max_multi:]:
            sids = items[i].get("source_ids") or []
            if sids:
                items[i]["source_ids"] = [sids[0]]
        return items

    def _ensure_mandatory_synth_items(
        self, synth_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        existing_text = " ".join(it.get("question", "").lower() for it in synth_items)
        for tmpl in MANDATORY_SYNTH_TEMPLATES:
            if any(kw in existing_text for kw in tmpl["match_keywords"]):
                continue
            synth_items.append({
                "question": tmpl["question"],
                "source_ids": tmpl["source_ids"],
                "importance": tmpl["importance"],
                "competency_category": tmpl["competency_category"],
            })
            existing_text += " " + tmpl["question"].lower()
            logger.info(f"  Injected mandatory synth item: {tmpl['question'][:60]}...")
        return synth_items

    def _ensure_claim_sr_items(
        self,
        sr_items: List[Dict[str, Any]],
        source_ids: List[str],
        query: str,
        min_ratio: float = 0.35,
    ) -> List[Dict[str, Any]]:
        """注入 claim-focused SR 项（当比例不足时，且必须与 query 域对齐）。"""
        if not sr_items:
            return sr_items
        claim_count = sum(
            1 for it in sr_items if self._is_claim_focused(it.get("question", ""))
        )
        if claim_count / len(sr_items) >= min_ratio:
            return sr_items
        existing_text = " ".join(it.get("question", "").lower() for it in sr_items)
        default_src = [source_ids[0]] if source_ids else []
        for tmpl in CLAIM_SR_TEMPLATES:
            if claim_count / max(len(sr_items), 1) >= min_ratio:
                break
            if not item_aligns_with_query(tmpl["question"], query):
                continue
            if any(kw in existing_text for kw in tmpl["match_keywords"]):
                continue
            sr_items.append({
                "question": tmpl["question"],
                "source_ids": tmpl.get("source_ids") or default_src,
                "importance": tmpl["importance"],
                "competency_category": "synthesis",
            })
            claim_count += 1
            existing_text += " " + tmpl["question"].lower()
            logger.info(f"  Injected claim-focused SR item: {tmpl['question'][:60]}...")
        return sr_items

    @staticmethod
    def _filter_domain_drift(
        items: List[Dict[str, Any]], query: str, label: str
    ) -> List[Dict[str, Any]]:
        kept: List[Dict[str, Any]] = []
        removed = 0
        for it in items:
            q = it.get("question", "")
            if q and not item_aligns_with_query(q, query):
                removed += 1
                logger.info(f"  Removed domain drift ({label}): {q[:60]}...")
                continue
            kept.append(it)
        if removed:
            logger.info(f"  Domain drift filter ({label}): removed {removed} items")
        return kept

    def _scrub_forbidden_terms(
        self,
        items: List[Dict[str, Any]],
        forbidden_terms: List[str],
    ) -> List[Dict[str, Any]]:
        """删除仍含 paper-specific 术语的评分项（仅匹配长度≥4 的明确术语）。"""
        if not forbidden_terms:
            return items
        significant = [
            t for t in forbidden_terms
            if len(t.strip()) >= 4 and (
                "-" in t or re.search(r"[A-Z]{2,}", t) or re.search(r"[a-z][A-Z]", t)
            )
        ]
        if not significant:
            return items
        cleaned = []
        for it in items:
            q_lower = it.get("question", "").lower()
            if any(term.lower() in q_lower for term in significant):
                logger.debug(
                    f"  Removed (paper term): {it.get('question', '')[:60]}..."
                )
                continue
            cleaned.append(it)
        return cleaned

    def _apply_claim_verification_policy(
        self,
        ia_items: List[Dict[str, Any]],
        sr_items: List[Dict[str, Any]],
        synth_items: List[Dict[str, Any]],
        sources: List[SourceDocument],
        query: str,
        forbidden_terms: List[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """主张核查专用后处理：质量约束与结构保障。"""
        forbidden_terms = forbidden_terms or []
        source_ids = [s.source_id for s in sources]

        for it in synth_items:
            if normalize_importance(it.get("importance")) == "critical":
                it["importance"] = "mandatory"

        synth_items = [
            it for it in synth_items
            if not self._is_negative_synth_trap(it.get("question", ""))
        ]
        ia_items = [
            it for it in ia_items if not self._has_answer_leakage(it.get("question", ""))
        ]
        sr_items = [
            it for it in sr_items if not self._has_answer_leakage(it.get("question", ""))
        ]
        synth_items = [
            it for it in synth_items if not self._has_answer_leakage(it.get("question", ""))
        ]

        ia_items = self._cap_multi_source(ia_items, 0.30)
        sr_items = self._cap_multi_source(sr_items, 0.30)

        ia_items = self._filter_domain_drift(ia_items, query, "IA")
        sr_items = self._filter_domain_drift(sr_items, query, "SR")

        synth_items = self._ensure_mandatory_synth_items(synth_items)
        sr_items = self._ensure_claim_sr_items(sr_items, source_ids, query)

        ia_items = self._scrub_forbidden_terms(ia_items, forbidden_terms)
        sr_items = self._scrub_forbidden_terms(sr_items, forbidden_terms)
        synth_items = self._scrub_forbidden_terms(synth_items, forbidden_terms)

        # 为 citation/evidence 类 Synth 项补充 source（若缺失）
        for it in synth_items:
            q_lower = it.get("question", "").lower()
            if not it.get("source_ids") and any(
                kw in q_lower for kw in (
                    "cite", "source", "attribute", "evidence entry",
                    "represent the scope", "correctly attribute",
                )
            ):
                it["source_ids"] = source_ids[:1]
        # 保证 Synth 至少 40% 有 source（优先给 integrity/citation 类）
        if synth_items:
            linked = sum(1 for it in synth_items if it.get("source_ids"))
            while linked / len(synth_items) < 0.40 and source_ids:
                for it in synth_items:
                    if not it.get("source_ids"):
                        it["source_ids"] = source_ids[:1]
                        linked += 1
                        break
                else:
                    break

        claim_sr = sum(1 for it in sr_items if self._is_claim_focused(it.get("question", "")))
        if sr_items and claim_sr / len(sr_items) < 0.35:
            logger.warning(
                f"  SR claim-focused ratio low ({claim_sr}/{len(sr_items)}), "
                "consider prompt tuning"
            )

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
        dim_config: Dict[str, Dict] = None,
        query_warnings: List[str] = None,
    ) -> Dict[str, Any]:
        """组装最终的评分表输出。"""
        if dim_config is None:
            dim_config = get_dimension_config(task_type)
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
                enriched = enrich_item_observability(
                    {**item, "question": q, "competency_category": cat},
                    dim_id,
                )

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
            config = dim_config[dim_id]
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
            "task_id": self.config.task_id or f"{task_type}_auto_v5",
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
                "version": "5.2-ocr" if task_type == "claim_verification" else "5.2-ocr",
                "rubric_key_enabled": True,
                "capability_coverage_enabled": True,
                "ocr_enabled": True,
                "ocr_checklist_items": ocr_checklist,
                "ocr_naked_explain_remaining": ocr_naked,
                "dimension_stats": dimension_stats,
                "generation_model": self.config.rubric_model,
                "extraction_model": self.config.extract_model,
                "query_style": "survey" if is_survey_style_query(query) else "claim",
                "query_warnings": query_warnings or [],
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
        logger.info("Rubric Generation Complete v5")
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
