"""数据溯源 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class DataProvenanceSkill(BaseSkill):
    name = "DataProvenance"
    description = "为每条数据源记录 provenance"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        records = input_data.get("records", []) or []
        provenance_list: List[Dict[str, Any]] = []

        for rec in records:
            prov = {
                "source_type": rec.get("source_type", "paper_table"),
                "source_title": rec.get("source_title", ""),
                "paper_id": rec.get("paper_id", ""),
                "page": rec.get("page"),
                "table_or_figure": rec.get("table_or_figure") or rec.get("table_id") or rec.get("figure_id", ""),
                "url": rec.get("url", ""),
                "extraction_method": rec.get("extraction_method", ""),
                "confidence": rec.get("confidence", rec.get("quality_score", 0.0)),
                "record_id": rec.get("record_id") or rec.get("table_id") or rec.get("figure_id", ""),
            }
            provenance_list.append(prov)

        result.data = {
            "provenance": provenance_list,
            "count": len(provenance_list),
            "all_have_source_title": all(p.get("source_title") for p in provenance_list) if provenance_list else False,
        }
        return result
