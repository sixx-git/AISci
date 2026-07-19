"""
公开数据集发现 Skill

根据实验设计/研究问题，通过外部开放 API 动态检索数据集（Zenodo、HuggingFace、Figshare、GEO 等），
不使用预定义静态数据集列表。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill

logger = logging.getLogger(__name__)


def build_experiment_dataset_search_query(input_data: Dict[str, Any]) -> str:
    """从假设与实验设计字段拼装检索查询。"""
    parts: List[str] = []
    for key in (
        "research_question",
        "hypothesis",
        "required_data",
        "datasets",
        "source_data",
        "target_data",
        "methods",
        "metrics",
    ):
        val = input_data.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip()[:600])
    keywords = input_data.get("keywords") or []
    if isinstance(keywords, list):
        parts.extend(str(k).strip() for k in keywords if k and str(k).strip())
    combined = " ".join(parts).strip()
    return combined[:2000]


def _map_candidate_to_dataset(candidate: Dict[str, Any]) -> Dict[str, Any]:
    from app.core.dataset_urls import normalize_dataset_download_url

    url = normalize_dataset_download_url(
        str(candidate.get("url") or candidate.get("download_url") or "").strip(),
        name=str(candidate.get("dataset_name") or candidate.get("name") or ""),
        source_type=str(candidate.get("source_platform") or candidate.get("source") or ""),
    )
    return {
        "dataset_name": candidate.get("dataset_name") or candidate.get("name") or "未命名数据集",
        "source_platform": candidate.get("source_platform") or candidate.get("source") or "",
        "source": candidate.get("source_platform") or candidate.get("source") or "",
        "url": url,
        "download_url": url,
        "description": (candidate.get("description") or "")[:500],
        "license": candidate.get("license") or "",
        "confidence": candidate.get("confidence"),
        "availability": candidate.get("availability") or "url_only",
        "import_supported": bool(candidate.get("import_supported", False)),
        "api_type": candidate.get("api_type") or "live",
    }


class DatasetDiscoverySkill(BaseSkill):
    """根据实验需求动态检索公开数据集（仅 live API，无预定义列表）。"""

    name = "DatasetDiscovery"
    description = "根据实验设计需求检索开放数据集并返回下载/落地页链接"
    source_reference = "Zenodo / HuggingFace / Figshare / NCBI GEO — 外部开放 API"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        max_results = int(input_data.get("max_results") or 10)
        max_results = max(1, min(max_results, 20))
        data_spec = input_data.get("data_spec") if isinstance(input_data.get("data_spec"), dict) else {}
        research_domain = str(
            input_data.get("research_field") or input_data.get("research_domain") or ""
        ).strip()

        search_query = build_experiment_dataset_search_query(input_data)
        if not search_query:
            result.success = False
            result.add_warning("缺少实验检索关键词，无法检索公开数据集")
            result.data = {
                "datasets": [],
                "total": 0,
                "search_query": "",
                "search_source": "live_api",
                "live_apis": [],
            }
            return result

        keywords = input_data.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = []

        ext_skill = ExternalDatasetSearchSkill()
        ext_result = await ext_skill.run(
            input_data={
                "research_question": search_query,
                "dataset_keywords": keywords,
                "data_spec": data_spec,
                "research_domain": research_domain,
            },
            context=context,
        )

        ext_data = ext_result.data if isinstance(ext_result.data, dict) else {}
        candidates = ext_data.get("candidates") or []
        datasets = [_map_candidate_to_dataset(c) for c in candidates if isinstance(c, dict)]
        datasets = [d for d in datasets if d.get("dataset_name")][:max_results]

        result.data = {
            "datasets": datasets,
            "total": len(datasets),
            "search_query": ext_data.get("search_query") or search_query,
            "search_source": "live_api",
            "live_apis": ext_data.get("live_apis") or [],
            "research_field": ext_data.get("research_field"),
        }
        result.warnings.extend(ext_result.warnings or [])
        if not datasets:
            result.add_warning(
                "未检索到与当前实验需求匹配的公开数据集；请细化实验描述后重试，或手动上传数据。"
            )
        return result
