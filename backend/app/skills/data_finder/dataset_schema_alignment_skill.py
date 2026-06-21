"""数据集字段对齐 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import ProjectMode
from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import FL_STANDARD_COLUMNS, GENERAL_STANDARD_COLUMNS, match_column_mapping, normalize_col


class DatasetSchemaAlignmentSkill(BaseSkill):
    name = "DatasetSchemaAlignment"
    description = "将多源字段映射到标准 schema"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        columns = input_data.get("columns", []) or []
        project_mode = input_data.get("project_mode", ProjectMode.GENERAL.value)

        standard = list(GENERAL_STANDARD_COLUMNS)
        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            standard = list(dict.fromkeys(FL_STANDARD_COLUMNS + GENERAL_STANDARD_COLUMNS))

        mapping = match_column_mapping(columns, standard)
        standard_columns = sorted(set(mapping.values()))
        unmatched = [c for c in columns if c not in mapping]

        unit_conversion: Dict[str, str] = {}
        for orig, std in mapping.items():
            ol = normalize_col(orig)
            if "percent" in ol or ol.endswith("_pct"):
                unit_conversion[orig] = f"{std}: scale 0-100 -> 0-1 if needed"
            elif std in ("communication_cost_mb",) and "kb" in ol:
                unit_conversion[orig] = f"{orig}: KB -> MB divide by 1024"

        result.data = {
            "original_columns": columns,
            "standard_columns": standard_columns,
            "mapping": mapping,
            "unit_conversion": unit_conversion,
            "unmatched_columns": unmatched,
            "project_mode": project_mode,
        }
        return result
