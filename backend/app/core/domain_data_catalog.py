"""SJTU 125 学科分类 → 研究领域、检索词与开放数据源目录。"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

# 中文学科名 / 英文学科名 → research_field slug
CATEGORY_TO_FIELD: Dict[str, str] = {
    "天文学": "astronomy_physics",
    "Astronomy": "astronomy_physics",
    "物理学": "astronomy_physics",
    "Physics": "astronomy_physics",
    "化学": "chemistry",
    "Chemistry": "chemistry",
    "医学与健康": "biomedical",
    "Medicine & Health": "biomedical",
    "生物学": "biology",
    "Biology": "biology",
    "生态学": "earth_environment",
    "Ecology": "earth_environment",
    "工程与材料科学": "materials_engineering",
    "Engineering & Materials Science": "materials_engineering",
    "信息科学": "cs_ai",
    "Information Science": "cs_ai",
    "人工智能": "cs_ai",
    "Artificial Intelligence": "cs_ai",
    "神经科学": "neuroscience",
    "Neuroscience": "neuroscience",
    "能源科学": "energy_science",
    "Energy Science": "energy_science",
    "数学科学": "math_science",
    "Mathematical Sciences": "math_science",
}

# 与 build_sjtu_125_dataset.py 对齐的数据提示（中文）
DOMAIN_DATA_HINTS: Dict[str, str] = {
    "数学科学": "公开数学文献、数值模拟数据、素数/流体方程相关基准数据集",
    "化学": "分子结构数据库、材料性能数据、电化学与储能实验数据",
    "医学与健康": "临床队列、基因组学、公共卫生与流行病学开放数据",
    "生物学": "基因组/转录组、物种分布、生态与进化比较数据",
    "天文学": "巡天观测、宇宙学模拟、天体物理开放目录数据",
    "物理学": "粒子物理、凝聚态实验数据、量子计算基准",
    "工程与材料科学": "材料表征、结构仿真、工程测试与制造数据",
    "信息科学": "计算理论基准、拓扑量子计算与算法实验数据",
    "神经科学": "脑成像、神经电生理、认知与语言行为数据集",
    "生态学": "气候/遥感、物种与农业生态系统监测数据",
    "能源科学": "能源系统运行数据、氢能/核能相关实验与仿真数据",
    "人工智能": "机器学习基准、机器人与群体智能评测数据",
}

# 面向 Zenodo / HuggingFace / Figshare 的英文检索种子
FIELD_SEARCH_SEEDS: Dict[str, str] = {
    "astronomy_physics": "astronomy survey cosmology planetary ephemeris dataset",
    "biomedical": "clinical genomics gene expression public health dataset",
    "biology": "genomics transcriptomics species ecology evolution dataset",
    "chemistry": "molecular structure chemistry materials electrochemistry dataset",
    "cs_ai": "machine learning benchmark computer vision NLP dataset",
    "earth_environment": "climate ecology remote sensing biodiversity GIS dataset",
    "social_science": "survey economics social science open dataset",
    "neuroscience": "neuroimaging fMRI EEG brain connectome dataset",
    "energy_science": "energy grid hydrogen nuclear renewable simulation dataset",
    "materials_engineering": "materials characterization mechanical testing simulation dataset",
    "math_science": "numerical simulation mathematical benchmark fluid dynamics dataset",
}

# 注入 data_spec.domain_keywords / dataset_keywords 的英文检索词
FIELD_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "astronomy_physics": [
        "astronomy", "cosmology", "planetary", "orbit", "ephemeris", "survey", "spectroscopy",
    ],
    "biomedical": ["clinical", "genomics", "epidemiology", "patient", "biomarker"],
    "biology": ["genomics", "transcriptomics", "species", "phylogeny", "proteomics"],
    "chemistry": ["molecule", "SMILES", "electrochemistry", "catalyst", "materials"],
    "cs_ai": ["machine learning", "benchmark", "classification", "NLP", "computer vision"],
    "earth_environment": ["climate", "ecology", "remote sensing", "biodiversity", "GIS"],
    "social_science": ["survey", "economics", "demographics", "social"],
    "neuroscience": ["fMRI", "EEG", "connectome", "neuroimaging", "cognitive"],
    "energy_science": ["renewable", "hydrogen", "grid", "battery", "nuclear"],
    "materials_engineering": ["materials", "characterization", "mechanical", "composite"],
    "math_science": ["simulation", "numerical", "PDE", "optimization", "prime"],
}

# DatasetDiscoverySkill 无精确匹配时的门户回退（dataset_name 列表）
FIELD_CATALOG_FALLBACKS: Dict[str, tuple[str, ...]] = {
    "astronomy_physics": (
        "NASA Exoplanet Archive", "JPL Horizons Ephemeris",
        "Sloan Digital Sky Survey (SDSS)", "Gaia Archive", "Zenodo",
    ),
    "biomedical": (
        "PubMed / PubMed Central", "GEO (Gene Expression Omnibus)", "ChEMBL",
        "PubChem BioAssay", "Zenodo", "Hugging Face Datasets",
    ),
    "biology": (
        "GEO (Gene Expression Omnibus)", "Zenodo", "Hugging Face Datasets",
        "UCI Machine Learning Repository",
    ),
    "chemistry": (
        "PubChem BioAssay", "ChEMBL", "Materials Project", "Zenodo",
    ),
    "cs_ai": (
        "Hugging Face Datasets", "OpenML", "Kaggle Datasets", "UCI Machine Learning Repository",
    ),
    "earth_environment": (
        "GBIF", "WorldClim", "Zenodo", "Hugging Face Datasets",
    ),
    "neuroscience": (
        "OpenNeuro", "Human Connectome Project", "Zenodo",
    ),
    "energy_science": (
        "NREL Data Catalog", "Zenodo", "UCI Machine Learning Repository",
    ),
    "materials_engineering": (
        "Materials Project", "NIST Materials Data", "Zenodo",
    ),
    "math_science": (
        "Zenodo", "UCI Machine Learning Repository", "OpenML",
    ),
    "social_science": (
        "Zenodo", "UCI Machine Learning Repository", "Hugging Face Datasets",
    ),
}

_CATEGORY_PREFIX_RE = re.compile(r"领域[：:]\s*([^。；\n]+)")


def parse_category_from_description(text: str) -> str:
    """从 file_description / data_need_note 解析「领域：XXX」。"""
    if not text:
        return ""
    m = _CATEGORY_PREFIX_RE.search(str(text))
    if m:
        return m.group(1).strip()
    return ""


def field_from_category(category: str) -> str:
    """学科名 → research_field slug；未知则 general。"""
    cat = (category or "").strip()
    if not cat:
        return "general"
    if cat in CATEGORY_TO_FIELD:
        return CATEGORY_TO_FIELD[cat]
    lower = cat.lower()
    for key, slug in CATEGORY_TO_FIELD.items():
        if key.lower() == lower:
            return slug
    return "general"


def infer_field_from_text(
    *,
    research_domain: str = "",
    file_description: str = "",
    research_question: str = "",
) -> str:
    """综合学科名与 file_description 推断领域 slug。"""
    for src in (research_domain, parse_category_from_description(file_description)):
        slug = field_from_category(src)
        if slug != "general":
            return slug
    if file_description:
        slug = field_from_category(parse_category_from_description(file_description))
        if slug != "general":
            return slug
    from app.core.research_field import infer_research_field

    return infer_research_field(
        research_question=research_question,
        research_domain=research_domain or parse_category_from_description(file_description),
    )


def get_search_seed(field: str) -> str:
    return FIELD_SEARCH_SEEDS.get(field or "general", "open research dataset")


def get_domain_keywords(field: str) -> List[str]:
    return list(FIELD_DOMAIN_KEYWORDS.get(field or "general", []))


def get_catalog_fallbacks(field: str) -> tuple[str, ...]:
    return FIELD_CATALOG_FALLBACKS.get(field or "general", ("Zenodo", "Hugging Face Datasets", "OpenML"))


def enrich_data_spec_from_domain(
    data_spec: Dict[str, Any],
    *,
    research_domain: str = "",
    file_description: str = "",
    research_question: str = "",
) -> Dict[str, Any]:
    """将学科目录关键词合并进 DataSpec（不覆盖用户已有项）。"""
    spec = dict(data_spec or {})
    note = str(spec.get("user_data_notes") or file_description or "").strip()
    category = parse_category_from_description(note) or (research_domain or "").strip()
    field = infer_field_from_text(
        research_domain=research_domain or category,
        file_description=note or file_description,
        research_question=research_question or str(spec.get("research_question") or ""),
    )

    spec["research_field_inferred"] = field
    if category and not spec.get("research_category"):
        spec["research_category"] = category

    domain_kw = get_domain_keywords(field)
    existing_domain: Set[str] = {str(x).lower() for x in (spec.get("domain_keywords") or [])}
    merged_domain = list(spec.get("domain_keywords") or [])
    for kw in domain_kw:
        if kw.lower() not in existing_domain:
            merged_domain.append(kw)
            existing_domain.add(kw.lower())
    if merged_domain:
        spec["domain_keywords"] = merged_domain[:20]

    # 从中文数据提示提取可检索词（分词后 ≥2 字）
    hint = DOMAIN_DATA_HINTS.get(category, "")
    if hint:
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}", hint)
        existing_ds: Set[str] = {str(x).lower() for x in (spec.get("dataset_keywords") or [])}
        merged_ds = list(spec.get("dataset_keywords") or [])
        for t in tokens[:8]:
            if t.lower() not in existing_ds:
                merged_ds.append(t)
                existing_ds.add(t.lower())
        if merged_ds:
            spec["dataset_keywords"] = merged_ds[:20]

    seed = get_search_seed(field)
    if seed:
        spec["external_search_seed"] = seed

    return spec


def merge_domain_hints_into_config(
    hints: Optional[Dict[str, Any]],
    *,
    research_domain: str = "",
    file_description: str = "",
) -> Dict[str, Any]:
    """为 project.config.data_spec_hints 注入领域关键词。"""
    out = dict(hints or {})
    note = str(out.get("data_need_note") or file_description or "").strip()
    category = parse_category_from_description(note) or research_domain.strip()
    field = field_from_category(category) if category else "general"
    if field != "general":
        out["research_field"] = field
    if category and not out.get("research_category"):
        out["research_category"] = category

    domain_kw = get_domain_keywords(field)
    if domain_kw:
        existing = {str(x).lower() for x in (out.get("domain_keywords") or [])}
        merged = list(out.get("domain_keywords") or [])
        for kw in domain_kw:
            if kw.lower() not in existing:
                merged.append(kw)
        out["domain_keywords"] = merged[:15]
    return out
