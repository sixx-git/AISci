"""结构化文件统一抽取 — 按格式路由至表格 / 化学结构等 Skill。"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder.chem_structure_extraction_skill import ChemStructureExtractionSkill
from app.skills.data_finder.file_format_registry import detect_file_format, is_chemistry_format, is_fits_format
from app.skills.data_finder.fits_extraction_skill import FitsExtractionSkill
from app.skills.data_finder.tabular_file_extraction_skill import TabularFileExtractionSkill


class StructuredFileExtractionSkill(BaseSkill):
    name = "StructuredFileExtraction"
    description = "统一解析 CSV/JSON/ZIP/SDF/MOL/SMILES 等结构化数据文件"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        file_path = input_data.get("file_path", "")
        filename = input_data.get("filename") or os.path.basename(file_path or "")

        if is_chemistry_format(filename):
            return await ChemStructureExtractionSkill().run(input_data, context)

        if is_fits_format(filename):
            return await FitsExtractionSkill().run(input_data, context)

        fmt = detect_file_format(filename)
        if fmt == "tabular" or fmt in {"csv", "tsv", "json", "jsonl"} or os.path.splitext(filename)[1] in {
            ".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".jsonl",
        }:
            return await TabularFileExtractionSkill().run(input_data, context)

        result = SkillResult(success=True)
        result.add_warning(f"未识别的文件格式: {filename}")
        result.data = {"tables": []}
        return result


async def extract_tables_from_file(
    file_path: str,
    *,
    source_title: str,
    output_dir: str,
    filename: str | None = None,
    max_records: int | None = None,
    context: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """供上传服务调用的便捷入口。"""
    payload: Dict[str, Any] = {
        "file_path": file_path,
        "source_title": source_title,
        "output_dir": output_dir,
        "filename": filename or os.path.basename(file_path),
    }
    if max_records is not None:
        payload["max_records"] = max_records

    if is_chemistry_format(payload["filename"]):
        skill = ChemStructureExtractionSkill()
    elif is_fits_format(payload["filename"]):
        skill = FitsExtractionSkill()
    else:
        skill = StructuredFileExtractionSkill()

    res = await skill.run(payload, context or {})
    return list(res.data.get("tables") or [])
