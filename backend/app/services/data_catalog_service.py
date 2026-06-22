"""项目级数据目录 — 统一 provenance / schema / used_by_stages"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class DataCatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.storage_root = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "catalog",
        )

    def _catalog_path(self, project_id: str) -> str:
        directory = os.path.join(self.storage_root, project_id)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, "data_catalog.json")

    def build_catalog(self, project_id: str) -> Dict[str, Any]:
        assets: List[Dict[str, Any]] = []

        from app.services.dataset_service import DatasetService

        ds_service = DatasetService(self.db)
        try:
            ctx = ds_service.build_data_context(project_id)
        except Exception as exc:
            logger.warning("DataCatalog 加载 data_context 失败: %s", exc)
            ctx = {}

        for ds in ctx.get("datasets") or []:
            assets.append({
                "asset_id": ds.get("dataset_id") or ds.get("id"),
                "type": ds.get("data_type") or "tabular",
                "filename": ds.get("filename"),
                "path": ds.get("file_path"),
                "provenance": {
                    "source": ds.get("source") or "user_upload",
                    "columns": ds.get("columns") or ds.get("column_names"),
                },
                "schema": {"columns": ds.get("columns") or []},
                "quality_report": ds.get("quality_report") or {},
                "used_by_stages": self._infer_stages(ds),
            })

        try:
            from app.services.data_finder_service import get_data_finder_service

            df = get_data_finder_service(self.db).load_results(project_id) or {}
            merged = df.get("merged") or {}
            csv_path = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
            if csv_path:
                assets.append({
                    "asset_id": merged.get("merge_id") or "data_finder_merged",
                    "type": "merged_csv",
                    "path": csv_path,
                    "provenance": {
                        "source": "data_finder",
                        "provenance_records": (df.get("provenance") or [])[:10],
                        "coverage_score": (df.get("coverage_report") or {}).get("completeness_score"),
                    },
                    "schema": {"columns": merged.get("columns") or []},
                    "quality_report": merged.get("cleaning_report") or {},
                    "used_by_stages": ["hypothesis_generation", "experiment_design", "small_validation"],
                })
            bundle = df.get("analysis_bundle") or {}
            if bundle.get("ready"):
                assets.append({
                    "asset_id": "analysis_bundle",
                    "type": "bundle",
                    "path": bundle.get("bundle_zip_path") or bundle.get("bundle_path"),
                    "provenance": {"source": "data_finder_bundle"},
                    "used_by_stages": ["report_generation", "external_export"],
                })
        except Exception as exc:
            logger.warning("DataCatalog data_finder 部分失败: %s", exc)

        for mm in ctx.get("multimodal_assets") or []:
            assets.append({
                "asset_id": mm.get("asset_id") or mm.get("id"),
                "type": mm.get("modality") or "multimodal",
                "filename": mm.get("filename"),
                "path": mm.get("file_path"),
                "provenance": {"source": "multimodal_upload"},
                "used_by_stages": ["hypothesis_generation", "evidence_reasoning"],
            })

        catalog = {
            "project_id": project_id,
            "generated_at": datetime.now(CHINA_TZ).isoformat(),
            "asset_count": len(assets),
            "assets": assets,
            "summary": {
                "tabular_count": sum(1 for a in assets if a.get("type") in ("tabular", "merged_csv")),
                "multimodal_count": sum(1 for a in assets if a.get("type") in ("image", "audio", "multimodal")),
                "bundle_ready": any(a.get("type") == "bundle" for a in assets),
            },
        }
        path = self._catalog_path(project_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2, default=str)
        catalog["catalog_path"] = path
        return catalog

    @staticmethod
    def _infer_stages(ds: Dict[str, Any]) -> List[str]:
        stages = ["hypothesis_generation"]
        if ds.get("use_for_hypothesis"):
            stages.append("experiment_design")
        source = (ds.get("source") or "").lower()
        if "data_finder" in source:
            stages.extend(["small_validation", "report_generation"])
        return list(dict.fromkeys(stages))

    def load_catalog(self, project_id: str) -> Optional[Dict[str, Any]]:
        path = self._catalog_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def get_data_catalog_service(db: Session) -> DataCatalogService:
    return DataCatalogService(db)
