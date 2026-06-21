"""隐私机制建议 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class PrivacyMechanismSuggestionSkill(BaseSkill):
    name = "PrivacyMechanismSuggestion"
    description = "根据联邦场景推荐 DP/PSI/Secure Aggregation 等隐私机制"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        fl_setting = input_data.get("fl_setting", "horizontal_fl")
        fl_context = input_data.get("fl_context", {}) or {}
        party_fields = fl_context.get("party_fields") or []

        mechanisms: List[Dict[str, str]] = []

        if fl_setting in ("horizontal_fl", "personalized_fl", "unknown"):
            mechanisms.extend([
                {"name": "Differential Privacy (DP)", "reason": "限制单轮梯度泄露，控制 privacy_budget"},
                {"name": "Secure Aggregation", "reason": "横向联邦中保护客户端更新不被服务器窥视"},
            ])
        if fl_setting == "vertical_fl" or party_fields:
            mechanisms.extend([
                {"name": "PSI (Private Set Intersection)", "reason": "垂直联邦样本对齐而不暴露交集外样本"},
                {"name": "SplitNN / VFL 加密中间表示", "reason": "特征方/标签方协同训练且最小化原始特征暴露"},
            ])
        if fl_setting == "heterogeneous_fl":
            mechanisms.append(
                {"name": "Knowledge Distillation with noise", "reason": "异构模型蒸馏时加入噪声或 logits 裁剪"}
            )

        mechanisms.append(
            {"name": "Communication compression + DP", "reason": "降低 communication_cost_mb 同时控制隐私风险"}
        )

        result.data = {
            "privacy_mechanisms": mechanisms[:6],
            "recommended_budget_field": "privacy_budget" if "privacy_budget" in (fl_context.get("detected_fields") or []) else None,
        }
        return result
