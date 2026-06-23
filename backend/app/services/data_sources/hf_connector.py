"""HuggingFace 数据连接器"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.services.data_sources.base import CandidateHit, FetchedAsset
from app.services.external_dataset_import_service import import_huggingface_candidate
from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill


class HuggingFaceConnector:
    name = "HuggingFace"

    async def search(
        self,
        query: str,
        data_spec: Dict[str, Any],
        *,
        limit: int = 5,
    ) -> List[CandidateHit]:
        res = ExternalDatasetSearchSkill._search_huggingface(query)
        hits: List[CandidateHit] = []
        for item in (res.get("results") or [])[:limit]:
            hits.append(CandidateHit(
                source_platform=item.get("source_platform", "HuggingFace Datasets"),
                dataset_name=item.get("dataset_name", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                license=item.get("license", ""),
                confidence=float(item.get("confidence", 0.75)),
                availability="search_and_import",
                import_supported=True,
                api_type="live",
            ))
        return hits

    async def fetch(
        self,
        candidate: Dict[str, Any],
        output_dir: str,
    ) -> List[FetchedAsset]:
        meta = import_huggingface_candidate(candidate, output_dir)
        return [FetchedAsset(
            source_type="hf_dataset",
            source_title=meta.get("dataset_name", "HF Dataset"),
            local_path=meta["csv_path"],
            file_kind="csv",
            url=candidate.get("url", ""),
            columns=meta.get("columns") or [],
            row_count=int(meta.get("row_count") or 0),
            extraction_method=meta.get("import_method", "hf_auto_import"),
            confidence=0.72,
        )]
