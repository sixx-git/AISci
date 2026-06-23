"""数据连接器注册表"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.data_sources.base import CandidateHit, DataSourceConnector, FetchedAsset


_REGISTRY: List[DataSourceConnector] = []


def register_connector(connector: DataSourceConnector) -> None:
    if connector not in _REGISTRY:
        _REGISTRY.append(connector)


def get_connectors() -> List[DataSourceConnector]:
    if not _REGISTRY:
        _bootstrap()
    return list(_REGISTRY)


def _bootstrap() -> None:
    from app.services.data_sources.catalog_connector import CatalogConnector
    from app.services.data_sources.hf_connector import HuggingFaceConnector
    from app.services.data_sources.repository_connector import RepositoryConnector

    register_connector(HuggingFaceConnector())
    register_connector(RepositoryConnector())
    register_connector(CatalogConnector())


async def search_all(
    query: str,
    data_spec: Optional[Dict[str, Any]] = None,
    *,
    limit_per_source: int = 5,
) -> Dict[str, Any]:
    spec = data_spec or {}
    candidates: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for conn in get_connectors():
        try:
            hits = await conn.search(query, spec, limit=limit_per_source)
            candidates.extend([h.to_dict() for h in hits])
        except Exception as exc:
            warnings.append(f"{conn.name} 检索失败: {exc}")

    dedup: List[Dict[str, Any]] = []
    seen = set()
    for c in candidates:
        key = (c.get("dataset_name") or c.get("url") or "").lower()
        if key and key not in seen:
            seen.add(key)
            dedup.append(c)

    return {"candidates": dedup[:25], "warnings": warnings, "count": len(dedup)}


async def fetch_candidate(
    candidate: Dict[str, Any],
    output_dir: str,
) -> List[FetchedAsset]:
    platform = (candidate.get("source_platform") or "").lower()
    for conn in get_connectors():
        if conn.name.lower() in platform or platform in conn.name.lower():
            return await conn.fetch(candidate, output_dir)
        if "huggingface" in platform and conn.name == "HuggingFace":
            return await conn.fetch(candidate, output_dir)
        if any(x in platform for x in ("zenodo", "figshare", "dryad")) and conn.name == "Repository":
            return await conn.fetch(candidate, output_dir)
    return []


async def fetch_many(
    candidates: List[Dict[str, Any]],
    output_dir: str,
    *,
    max_fetch: int = 2,
) -> Dict[str, Any]:
    imported: List[Dict[str, Any]] = []
    errors: List[str] = []
    for cand in candidates[:max_fetch]:
        try:
            assets = await fetch_candidate(cand, output_dir)
            for asset in assets:
                item = asset.to_dict() if hasattr(asset, "to_dict") else asset
                imported.append(item if isinstance(item, dict) else {
                    "local_path": asset.local_path,
                    "source_type": asset.source_type,
                    "columns": asset.columns,
                    "row_count": asset.row_count,
                })
                cand["imported"] = True
                cand["imported_csv_path"] = asset.local_path
        except Exception as exc:
            errors.append(str(exc))
    return {"imported": imported, "imported_count": len(imported), "errors": errors}
