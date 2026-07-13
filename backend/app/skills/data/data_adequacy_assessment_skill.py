"""数据充分性评估 Skill — LLM 判断假设与已上传数据是否匹配，规则 fallback。"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()

ADEQUACY_STATUSES = frozenset({"adequate", "partial", "inadequate"})

_HYPOTHESIS_SIGNALS = {
    "federated": ("federated", "fedavg", "fedprox", "联邦", "non-iid", "client", "party"),
    "gan": ("gan", "generative adversarial", "生成对抗", "generator", "discriminator"),
    "privacy": ("privacy", "differential privacy", "差分隐私", "secure aggregation", "隐私"),
    "image": ("image", "cnn", "resnet", "vision", "图像", "png", "pixel"),
    "nlp": ("nlp", "bert", "transformer", "text classification", "文本分类"),
    "timeseries": ("time series", "时序", "forecast", "预测", "sensor"),
    "classification": ("classification", "分类", "accuracy", "f1", "auc"),
    "regression": ("regression", "回归", "rmse", "mae"),
}

_DATA_TYPE_SIGNALS = {
    "federated": ("client_id", "party_id", "global_accuracy", "communication", "non_iid"),
    "gan": ("generated", "fake", "real_score", "fid", "is_real"),
    "privacy": ("epsilon", "privacy_budget", "dp_noise", "leakage"),
    "image": ("width", "height", "pixel", "channel", "image_path"),
    "benchmark_metrics": ("accuracy", "loss", "f1", "auc", "rmse", "latency"),
    "compliance_rubric": ("rater", "motivation", "indicator", "score", "compliance", "fhir"),
}


class DataAdequacyAssessmentSkill(BaseSkill):
    name = "DataAdequacyAssessment"
    description = "评估已上传数据是否足以验证当前科学假设，并输出缺口与所需数据集描述"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = str(input_data.get("hypothesis") or "").strip()
        required_data = str(input_data.get("required_data") or "").strip()
        validation_target = str(input_data.get("validation_target") or "").strip()
        uploaded = input_data.get("uploaded_datasets") or []
        if not isinstance(uploaded, list):
            uploaded = []

        if not uploaded:
            payload = _empty_upload_payload(hypothesis, required_data)
            result.data = payload
            result.add_warning("无已上传数据集，需上传或下载推荐数据集")
            return result

        adequacy = await self._try_llm_adequacy(
            hypothesis=hypothesis,
            required_data=required_data,
            validation_target=validation_target,
            methods=str(input_data.get("methods") or ""),
            metrics=str(input_data.get("metrics") or ""),
            uploaded_datasets=uploaded,
            project_mode=str(input_data.get("project_mode") or context.get("project_mode") or "general"),
        )
        if not adequacy:
            adequacy = rule_fallback_adequacy(
                hypothesis=hypothesis,
                required_data=required_data,
                validation_target=validation_target,
                uploaded_datasets=uploaded,
            )
            result.add_warning("使用规则 fallback 评估数据充分性（LLM 不可用或未返回有效结果）")
        else:
            adequacy["source"] = "llm"

        result.data = adequacy
        return result

    async def _try_llm_adequacy(
        self,
        *,
        hypothesis: str,
        required_data: str,
        validation_target: str,
        methods: str,
        metrics: str,
        uploaded_datasets: List[Dict[str, Any]],
        project_mode: str,
    ) -> Optional[Dict[str, Any]]:
        if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
            return None

        ds_summary = []
        for ds in uploaded_datasets[:8]:
            if not isinstance(ds, dict):
                continue
            semantic = ds.get("semantic_schema") if isinstance(ds.get("semantic_schema"), dict) else {}
            ds_summary.append({
                "filename": ds.get("filename"),
                "n_rows": ds.get("n_rows"),
                "n_columns": ds.get("n_columns"),
                "columns": (ds.get("columns") or [])[:20],
                "semantic_schema": {
                    "recommended_targets": semantic.get("recommended_targets"),
                    "experiment_hints": (semantic.get("experiment_hints") or "")[:200],
                },
            })

        schema_example = {
            "status": "inadequate",
            "score": 0.35,
            "mismatch_reasons": ["示例：上传数据为合规评分表，无法验证 GAN 生成质量"],
            "what_uploaded_can_do": ["评分者一致性分析", "指标分布统计"],
            "what_hypothesis_needs": ["带标签训练样本", "模型性能指标列"],
            "required_datasets": [{
                "name": "联邦学习 benchmark 表格",
                "description": "含 client_id、global_accuracy、communication_cost",
                "modality": "tabular",
                "required_columns": ["client_id", "accuracy"],
                "search_keywords": ["federated learning benchmark", "non-iid"],
            }],
            "gaps": ["缺少模型训练/对比指标"],
            "recommended_search_query": "federated learning benchmark csv accuracy",
        }

        prompt = (
            "你是科研数据充分性评审助手。判断「已上传数据集」是否足以验证「科学假设」。\n"
            "要求：\n"
            "1. status 只能是 adequate（充分）/ partial（部分可用）/ inadequate（不充分）\n"
            "2. 若数据语义与假设领域明显不符（如 FHIR 合规评分 vs GAN/联邦训练），必须 inadequate\n"
            "3. partial：可用上传数据做探索性/pilot 分析，但不能完整验证核心假设\n"
            "4. required_datasets 描述真正需要补充的数据（不要编造具体 Zenodo 记录 ID）\n"
            "5. gaps 与 mismatch_reasons 用中文，具体可执行\n\n"
            f"项目模式: {project_mode}\n"
            f"假设: {hypothesis}\n"
            f"所需数据描述: {required_data or '（无）'}\n"
            f"验证目标: {validation_target or '（无）'}\n"
            f"方法: {methods[:800]}\n"
            f"指标: {metrics[:400]}\n"
            f"已上传数据集: {json.dumps(ds_summary, ensure_ascii=False)[:4000]}\n"
        )

        try:
            from app.services.qwen_client import qwen_structured_chat

            raw = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                system_prompt="仅输出合法 JSON。引擎探查的行数/列名为事实，不要修改。",
                temperature=0.15,
                prompt_version="data_adequacy_v1",
            )
            return normalize_adequacy_payload(raw, uploaded_datasets=uploaded_datasets)
        except Exception as exc:
            logger.warning("数据充分性 LLM 评估失败: %s", exc)
            return None


def _empty_upload_payload(hypothesis: str, required_data: str) -> Dict[str, Any]:
    return {
        "source": "rule_fallback",
        "status": "inadequate",
        "score": 0.0,
        "mismatch_reasons": [],
        "what_uploaded_can_do": [],
        "what_hypothesis_needs": [required_data or "与假设匹配的表格/实验数据"],
        "required_datasets": [{
            "name": "研究所需主数据集",
            "description": required_data or hypothesis[:200] or "与假设匹配的 CSV/表格",
            "modality": "tabular",
            "required_columns": [],
            "search_keywords": _extract_keywords(hypothesis + " " + required_data)[:8],
        }],
        "gaps": ["尚未上传任何数据集"],
        "recommended_search_query": (hypothesis + " " + required_data).strip()[:400],
    }


def _extract_keywords(text: str) -> List[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]{3,}", (text or "").lower())
    return list(dict.fromkeys(tokens))[:15]


def _detect_hypothesis_domains(text: str) -> set[str]:
    blob = (text or "").lower()
    found = set()
    for domain, kws in _HYPOTHESIS_SIGNALS.items():
        if any(k in blob for k in kws):
            found.add(domain)
    return found


def _detect_data_domains(uploaded_datasets: List[Dict[str, Any]]) -> set[str]:
    blob_parts: List[str] = []
    for ds in uploaded_datasets:
        if not isinstance(ds, dict):
            continue
        blob_parts.append(str(ds.get("filename") or ""))
        blob_parts.extend(str(c) for c in (ds.get("columns") or [])[:30])
        sem = ds.get("semantic_schema") if isinstance(ds.get("semantic_schema"), dict) else {}
        blob_parts.append(str(sem.get("experiment_hints") or ""))
    blob = " ".join(blob_parts).lower()
    found = set()
    for domain, kws in _DATA_TYPE_SIGNALS.items():
        if any(k in blob for k in kws):
            found.add(domain)
    if "fhir" in blob or ("indicator" in blob and "rater" in blob):
        found.add("compliance_rubric")
    return found


def rule_fallback_adequacy(
    *,
    hypothesis: str,
    required_data: str,
    validation_target: str,
    uploaded_datasets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    hypo_domains = _detect_hypothesis_domains(
        f"{hypothesis} {required_data} {validation_target}"
    )
    data_domains = _detect_data_domains(uploaded_datasets)

    mismatch: List[str] = []
    what_can: List[str] = []
    what_needs: List[str] = []
    status = "adequate"
    score = 0.85

    if hypo_domains & {"federated", "gan", "privacy"} and "compliance_rubric" in data_domains:
        status = "inadequate"
        score = 0.2
        mismatch.append(
            "已上传数据为合规/评分类表格（如 FHIR 指标），无法反映模型训练性能或隐私保护实验结果"
        )
        what_can.extend(["评分分布分析", "评分者一致性", "合规指标统计"])
        what_needs.extend([
            "含模型/算法对比指标的数据（accuracy、F1、communication_cost 等）",
            "或联邦学习 benchmark 客户端级结果表",
        ])
    elif hypo_domains & {"image"} and "image" not in data_domains:
        status = "inadequate"
        score = 0.25
        mismatch.append("假设涉及图像任务，但上传数据未包含图像或图像特征字段")
        what_needs.append("图像数据集或含 image_path/像素特征的表格")
    elif hypo_domains and not data_domains:
        status = "partial"
        score = 0.55
        mismatch.append("无法从列名明确判断数据领域，建议人工确认或补充语义标注")
    elif hypo_domains & {"federated"} and "federated" not in data_domains and "benchmark_metrics" in data_domains:
        status = "partial"
        score = 0.6
        mismatch.append("有通用指标列但缺少联邦学习特有字段（client_id、communication 等）")
        what_can.append("基线分类/回归 pilot 分析")
        what_needs.append("联邦场景 benchmark 或多方 client 结果")

    gaps = list(mismatch)
    if status == "adequate" and not uploaded_datasets:
        status = "inadequate"
        score = 0.0
        gaps.append("无已上传数据")

    search_q = " ".join(_extract_keywords(f"{hypothesis} {required_data} {validation_target}"))[:400]
    required_datasets: List[Dict[str, Any]] = []
    if status != "adequate":
        required_datasets.append({
            "name": "假设验证所需主数据集",
            "description": required_data or validation_target or hypothesis[:200],
            "modality": "tabular",
            "required_columns": [],
            "search_keywords": _extract_keywords(
                f"{hypothesis} {required_data} {' '.join(what_needs)}"
            )[:10],
        })

    return {
        "source": "rule_fallback",
        "status": status,
        "score": round(score, 2),
        "mismatch_reasons": mismatch,
        "what_uploaded_can_do": what_can,
        "what_hypothesis_needs": what_needs or _extract_keywords(required_data or hypothesis)[:5],
        "required_datasets": required_datasets,
        "gaps": gaps,
        "recommended_search_query": search_q,
    }


def normalize_adequacy_payload(
    raw: Dict[str, Any],
    *,
    uploaded_datasets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    status = str(raw.get("status") or "partial").strip().lower()
    if status not in ADEQUACY_STATUSES:
        status = "partial"

    def _str_list(key: str, limit: int = 8) -> List[str]:
        val = raw.get(key)
        if not isinstance(val, list):
            return []
        return [str(x)[:300] for x in val if x][:limit]

    required_datasets: List[Dict[str, Any]] = []
    for item in raw.get("required_datasets") or []:
        if not isinstance(item, dict):
            continue
        required_datasets.append({
            "name": str(item.get("name") or "")[:120],
            "description": str(item.get("description") or "")[:500],
            "modality": str(item.get("modality") or "tabular")[:40],
            "required_columns": [str(c)[:80] for c in (item.get("required_columns") or []) if c][:20],
            "search_keywords": [str(k)[:60] for k in (item.get("search_keywords") or []) if k][:10],
        })

    score = raw.get("score")
    try:
        score_f = float(score) if score is not None else 0.5
    except (TypeError, ValueError):
        score_f = 0.5
    score_f = max(0.0, min(1.0, score_f))

    gaps = _str_list("gaps", 10)
    mismatch = _str_list("mismatch_reasons", 8)

    payload = {
        "source": "llm",
        "status": status,
        "score": round(score_f, 2),
        "mismatch_reasons": mismatch,
        "what_uploaded_can_do": _str_list("what_uploaded_can_do", 8),
        "what_hypothesis_needs": _str_list("what_hypothesis_needs", 8),
        "required_datasets": required_datasets[:6],
        "gaps": gaps or mismatch,
        "recommended_search_query": str(raw.get("recommended_search_query") or "")[:400],
    }

    if status == "adequate" and mismatch:
        payload["status"] = "partial"
        payload["score"] = min(payload["score"], 0.65)

    if not uploaded_datasets:
        return _empty_upload_payload("", "")

    return payload


def merge_adequacy_into_experiment_design(
    result_dict: Dict[str, Any],
    adequacy: Dict[str, Any],
    *,
    round_id: str = "",
) -> Dict[str, Any]:
    """将充分性评估写入实验设计结果并合并 data_gap。"""
    result_dict["data_adequacy"] = adequacy
    gaps = list(result_dict.get("data_gap") or [])
    if isinstance(gaps, str):
        gaps = [gaps] if gaps else []
    for g in adequacy.get("gaps") or adequacy.get("mismatch_reasons") or []:
        if g and g not in gaps:
            gaps.append(str(g))
    result_dict["data_gap"] = gaps

    status = adequacy.get("status")
    if status == "inadequate":
        result_dict["validation_blocked"] = True
        result_dict["validation_blocked_reason"] = "; ".join(
            adequacy.get("mismatch_reasons") or gaps[:3]
        )[:500]
    elif status == "partial":
        result_dict.setdefault("warnings", [])
        if isinstance(result_dict["warnings"], list):
            result_dict["warnings"].append(
                "数据仅部分匹配假设，小样验证结果应标注为 pilot/exploratory"
            )
    if round_id:
        adequacy["assessment_round_id"] = round_id
    return result_dict


def resolve_upload_status(adequacy: Dict[str, Any], uploaded_count: int) -> str:
    if uploaded_count == 0:
        return "pending_upload"
    status = adequacy.get("status")
    if status == "adequate":
        return "ready"
    if status == "partial":
        return "partial"
    return "inadequate"


def resolve_next_action(adequacy: Dict[str, Any], uploaded_count: int) -> str:
    if uploaded_count == 0:
        return "upload_datasets"
    if adequacy.get("status") == "inadequate":
        return "download_recommended"
    if adequacy.get("status") == "partial":
        return "revise_hypothesis_or_add_data"
    return "proceed_validation"
