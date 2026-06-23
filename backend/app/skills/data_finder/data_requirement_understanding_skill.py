"""数据需求理解 Skill — LLM 生成 DataSpec，规则 fallback"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.data_scenario_presets import project_mode_to_scenario
from app.core.project_modes import ProjectMode
from app.schemas.data_integration import empty_data_spec, merge_data_requirements_legacy, apply_data_spec_hints
from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import normalize_col

logger = logging.getLogger(__name__)
settings = get_settings()


class DataRequirementUnderstandingSkill(BaseSkill):
    name = "DataRequirementUnderstanding"
    description = "从研究问题与假设解析 DataSpec（多领域数据需求）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = input_data.get("research_question", "")
        hypothesis = input_data.get("selected_hypothesis", "") or input_data.get("hypothesis", "")
        project_mode = input_data.get("project_mode", ProjectMode.GENERAL.value)
        scenario = project_mode_to_scenario(project_mode)
        user_hints = input_data.get("user_data_spec_hints") or {}

        data_spec = await self._try_llm_data_spec(research_question, hypothesis, scenario, user_hints)
        if not data_spec:
            data_spec = self._rule_data_spec(research_question, hypothesis, scenario, project_mode)
            result.add_warning("使用规则 fallback 解析数据需求（LLM 不可用或未返回有效结果）")

        data_spec = apply_data_spec_hints(data_spec, user_hints)

        # 双写字段：data_spec 为新契约，data_requirements 兼容旧消费方
        legacy = merge_data_requirements_legacy(data_spec)
        payload = {**legacy, "data_spec": data_spec}
        result.data = payload
        return result

    async def _try_llm_data_spec(
        self,
        research_question: str,
        hypothesis: str,
        scenario: str,
        user_hints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:
        if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
            return None

        combined = f"{research_question}\n{hypothesis}".strip()
        if not combined:
            return None

        schema_example = {
            "research_question": "研究问题摘要",
            "scenario": scenario,
            "entities_of_interest": ["sample_id", "method"],
            "target_variables": ["metric_name", "value"],
            "column_synonyms": {"method": ["algo", "approach"]},
            "dataset_keywords": ["keyword1"],
            "domain_keywords": ["domain_term"],
            "preferred_sources": ["paper_table", "open_repository"],
            "merge_strategy_hint": "auto",
        }

        prompt = (
            "根据以下科研问题与假设，推断本次多源数据采集任务的结构化数据需求（DataSpec）。\n"
            "要求：领域无关、具体可检索；entities_of_interest 为跨表对齐用的实体/主键类字段名；"
            "target_variables 为希望整合的度量或变量名；column_synonyms 为常见同义列映射。\n"
            f"场景预设 scenario 固定为: {scenario}\n\n"
            f"研究问题:\n{research_question}\n\n"
            f"假设:\n{hypothesis or '（无）'}\n"
        )
        if user_hints:
            prompt += f"\n用户已填写的数据需求提示（请优先保留）:\n{user_hints}\n"

        try:
            from app.services.qwen_client import qwen_structured_chat

            raw = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                system_prompt=(
                    "你是科学数据需求分析助手。仅输出合法 JSON，不要 markdown。"
                    "不要编造不存在的具体数据集名称；列名用英文 snake_case 或常见学术缩写。"
                ),
                temperature=0.2,
                prompt_version="data_spec_v1",
            )
            return self._normalize_llm_spec(raw, research_question, scenario)
        except Exception as exc:
            logger.warning("DataSpec LLM 解析失败: %s", exc)
            return None

    @staticmethod
    def _normalize_llm_spec(
        raw: Dict[str, Any],
        research_question: str,
        scenario: str,
    ) -> Dict[str, Any]:
        spec = empty_data_spec(research_question, scenario)
        spec["research_question"] = str(raw.get("research_question") or research_question)[:500]
        spec["scenario"] = scenario

        for key in ("entities_of_interest", "target_variables", "dataset_keywords", "domain_keywords"):
            val = raw.get(key)
            if isinstance(val, list):
                spec[key] = [str(x)[:80] for x in val if x][:15]

        syns = raw.get("column_synonyms")
        if isinstance(syns, dict):
            spec["column_synonyms"] = {
                str(k): [str(s) for s in (v if isinstance(v, list) else [v])][:8]
                for k, v in syns.items()
                if k
            }

        hint = raw.get("merge_strategy_hint")
        if hint in ("auto", "stack", "join"):
            spec["merge_strategy_hint"] = hint

        sources = raw.get("preferred_sources")
        if isinstance(sources, list) and sources:
            spec["preferred_sources"] = [str(s) for s in sources][:12]

        return spec

    @staticmethod
    def _rule_data_spec(
        research_question: str,
        hypothesis: str,
        scenario: str,
        project_mode: str,
    ) -> Dict[str, Any]:
        combined = f"{research_question} {hypothesis}".strip()
        tokens = [t for t in re.findall(r"[\w\u4e00-\u9fff]+", combined.lower()) if len(t) >= 3]

        metric_keywords = {
            "accuracy", "f1", "auc", "rmse", "mae", "precision", "recall",
            "准确率", "f1_score", "global_accuracy", "loss", "error",
        }
        target_vars = sorted({t for t in tokens if any(m in t for m in metric_keywords) or t in metric_keywords})

        domain_keywords = list(dict.fromkeys(tokens[:20]))
        dataset_keywords = [t for t in tokens if t not in metric_keywords][:15]

        entities: List[str] = []
        for hint in ("id", "name", "sample", "subject", "client", "patient", "specimen"):
            for t in tokens:
                if hint in t and t not in entities:
                    entities.append(normalize_col(t))

        spec = empty_data_spec(combined[:500] or research_question, scenario)
        spec["target_variables"] = target_vars[:10]
        spec["entities_of_interest"] = entities[:8]
        spec["domain_keywords"] = domain_keywords[:20]
        spec["dataset_keywords"] = dataset_keywords[:15]

        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            fl_extra = [
                "FedAvg", "FedProx", "SCAFFOLD", "Non-IID", "communication cost",
                "client drift", "global accuracy", "federated benchmark",
            ]
            spec["domain_keywords"] = list(dict.fromkeys(spec["domain_keywords"] + [normalize_col(x) for x in fl_extra]))
            spec["dataset_keywords"] = list(dict.fromkeys(spec["dataset_keywords"] + ["federated", "non_iid", "client"]))
            spec["target_variables"] = list(dict.fromkeys(spec["target_variables"] + [
                "global_accuracy", "f1_score", "communication_cost_mb", "client_drift",
            ]))[:12]
            spec["entities_of_interest"] = list(dict.fromkeys(
                spec["entities_of_interest"] + ["client_id", "party_id", "entity_id"],
            ))[:10]
            spec["preferred_sources"].append("papers_with_code")

        return spec
