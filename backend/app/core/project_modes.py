"""项目运行模式定义与模板"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class ProjectMode(str, Enum):
    GENERAL = "general"
    FEDERATED_LEARNING = "federated_learning"


VALID_PROJECT_MODES = {ProjectMode.GENERAL.value, ProjectMode.FEDERATED_LEARNING.value}


def normalize_project_mode(mode: str | None) -> str:
    if mode and mode in VALID_PROJECT_MODES:
        return mode
    return ProjectMode.GENERAL.value


PROJECT_MODE_LABELS = {
    ProjectMode.GENERAL.value: "General AI Scientist",
    ProjectMode.FEDERATED_LEARNING.value: "Federated Learning Scientist",
}

PROJECT_MODE_LABELS_ZH = {
    ProjectMode.GENERAL.value: "通用 AI Scientist 模式",
    ProjectMode.FEDERATED_LEARNING.value: "联邦学习科研模式",
}

FL_RESEARCH_QUESTION_TEMPLATE = (
    "在非独立同分布（Non-IID）数据和异构客户端模型结构条件下，"
    "如何通过知识蒸馏或个性化联邦机制提升联邦学习系统的模型精度、收敛速度和通信效率？"
)

FL_TEMPLATE_KEYWORDS = [
    "FedAvg", "FedProx", "SCAFFOLD", "FedMD", "FedDF", "SplitNN", "VFL",
    "Non-IID", "client drift", "communication cost", "privacy budget",
]

FL_RESEARCH_DOMAIN = "联邦学习 / 分布式机器学习"
FL_RESEARCH_GOAL = (
    "在 Non-IID 与异构客户端条件下，设计并验证知识蒸馏、个性化联邦或 VFL 机制，"
    "提升全局/本地精度、收敛速度与通信效率，并兼顾隐私保护。"
)
FL_DATA_SOURCE = "历史联邦实验 CSV、公开 FL benchmark（如 LEAF/FEMNIST）、组内标注报告、客户端通信日志"
FL_CONSTRAINTS = "Non-IID 数据划分、通信带宽、隐私预算（DP/PSI）、客户端参与率、异构模型结构"
FL_EXPECTED_OUTPUT = "联邦实验对比报告、baseline 对比表、通信-精度权衡分析、隐私机制建议"

HORIZONTAL_FL_FIELDS = [
    "client_id", "method", "non_iid_type", "non_iid_degree",
    "global_accuracy", "f1_score", "communication_rounds",
    "communication_cost_mb", "client_drift",
]
HETEROGENEOUS_FL_FIELDS = [
    "model_type", "teacher_model", "student_model",
    "distillation_temperature", "skill_token_dim", "heterogeneity_level",
]
VERTICAL_FL_FIELDS = [
    "party_id", "entity_id", "aligned_id", "feature_owner", "label_owner",
    "aligned_sample_rate", "privacy_method", "privacy_budget",
]
FL_METRICS_FIELDS = [
    "accuracy", "f1_score", "auc", "global_accuracy", "communication_rounds",
    "communication_cost_mb", "client_drift", "convergence_round",
    "fairness_gap", "privacy_risk_score",
]

FL_BASELINES = {
    "horizontal_fl": ["Centralized", "LocalOnly", "FedAvg", "FedProx", "SCAFFOLD", "FedNova"],
    "heterogeneous_fl": ["FedMD", "FedDF", "FedGKT", "HeteroFL"],
    "personalized_fl": ["FedPer", "pFedMe", "Ditto", "FedRep", "FedBN"],
    "vertical_fl": ["VFL-LR", "VFL-NN", "SplitNN", "SecureBoost", "FedBCD"],
}

FL_METRICS = [
    "accuracy", "f1_score", "auc", "global_accuracy", "communication_rounds",
    "communication_cost_mb", "client_drift", "convergence_round",
    "fairness_gap", "privacy_risk_score",
]

FL_VARIABLES = [
    "num_clients", "participation_rate", "non_iid_degree", "local_epochs",
    "learning_rate", "distillation_temperature", "skill_token_dim",
    "privacy_budget", "aligned_sample_rate",
]

FL_KNOWN_REFERENCES = [
    "McMahan et al., Communication-Efficient Learning of Deep Networks from Decentralized Data (FedAvg), AISTATS 2017",
    "Li et al., Federated Optimization in Heterogeneous Networks (FedProx), MLSys 2020",
    "Karimireddy et al., SCAFFOLD: Stochastic Controlled Averaging for Federated Learning, ICML 2020",
    "Li et al., FedMD: Heterogenous Federated Learning via Model Distillation, NeurIPS Workshop 2019",
    "Lin et al., Ensemble Distillation for Robust Model Fusion in Federated Learning (FedDF), NeurIPS 2020",
    "Vepakomma et al., Split Learning for Health: Distributed Deep Learning without Sharing Raw Data (SplitNN), 2018",
    "Yang et al., Federated Machine Learning: Concept and Applications, IEEE Signal Processing Magazine 2019",
]


def get_research_question_template(mode: str) -> Dict[str, str]:
    if normalize_project_mode(mode) == ProjectMode.FEDERATED_LEARNING.value:
        return {
            "research_domain": FL_RESEARCH_DOMAIN,
            "research_question": FL_RESEARCH_QUESTION_TEMPLATE,
            "research_goal": FL_RESEARCH_GOAL,
            "research_background": (
                "联邦学习在 Non-IID 客户端、异构模型与通信约束下常出现 client drift、"
                "收敛慢与通信开销高；知识蒸馏与个性化联邦/VFL 是常见改进方向。"
            ),
            "data_source": FL_DATA_SOURCE,
            "constraints": FL_CONSTRAINTS,
            "expected_output": FL_EXPECTED_OUTPUT,
            "keywords": ", ".join(FL_TEMPLATE_KEYWORDS),
        }
    return {}


def empty_fl_context() -> Dict[str, Any]:
    return {
        "project_mode": ProjectMode.FEDERATED_LEARNING.value,
        "fl_setting": "unknown",
        "detected_fields": [],
        "client_fields": [],
        "party_fields": [],
        "metrics_fields": [],
        "target_candidates": [],
    }
