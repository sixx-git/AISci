"""
论文特征提取模块 — PaperFeatureExtractionSkill

从论文PDF文本中提取结构化特征，用于影响力评估。
提取的特征包括：
  - 论文结构特征（长度、章节数、图表数、参考文献数）
  - 内容特征（标题关键词、摘要质量、方法论描述、实验规模）
  - 创新特征（新颖性指标、跨领域程度）
  - 质量信号（语言质量、格式规范性）

这些特征与OpenAlex元数据互补，提供"文本质量"维度的量化输入。
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# 创新词列表（用于检测创新性声明）
INNOVATION_KEYWORDS = {
    "novel", "new", "first", "propose", "introduce", "innovative",
    "breakthrough", "pioneering", "groundbreaking", "state-of-the-art",
    "sota", "outperform", "surpass", "exceed", "improve",
    "novelty", "contribution", "original", "unique", "distinctive",
    "首创", "首次", "创新", "提出", "改进", "超越", "优于",
}

# 方法论关键词
METHODOLOGY_KEYWORDS = {
    "method", "approach", "algorithm", "framework", "model",
    "architecture", "system", "technique", "strategy", "mechanism",
    "protocol", "pipeline", "workflow", "procedure", "process",
    "实验", "方法", "算法", "框架", "模型", "体系结构",
}

# 实验规模关键词
EXPERIMENT_SCALE_KEYWORDS = {
    "dataset", "benchmark", "baseline", "ablation", "evaluation",
    "experiment", "trial", "test", "validation", "empirical",
    "dataset size", "number of samples", "participants", "subjects",
    "数据集", "基准", "实验", "消融", "评估",
}


def extract_paper_features(pdf_text: str) -> dict[str, Any]:
    """从论文PDF文本中提取结构化特征。

    Args:
        pdf_text: PDF提取的纯文本内容

    Returns:
        特征字典。
    """
    if not pdf_text:
        return _empty_features()

    text = pdf_text.strip()

    # 1. 基础结构特征
    structure = _extract_structure_features(text)

    # 2. 内容特征
    content = _extract_content_features(text)

    # 3. 创新特征
    innovation = _extract_innovation_features(text)

    # 4. 质量信号
    quality = _extract_quality_signals(text)

    # 5. 计算综合质量分（0-100）
    quality_score = _compute_quality_score(structure, content, innovation, quality)

    return {
        "structure": structure,
        "content": content,
        "innovation": innovation,
        "quality_signals": quality,
        "overall_quality_score": quality_score,
        "feature_version": "1.0",
    }


def _empty_features() -> dict[str, Any]:
    """返回空特征字典。"""
    return {
        "structure": {},
        "content": {},
        "innovation": {},
        "quality_signals": {},
        "overall_quality_score": 0,
        "feature_version": "1.0",
        "error": "Empty text",
    }


def _extract_structure_features(text: str) -> dict[str, Any]:
    """提取论文结构特征。"""
    lines = text.splitlines()
    words = text.split()

    # 文本长度
    char_count = len(text)
    word_count = len(words)

    # 图表数（基于关键词估算）
    figure_count = len(re.findall(r'\b[Ff]ig(?:ure)?\.?\s*\d+', text))
    table_count = len(re.findall(r'\b[Tt]able\.?\s*\d+', text))

    # 章节数
    section_patterns = [
        r'\n\d+\.\s+\w+',           # 1. Introduction
        r'\n[A-Z][a-z]+\s+and\s+[A-Z]',  # Methods and Materials
        r'\n(?:Abstract|Introduction|Methods?|Results?|Discussion|Conclusion|References|Appendix)',
    ]
    section_count = 0
    for pattern in section_patterns:
        section_count += len(re.findall(pattern, text))
    section_count = min(section_count, 20)  # 上限

    # 参考文献数（基于 [1], [2] 等格式或数字列表）
    ref_patterns = [
        r'\[\d+\]',           # [1], [2]
        r'\(\d{4}\)',         # (2023)
        r'^\d+\.\s+\w+.*\d{4}',  # 1. Author. Title. 2023.
    ]
    ref_count = 0
    for pattern in ref_patterns:
        matches = re.findall(pattern, text)
        ref_count = max(ref_count, len(matches))

    # 段落数
    paragraph_count = len([l for l in lines if l.strip() and not l.strip().startswith("[")])

    return {
        "char_count": char_count,
        "word_count": word_count,
        "paragraph_count": paragraph_count,
        "estimated_figures": figure_count,
        "estimated_tables": table_count,
        "estimated_sections": section_count,
        "estimated_references": ref_count,
        "has_abstract": bool(re.search(r'\b[Aa]bstract\b', text[:5000])),
        "has_introduction": bool(re.search(r'\b[Ii]ntroduction\b', text)),
        "has_methods": bool(re.search(r'\b(?:[Mm]ethods?|[Mm]ethodology)\b', text)),
        "has_results": bool(re.search(r'\b(?:[Rr]esults?|[Ff]indings?)\b', text)),
        "has_discussion": bool(re.search(r'\b[Dd]iscussion\b', text)),
        "has_conclusion": bool(re.search(r'\b[Cc]onclusion\b', text)),
        "has_references": bool(re.search(r'\b(?:[Rr]eferences?|[Bb]ibliography)\b', text)),
    }


def _extract_content_features(text: str) -> dict[str, Any]:
    """提取内容特征。"""
    text_lower = text.lower()

    # 摘要提取（前3000字符中寻找Abstract部分）
    abstract_text = ""
    abstract_match = re.search(r'[Aa]bstract[.:]?\s*(.+?)(?=\n\s*(?:[Ii]ntroduction|[1]\.\s*\w))', text[:8000], re.DOTALL)
    if abstract_match:
        abstract_text = abstract_match.group(1).strip()

    # 摘要质量
    abstract_words = abstract_text.split()
    abstract_length = len(abstract_words)
    has_structured_abstract = bool(re.search(r'\b(?:[Bb]ackground|[Oo]bjective|[Mm]ethods?|[Rr]esults?|[Cc]onclusion)\b', abstract_text))

    # 标题关键词（第一行或前200字符）
    title_text = text[:500].strip().split('\n')[0] if text else ""
    title_keywords = [w for w in title_text.lower().split() if len(w) > 3 and w.isalpha()]

    # 方法论描述丰富度
    method_section_match = re.search(r'(?:[Mm]ethods?|[Mm]ethodology)[.:]?\s*(.+?)(?=\n\s*(?:[Rr]esults?|[Dd]iscussion|[Cc]onclusion|[Ee]xperiments?))', text, re.DOTALL)
    method_text = method_section_match.group(1) if method_section_match else ""
    method_words = len(method_text.split())
    method_depth = "detailed" if method_words > 500 else "moderate" if method_words > 200 else "brief"

    # 实验规模信号
    experiment_matches = sum(1 for kw in EXPERIMENT_SCALE_KEYWORDS if kw.lower() in text_lower)
    has_ablation = "ablation" in text_lower or "消融" in text
    has_baseline = "baseline" in text_lower or "基线" in text
    has_comparison = any(kw in text_lower for kw in ["compare", "comparison", "versus", "vs", "对比"])

    # 跨领域信号
    concept_diversity = len(set(re.findall(r'\b\w{5,}\b', text_lower)))

    return {
        "abstract": {
            "length_words": abstract_length,
            "has_structured_format": has_structured_abstract,
            "quality": "good" if abstract_length > 150 else "moderate" if abstract_length > 80 else "poor",
        },
        "title_keywords": title_keywords[:10],
        "methodology": {
            "section_length_words": method_words,
            "description_depth": method_depth,
        },
        "experiment_signals": {
            "scale_indicators": experiment_matches,
            "has_ablation_study": has_ablation,
            "has_baseline_comparison": has_baseline,
            "has_comparison_with_others": has_comparison,
        },
        "concept_diversity": concept_diversity,
    }


def _extract_innovation_features(text: str) -> dict[str, Any]:
    """提取创新特征。"""
    text_lower = text.lower()

    # 创新词计数
    innovation_count = sum(1 for kw in INNOVATION_KEYWORDS if kw.lower() in text_lower)
    innovation_density = round(innovation_count / max(len(text.split()) / 1000, 1), 2)

    # 新颖性声明（明确声明"首次""第一个"等的句子）
    novelty_patterns = [
        r'\b(?:first|firstly)\b[^.]*\b(?:propose|introduce|present|report|demonstrate)',
        r'\b(?:to the best of our knowledge)\b',
        r'\b(?:no previous work)\b',
        r'\b(?:prior work has not)\b',
        r'首创',
        r'首次',
        r'第一次',
    ]
    novelty_claims = 0
    for pattern in novelty_patterns:
        novelty_claims += len(re.findall(pattern, text_lower))

    # 跨领域程度
    field_indicators = {
        "cs": ["neural", "deep learning", "machine learning", "algorithm", "dataset"],
        "biology": ["gene", "protein", "cell", "tissue", "organism", "clinical"],
        "physics": ["quantum", "particle", "thermal", "optical", "magnetic"],
        "medicine": ["patient", "treatment", "therapy", "diagnosis", "clinical trial"],
        "math": ["theorem", "proof", "lemma", "convergence", "optimization"],
    }
    field_scores = {}
    for field, indicators in field_indicators.items():
        field_scores[field] = sum(1 for ind in indicators if ind in text_lower)
    dominant_field = max(field_scores, key=field_scores.get) if field_scores else "unknown"
    cross_field_count = sum(1 for score in field_scores.values() if score >= 3)
    cross_domain_degree = "high" if cross_field_count >= 2 else "moderate" if cross_field_count >= 1 else "low"

    # 贡献声明（Introduction/Conclusion中的明确贡献列表）
    contribution_section = re.search(r'(?:contribution|contributions)[.:]?\s*(.+?)(?=\n\s*(?:[Oo]rganization|[Ss]tructure))', text_lower, re.DOTALL)
    contribution_text = contribution_section.group(1) if contribution_section else ""
    contribution_items = len(re.findall(r'(?:^|\n)\s*(?:\d+[.)]\s+|[-•]\s+|\(\d+\)\s*)', contribution_text))

    return {
        "innovation_keyword_count": innovation_count,
        "innovation_density": innovation_density,
        "novelty_claims": novelty_claims,
        "cross_domain_degree": cross_domain_degree,
        "cross_field_indicators": {k: v for k, v in field_scores.items() if v > 0},
        "dominant_field": dominant_field,
        "contribution_items": contribution_items,
        "has_clear_contributions": contribution_items > 0,
    }


def _extract_quality_signals(text: str) -> dict[str, Any]:
    """提取质量信号。"""
    text_lower = text.lower()

    # 语言质量
    # 检查常见语法错误模式（简化）
    error_patterns = [
        r'\b(?:a|an)\s+(?:a|an|the)\b',  # "a a"
        r'\bthe\s+the\b',
        r'\b\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+',  # 超长句子
    ]
    error_count = sum(len(re.findall(p, text_lower)) for p in error_patterns)
    error_rate = round(error_count / max(len(text.split()) / 1000, 1), 2)

    # 公式密度
    formula_count = len(re.findall(r'\$[^$]+\$', text)) + len(re.findall(r'\\begin\{equation\}', text))
    formula_density = round(formula_count / max(len(text.split()) / 1000, 1), 2)

    # 代码/伪代码
    has_code = bool(re.search(r'(?:```|def\s+\w+|class\s+\w+|Algorithm\s*\d|pseudo-code)', text_lower))

    # 数据可用性声明
    has_data_availability = bool(re.search(r'(?:data availability|code availability|supplementary|appendix)', text_lower))

    # 伦理声明（医学/人文领域）
    has_ethics = bool(re.search(r'(?:ethical approval|institutional review|irb|ethics committee)', text_lower))

    # 致谢和资助
    has_acknowledgments = bool(re.search(r'(?:acknowledgment|acknowledgement|funding|grant)', text_lower))

    # 作者贡献声明
    has_author_contributions = bool(re.search(r'(?:author contribution|credit|crediT)', text_lower))

    # 利益冲突声明
    has_conflict = bool(re.search(r'(?:conflict of interest|competing interest)', text_lower))

    return {
        "language_error_rate": error_rate,
        "formula_density": formula_density,
        "has_code_or_pseudocode": has_code,
        "has_data_availability": has_data_availability,
        "has_ethics_statement": has_ethics,
        "has_acknowledgments": has_acknowledgments,
        "has_author_contributions": has_author_contributions,
        "has_conflict_of_interest": has_conflict,
        "transparency_score": sum([
            has_data_availability,
            has_ethics,
            has_acknowledgments,
            has_author_contributions,
            has_conflict,
        ]),
    }


def _compute_quality_score(
    structure: dict,
    content: dict,
    innovation: dict,
    quality: dict,
) -> int:
    """计算综合质量分（0-100）。

    基于提取的特征，给出一个简化的质量评分。
    这个评分与LLM的内容质量评分互补，提供文本层面的客观信号。
    """
    score = 0

    # 结构完整性（30分）
    required_sections = ["has_abstract", "has_introduction", "has_methods", "has_references"]
    present = sum(1 for s in required_sections if structure.get(s, False))
    score += min(30, present * 7)

    # 内容质量（25分）
    abstract_quality = content.get("abstract", {}).get("quality", "poor")
    abstract_score = {"good": 10, "moderate": 6, "poor": 3}.get(abstract_quality, 3)
    method_depth = content.get("methodology", {}).get("description_depth", "brief")
    method_score = {"detailed": 10, "moderate": 6, "brief": 3}.get(method_depth, 3)
    experiment_score = min(5, content.get("experiment_signals", {}).get("scale_indicators", 0))
    score += abstract_score + method_score + experiment_score

    # 创新性（25分）
    novelty_score = min(15, innovation.get("novelty_claims", 0) * 3)
    cross_domain_score = {"high": 10, "moderate": 6, "low": 2}.get(innovation.get("cross_domain_degree", "low"), 2)
    contribution_score = min(5, innovation.get("contribution_items", 0) * 2)
    score += novelty_score + cross_domain_score + contribution_score

    # 质量信号（20分）
    transparency = quality.get("transparency_score", 0)
    transparency_score = min(10, transparency * 2)
    formula_score = min(5, quality.get("formula_density", 0) * 2)
    code_score = 5 if quality.get("has_code_or_pseudocode", False) else 0
    score += transparency_score + formula_score + code_score

    return min(100, max(0, score))
