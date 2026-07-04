"""静态索引连接器 — Kaggle / OpenML 等（catalog_only，不自动 import）"""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.data_sources.base import CandidateHit
from app.skills.data.dataset_discovery_skill import DatasetDiscoverySkill


class CatalogConnector:
    name = "Catalog"

    async def search(
        self,
        query: str,
        data_spec: Dict[str, Any],
        *,
        limit: int = 5,
    ) -> List[CandidateHit]:
        keywords = list(data_spec.get("dataset_keywords") or [])
        keywords.extend(data_spec.get("domain_keywords") or [])
        if data_spec.get("target_variables"):
            keywords.extend(data_spec.get("target_variables") or [])
        if data_spec.get("entities_of_interest"):
            keywords.extend(data_spec.get("entities_of_interest") or [])
        modality_filter = list(data_spec.get("modality_filter") or data_spec.get("modalities") or [])
        from app.core.domain_data_catalog import infer_field_from_text

        research_field = str(data_spec.get("research_field_inferred") or "").strip()
        if not research_field:
            research_field = infer_field_from_text(
                research_domain=str(data_spec.get("research_category") or ""),
                file_description=str(data_spec.get("user_data_notes") or ""),
                research_question=query,
            )
        discovery = DatasetDiscoverySkill()
        res = await discovery.run(
            {
                "research_question": query,
                "keywords": keywords,
                "modality_filter": modality_filter,
                "max_results": limit,
                "research_field": research_field,
            },
            {},
        )
        hits: List[CandidateHit] = []
        for ds in (res.data.get("datasets") or [])[:limit]:
            src = str(ds.get("source", "known_catalog"))
            platform = "Kaggle (curated index)" if "kaggle" in src.lower() else src
            hits.append(CandidateHit(
                source_platform=platform,
                dataset_name=ds.get("dataset_name", ""),
                url=ds.get("url", ""),
                description=(ds.get("description") or "")[:300],
                license=ds.get("license", ""),
                confidence=0.65,
                availability="catalog_only",
                import_supported=False,
                api_type="catalog",
                extra={"catalog_source": src},
            ))
        return hits

    async def fetch(self, candidate: Dict[str, Any], output_dir: str) -> List:
        return []
