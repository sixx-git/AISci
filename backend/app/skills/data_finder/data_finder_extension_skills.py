"""数据查找扩展 Skill — 别名与封装"""
from __future__ import annotations

from typing import Any, Dict

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill
from app.skills.data_finder.pdf_table_extraction_skill import PdfTableExtractionSkill


class ScientificDataSearchSkill(BaseSkill):
    name = "ScientificDataSearch"
    description = "根据研究目标搜索公开数据集"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = ExternalDatasetSearchSkill()
        return await inner.run(input_data, context)


class TableExtractionSkill(BaseSkill):
    name = "TableExtraction"
    description = "从 PDF 表格抽取 CSV"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = PdfTableExtractionSkill()
        return await inner.run(input_data, context)
