"""领域场景与教育层级配置 — 面向参赛团队的可复用模板"""
from __future__ import annotations

from typing import Any, Dict, List

EDUCATION_LEVELS = ["primary", "secondary", "undergraduate", "graduate", "researcher"]

EDUCATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "primary": {
        "label": "小学/科普",
        "max_path_steps": 2,
        "jargon_level": "plain",
        "show_confidence": False,
        "explanation_style": "用生活化比喻解释科学概念，避免公式和专业缩写。",
    },
    "secondary": {
        "label": "中学",
        "max_path_steps": 3,
        "jargon_level": "introductory",
        "show_confidence": False,
        "explanation_style": "使用基础术语，给出简单因果链和例子。",
    },
    "undergraduate": {
        "label": "本科",
        "max_path_steps": 4,
        "jargon_level": "standard",
        "show_confidence": True,
        "explanation_style": "给出方法、数据与结论的标准学术表述。",
    },
    "graduate": {
        "label": "研究生",
        "max_path_steps": 5,
        "jargon_level": "advanced",
        "show_confidence": True,
        "explanation_style": "包含假设、证据强度、局限性与可检验预测。",
    },
    "researcher": {
        "label": "科研工作者",
        "max_path_steps": 6,
        "jargon_level": "expert",
        "show_confidence": True,
        "explanation_style": "完整溯源链、置信度、反证与图谱路径。",
    },
}

DOMAIN_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "general_science": {
        "label": "通用科学问题",
        "description": "从论文/教材/网页抽取概念、方法、证据与结论，构建问题导向知识图谱。",
        "source_types": ["paper", "textbook", "database", "webpage"],
        "core_entities": ["Paper", "Concept", "Method", "Evidence", "Conclusion"],
        "example_questions": [
            "某方法在哪些数据集上被验证？",
            "当前假设有哪些支持与反对证据？",
            "领域内还有哪些未解问题？",
        ],
        "graph_rag_refs": ["LightRAG", "GraphRAG", "KAG"],
    },
    "federated_learning": {
        "label": "联邦学习",
        "description": "面向 Non-IID、通信成本、隐私机制等联邦场景的专业图谱与推理。",
        "source_types": ["paper", "benchmark_csv", "experiment_log"],
        "core_entities": ["FedAlgorithm", "Dataset", "NonIIDType", "Metric", "Hypothesis"],
        "example_questions": [
            "哪些方法能缓解 Non-IID？",
            "哪些算法会增加通信成本？",
            "FedProx 与 FedAvg 的证据差异是什么？",
        ],
        "graph_rag_refs": ["LightRAG", "KAG", "Youtu-GraphRAG"],
    },
    "biomedical": {
        "label": "生物医学",
        "description": "从文献与临床数据库抽取疾病、靶点、疗法与临床指标关系。",
        "source_types": ["paper", "clinical_db", "textbook"],
        "core_entities": ["Disease", "Target", "Therapy", "Metric", "Evidence"],
        "example_questions": [
            "某疗法针对哪些靶点？",
            "临床试验使用了哪些指标？",
            "支持与反对某疗法的证据分别来自哪里？",
        ],
        "graph_rag_refs": ["KAG", "GraphRAG"],
    },
}

RETRIEVAL_MODES = {
    "local": "实体邻域检索（LightRAG Local）— 适合具体方法/论文/证据查询",
    "global": "社区主题检索（GraphRAG Global）— 适合领域概览与宏观问题",
    "hybrid": "本地+全局融合（LightRAG Hybrid）— 默认推荐",
}


def normalize_education_level(level: str | None) -> str:
    if level and level in EDUCATION_LEVELS:
        return level
    return "undergraduate"


def normalize_retrieval_mode(mode: str | None) -> str:
    if mode in RETRIEVAL_MODES:
        return mode
    return "hybrid"


def resolve_domain_scenario(project_mode: str | None, override: str | None = None) -> str:
    if override and override in DOMAIN_SCENARIOS:
        return override
    if project_mode == "federated_learning":
        return "federated_learning"
    return "general_science"


def get_scenario_catalog() -> Dict[str, Any]:
    return {
        "education_levels": [
            {"id": k, **{kk: vv for kk, vv in v.items() if kk != "explanation_style"}}
            for k, v in EDUCATION_PROFILES.items()
        ],
        "domain_scenarios": DOMAIN_SCENARIOS,
        "retrieval_modes": RETRIEVAL_MODES,
    }
