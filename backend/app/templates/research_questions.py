"""研究问题模板 — 通用 / 横向联邦 / 垂直联邦（VFL）"""
from __future__ import annotations

from typing import Dict

VFL_RESEARCH_QUESTION_TEMPLATE = (
    "在垂直联邦学习（VFL）场景中，如何在样本对齐（entity_id/aligned_id）和隐私保护约束下，"
    "利用多方异构特征与标签方协同建模，提升大模型微调任务的预测性能与通信效率，"
    "并权衡模型性能、通信开销与隐私风险？"
)

VFL_RESEARCH_DOMAIN = "垂直联邦学习 / 隐私计算 / 多方协同建模"

VFL_RESEARCH_GOAL = (
    "在特征分布在不同参与方、标签方与特征方分离的 VFL 设置下，"
    "设计 PSI/样本对齐、Secure Aggregation、差分隐私与 Split Learning 相结合的实验方案，"
    "对比 Centralized / Local Only / SplitNN / VFL-LR / VFL-NN / FedBCD / SecureBoost，"
    "评估 accuracy、通信成本、推理延迟与对齐成功率，并形成可迭代的闭环实验计划。"
)

VFL_DATA_SOURCE = (
    "历史多方特征 CSV、人工标注报告、已有联邦/VFL 实验日志、"
    "entity_id 对齐表、privacy_budget 配置、通信轮次记录"
)

VFL_CONSTRAINTS = (
    "样本 ID 对齐（PSI/aligned_id）、特征方/标签方数据不可 Raw 共享、"
    "privacy_budget、通信轮次上限、特征缺失率、对齐成功率阈值"
)

VFL_EXPECTED_OUTPUT = (
    "VFL baseline 对比表、对齐成功率与通信-精度权衡分析、"
    "隐私机制（DP/Secure Aggregation）建议、下一轮实验 replan 建议"
)

VFL_TEMPLATE_KEYWORDS = [
    "VFL", "vertical federated learning", "SplitNN", "PSI", "entity_id", "aligned_id",
    "feature_owner", "label_owner", "Secure Aggregation", "Differential Privacy",
    "Qwen", "通义千问", "阿里云百炼", "communication cost", "alignment",
]


def get_vfl_research_template() -> Dict[str, str]:
    return {
        "research_domain": VFL_RESEARCH_DOMAIN,
        "research_question": VFL_RESEARCH_QUESTION_TEMPLATE,
        "research_goal": VFL_RESEARCH_GOAL,
        "research_background": (
            "垂直联邦学习中，特征分布在不同机构（特征方），标签常集中在单一标签方；"
            "需在 entity_id 对齐与隐私约束下进行纵向特征融合，"
            "并平衡 prediction_accuracy、communication_round 与 privacy_budget。"
        ),
        "data_source": VFL_DATA_SOURCE,
        "constraints": VFL_CONSTRAINTS,
        "expected_output": VFL_EXPECTED_OUTPUT,
        "keywords": ", ".join(VFL_TEMPLATE_KEYWORDS),
        "scenario": "vertical_fl",
    }
