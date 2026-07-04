"""研究领域推断与外部数据候选相关性过滤 — 支持全领域科研报告。"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

# 领域 slug -> 识别词（中英）
FIELD_HINTS: Dict[str, List[str]] = {
    "astronomy_physics": [
        "天文", "天体", "宇宙", "行星", "轨道", "恒星", "星系", "引力", "膨胀", "暗能量",
        "物理", "粒子", "量子", "凝聚态",
        "cosmology", "astronomy", "astrophysics", "planetary", "orbit", "solar system",
        "galaxy", "universe", "exoplanet", "ephemeris", "相对论", "天体物理", "行星科学",
        "physics", "quantum", "particle",
    ],
    "biomedical": [
        "医学", "临床", "基因", "蛋白", "细胞", "药物", "癌症", "cancer", "clinical",
        "genomics", "transcriptomics", "crispr", "chembl", "pubmed", "geo", "protein", "drug",
        "nanomedicine", "ehr", "mimic", "tcga", "健康", "流行病学",
    ],
    "biology": [
        "生物", "物种", "进化", "转录组", "基因组", "生态进化", "phylogeny", "proteomics",
        "organism", "species", "evolution", "transcriptomics",
    ],
    "chemistry": [
        "化学", "分子", "材料", "电化学", "催化", "储能", "smiles", "sdf", "mol",
        "chemistry", "molecule", "electrochemistry", "catalyst", "battery",
    ],
    "cs_ai": [
        "机器学习", "深度学习", "神经网络", "联邦学习", "federated", "computer vision",
        "nlp", "自然语言", "classification", "图像分类", "大模型", "llm",
        "人工智能", "信息科学", "算法", "机器人",
    ],
    "earth_environment": [
        "气候", "环境", "生态", "地理", "气象", "climate", "environment", "ecology", "gis",
        "遥感", "物种", "农业", "biodiversity", "remote sensing",
    ],
    "social_science": [
        "社会", "经济", "心理", "教育", "survey", "economics", "social science",
    ],
    "neuroscience": [
        "神经", "脑", "认知", "fmri", "eeg", "neuroimaging", "connectome", "neuroscience",
    ],
    "energy_science": [
        "能源", "氢能", "核能", "电池", "电网", "renewable", "hydrogen", "nuclear", "energy grid",
    ],
    "materials_engineering": [
        "工程", "材料", "制造", "结构仿真", "表征", "composite", "mechanical", "materials science",
    ],
    "math_science": [
        "数学", "数值模拟", "方程", "优化", "素数", "流体", "mathematics", "simulation", "pde",
    ],
}

# 非生物医学领域应屏蔽的数据源平台（小写子串匹配）
NON_BIOMED_BLOCKED_PLATFORMS = (
    "ncbi geo", "geo (gene", "pubmed", "chembl", "pubchem", "tcga", "mimic", "physionet",
)

# 候选标题/描述中的生物医学噪声词（用于非生医领域降权/剔除）
NON_BIOMED_BLOCKED_TERMS = (
    "crispr", "gene expression", "transcriptom", "cell line", "clinical trial",
    "cancer", "tumor", "trophoblast", "dlbcl", "lymphoma", "chip-seq", "rna-seq",
    "protein kinase", "genome-wide", "patient sample", "biopsy",
)

DEFAULT_MIN_RELEVANCE = 0.28


def _tokenize(text: str) -> Set[str]:
    if not text:
        return set()
    parts = re.split(r"[\s,，。；;、/|]+", text.lower())
    tokens: Set[str] = set()
    for p in parts:
        p = p.strip()
        if len(p) >= 2:
            tokens.add(p)
        for m in re.findall(r"[a-zA-Z]{3,}", p):
            tokens.add(m.lower())
    return tokens


def infer_research_field(
    *,
    research_question: str = "",
    research_domain: str = "",
    keywords: Optional[Iterable[str]] = None,
    data_spec: Optional[Dict[str, Any]] = None,
) -> str:
    """推断研究领域 slug；无法识别时返回 general。"""
    blob_parts: List[str] = []
    if research_domain:
        blob_parts.append(research_domain)
    if research_question:
        blob_parts.append(research_question)
    if keywords:
        blob_parts.extend(str(k) for k in keywords if k)
    if isinstance(data_spec, dict):
        blob_parts.extend(str(k) for k in (data_spec.get("domain_keywords") or []) if k)
        blob_parts.extend(str(k) for k in (data_spec.get("dataset_keywords") or []) if k)

    blob = " ".join(blob_parts).lower()
    if not blob.strip():
        return "general"

    from app.core.domain_data_catalog import field_from_category, parse_category_from_description

    for src in (research_domain, parse_category_from_description(" ".join(blob_parts))):
        slug = field_from_category(src)
        if slug != "general":
            return slug

    scores: Dict[str, int] = {}
    for field, hints in FIELD_HINTS.items():
        score = sum(1 for h in hints if h.lower() in blob)
        if score:
            scores[field] = score

    if not scores:
        return "general"

    # 生物医学需更高置信，避免泛词误触
    best_field = max(scores, key=scores.get)
    if best_field == "biomedical" and scores["biomedical"] < 2:
        non_bio = {k: v for k, v in scores.items() if k != "biomedical"}
        if non_bio and max(non_bio.values()) >= scores["biomedical"]:
            return max(non_bio, key=non_bio.get)
    return best_field


def build_research_context(
    *,
    research_question: str = "",
    research_domain: str = "",
    keywords: Optional[Iterable[str]] = None,
    data_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    spec = data_spec if isinstance(data_spec, dict) else {}
    kw = list(keywords or [])
    kw.extend(spec.get("domain_keywords") or [])
    kw.extend(spec.get("dataset_keywords") or [])
    field = infer_research_field(
        research_question=research_question,
        research_domain=research_domain,
        keywords=kw,
        data_spec=spec,
    )
    query_terms = _tokenize(
        f"{research_question} {research_domain} {' '.join(kw)} "
        f"{' '.join(spec.get('entities_of_interest') or [])} "
        f"{' '.join(spec.get('target_variables') or [])}"
    )
    return {
        "field": field,
        "research_question": research_question,
        "research_domain": research_domain,
        "query_terms": sorted(query_terms),
        "data_spec": spec,
    }


def build_external_search_query(context: Dict[str, Any]) -> str:
    """构造面向开放 API 的检索式（优先英文关键词，避免中文长句误检）。"""
    spec = context.get("data_spec") if isinstance(context.get("data_spec"), dict) else {}
    parts: List[str] = []

    for key in ("dataset_keywords", "domain_keywords"):
        for item in spec.get(key) or []:
            s = str(item).strip()
            if s and re.search(r"[A-Za-z]", s):
                parts.append(s)

    domain = str(context.get("research_domain") or "").strip()
    if domain and re.search(r"[A-Za-z]", domain):
        parts.append(domain)

    # 从问题中提取英文片段
    rq = str(context.get("research_question") or "")
    en_chunks = re.findall(r"[A-Za-z][A-Za-z0-9\s\-]{2,}", rq)
    parts.extend(c[:80] for c in en_chunks[:3])

    field = context.get("field") or "general"
    if not parts:
        from app.core.domain_data_catalog import get_search_seed

        spec_seed = spec.get("external_search_seed")
        if isinstance(spec_seed, str) and spec_seed.strip():
            parts.append(spec_seed.strip())
        else:
            parts.append(get_search_seed(field))

    # 去重保序
    seen: Set[str] = set()
    out: List[str] = []
    for p in parts:
        key = p.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(p.strip())
    return " ".join(out[:6])[:240]


def should_search_biomedical_sources(context: Dict[str, Any]) -> bool:
    return (context.get("field") or "general") in ("biomedical", "biology")


def score_external_candidate(
    candidate: Dict[str, Any],
    context: Dict[str, Any],
) -> float:
    """0~1 相关性评分。"""
    field = context.get("field") or "general"
    query_terms: Set[str] = set(context.get("query_terms") or [])
    if not query_terms:
        query_terms = _tokenize(
            f"{context.get('research_question', '')} {context.get('research_domain', '')}"
        )

    platform = str(candidate.get("source_platform") or "").lower()
    title = str(candidate.get("dataset_name") or candidate.get("name") or "")
    desc = str(candidate.get("description") or "")
    blob = f"{title} {desc} {platform}".lower()
    blob_tokens = _tokenize(blob)

    if not query_terms:
        return float(candidate.get("confidence") or 0.5)

    overlap = query_terms & blob_tokens
    score = min(1.0, len(overlap) * 0.18 + float(candidate.get("confidence") or 0.5) * 0.35)

    # 长词/短语加分
    rq = str(context.get("research_question") or "").lower()
    for term in query_terms:
        if len(term) >= 3 and term in blob:
            score += 0.08
        if len(term) >= 4 and term in rq and term in blob:
            score += 0.12

    # 非生医：屏蔽生医平台与噪声条目
    if field != "biomedical":
        if any(p in platform for p in NON_BIOMED_BLOCKED_PLATFORMS):
            score -= 0.55
        if any(t in blob for t in NON_BIOMED_BLOCKED_TERMS):
            score -= 0.45

    # OpenAlex 条目是论文元数据，不是可下载数据集
    if "openalex" in platform:
        score -= 0.35

    # 领域关键词加分
    field_hints = FIELD_HINTS.get(field)
    if field_hints:
        hint_terms = _tokenize(" ".join(field_hints))
        if blob_tokens & hint_terms:
            score += 0.22

    return max(0.0, min(1.0, score))


def filter_relevant_external_candidates(
    candidates: Optional[List[Dict[str, Any]]],
    context: Dict[str, Any],
    *,
    min_score: float = DEFAULT_MIN_RELEVANCE,
    max_results: int = 12,
) -> List[Dict[str, Any]]:
    """按领域相关性过滤并排序外部数据候选。"""
    if not candidates:
        return []

    scored: List[tuple[float, Dict[str, Any]]] = []
    for raw in candidates:
        c = dict(raw)
        rel = score_external_candidate(c, context)
        c["relevance_score"] = round(rel, 4)
        if rel >= min_score:
            scored.append((rel, c))

    scored.sort(key=lambda x: (-x[0], x[1].get("dataset_name") or ""))
    return [c for _, c in scored[:max_results]]


def is_actionable_dataset_candidate(candidate: Dict[str, Any]) -> bool:
    """是否属于需要用户手动下载/上传的数据集（排除论文元数据引用）。"""
    availability = str(candidate.get("availability") or "")
    if availability in ("reference_only", "filtered_out"):
        return False
    platform = str(candidate.get("source_platform") or "").lower()
    if "openalex" in platform:
        return False
    if availability in ("metadata_only", "catalog_only", "url_only"):
        return candidate.get("import_supported") is False
    return bool(candidate.get("import_supported", True) or candidate.get("url"))
