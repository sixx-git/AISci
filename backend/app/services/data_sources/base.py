"""多源数据连接器基础类型"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class CandidateHit:
    source_platform: str
    dataset_name: str
    url: str = ""
    description: str = ""
    license: str = ""
    confidence: float = 0.5
    record_id: str = ""
    availability: str = "search_and_import"  # search_and_import | url_only | catalog_only | metadata_only
    import_supported: bool = True
    size_hint_bytes: Optional[int] = None
    api_type: str = "live"  # live | catalog | metadata
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "source_platform": self.source_platform,
            "dataset_name": self.dataset_name,
            "url": self.url,
            "description": self.description,
            "license": self.license,
            "confidence": self.confidence,
            "availability": self.availability,
            "import_supported": self.import_supported,
            "api_type": self.api_type,
        }
        if self.record_id:
            d["record_id"] = self.record_id
        if self.size_hint_bytes is not None:
            d["size_hint_bytes"] = self.size_hint_bytes
        d.update(self.extra)
        return d


def normalize_legacy_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """为旧格式 external_candidates 补全 availability 字段。"""
    c = dict(candidate)
    platform = (c.get("source_platform") or "").lower()
    if "availability" in c and "import_supported" in c:
        return c
    if "kaggle" in platform or c.get("api_type") == "catalog":
        c.setdefault("availability", "catalog_only")
        c.setdefault("import_supported", False)
        c.setdefault("api_type", "catalog")
    elif "openalex" in platform or "pubmed" in platform:
        c.setdefault("availability", "reference_only")
        c.setdefault("import_supported", False)
        c.setdefault("api_type", "metadata")
    elif "geo" in platform or "ncbi" in platform:
        c.setdefault("availability", "metadata_only")
        c.setdefault("import_supported", False)
        c.setdefault("api_type", "metadata")
    elif c.get("url") and not c.get("import_supported", True):
        c.setdefault("availability", "url_only")
    else:
        c.setdefault("availability", "search_and_import")
        c.setdefault("import_supported", True)
        c.setdefault("api_type", c.get("api_type", "live"))
    return c


@dataclass
class FetchedAsset:
    source_type: str
    source_title: str
    local_path: str
    file_kind: str  # csv | xlsx | pdf | zip | other
    url: str = ""
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    extraction_method: str = ""
    confidence: float = 0.6

    def to_table_dict(self, table_id: str, paper_id: str = "") -> Dict[str, Any]:
        return {
            "table_id": table_id,
            "paper_id": paper_id,
            "source_title": self.source_title,
            "page": 0,
            "caption": f"External: {self.source_title}",
            "csv_path": self.local_path if self.file_kind == "csv" else "",
            "columns": self.columns,
            "row_count": self.row_count,
            "quality_score": self.confidence,
            "extraction_method": self.extraction_method or self.source_type,
            "source_type": self.source_type,
        }


@runtime_checkable
class DataSourceConnector(Protocol):
    name: str

    async def search(
        self,
        query: str,
        data_spec: Dict[str, Any],
        *,
        limit: int = 5,
    ) -> List[CandidateHit]: ...

    async def fetch(
        self,
        candidate: Dict[str, Any],
        output_dir: str,
    ) -> List[FetchedAsset]: ...
