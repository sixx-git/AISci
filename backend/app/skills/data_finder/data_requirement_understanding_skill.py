"""数据需求理解 Skill"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from app.core.project_modes import ProjectMode
from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import normalize_col


class DataRequirementUnderstandingSkill(BaseSkill):
    name = "DataRequirementUnderstanding"
    description = "从研究问题与假设解析数据需求"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = input_data.get("research_question", "")
        hypothesis = input_data.get("selected_hypothesis", "") or input_data.get("hypothesis", "")
        project_mode = input_data.get("project_mode", ProjectMode.GENERAL.value)

        combined = f"{research_question} {hypothesis}".strip()
        tokens = [t for t in re.findall(r"[\w\u4e00-\u9fff]+", combined.lower()) if len(t) >= 3]

        metric_keywords = {
            "accuracy", "f1", "auc", "rmse", "mae", "precision", "recall",
            "accuracy", "准确率", "f1_score", "global_accuracy",
        }
        expected_metrics = sorted({t for t in tokens if any(m in t for m in metric_keywords) or t in metric_keywords})

        domain_keywords = list(dict.fromkeys(tokens[:20]))
        dataset_keywords = [t for t in tokens if t not in metric_keywords][:15]

        preferred_sources = ["uploaded_pdf", "bibtex", "openalex", "zenodo", "figshare", "huggingface", "kaggle", "uci"]

        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            fl_extra = [
                "FedAvg", "FedProx", "SCAFFOLD", "Non-IID", "communication cost",
                "client drift", "global accuracy", "federated benchmark",
            ]
            domain_keywords = list(dict.fromkeys(domain_keywords + [normalize_col(x) for x in fl_extra]))
            dataset_keywords = list(dict.fromkeys(dataset_keywords + ["federated", "non_iid", "client"]))
            expected_metrics = list(dict.fromkeys(expected_metrics + [
                "global_accuracy", "f1_score", "communication_cost_mb", "client_drift",
            ]))
            preferred_sources.append("papers_with_code")

        payload = {
            "data_need": combined[:500] or "未提供明确数据需求",
            "target_variables": expected_metrics[:10],
            "expected_metrics": expected_metrics[:10],
            "domain_keywords": domain_keywords[:20],
            "dataset_keywords": dataset_keywords[:15],
            "preferred_sources": preferred_sources,
            "output_format": "csv",
        }
        result.data = payload
        return result
