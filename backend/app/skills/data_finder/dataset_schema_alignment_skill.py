"""数据集字段对齐 Skill — DataSpec + 场景预设驱动"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.data_scenario_presets import (
    get_column_synonyms,
    get_standard_columns_for_scenario,
    project_mode_to_scenario,
)
from app.core.project_modes import ProjectMode
from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import match_column_mapping, normalize_col


class DatasetSchemaAlignmentSkill(BaseSkill):
    name = "DatasetSchemaAlignment"
    description = "将多源字段映射到 DataSpec 与场景预设标准 schema"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        columns = input_data.get("columns", []) or []
        project_mode = input_data.get("project_mode", ProjectMode.GENERAL.value)
        data_spec = input_data.get("data_spec") or {}
        scenario = data_spec.get("scenario") or project_mode_to_scenario(project_mode)

        standard = get_standard_columns_for_scenario(scenario, data_spec)
        synonyms = get_column_synonyms(data_spec)

        mapping = match_column_mapping(columns, standard)

        # 应用 DataSpec 列同义词
        norm_cols = {normalize_col(c): c for c in columns}
        used_orig = set(mapping.keys())
        for std, syns in synonyms.items():
            for syn in syns:
                nc = normalize_col(syn)
                if nc in norm_cols:
                    orig = norm_cols[nc]
                    if orig not in used_orig:
                        mapping[orig] = std
                        used_orig.add(orig)

        standard_columns = sorted(set(mapping.values()))
        unmatched = [c for c in columns if c not in mapping]

        unit_conversion: Dict[str, str] = {}
        for orig, std in mapping.items():
            ol = normalize_col(orig)
            if "percent" in ol or ol.endswith("_pct"):
                unit_conversion[orig] = f"{std}: scale 0-100 -> 0-1 if needed"
            elif std in ("communication_cost_mb",) and "kb" in ol:
                unit_conversion[orig] = f"{orig}: KB -> MB divide by 1024"

        join_keys = [
            c for c in standard_columns
            if c in (data_spec.get("entities_of_interest") or [])
        ]
        merge_strategy = data_spec.get("merge_strategy_hint", "auto")
        if merge_strategy == "auto":
            merge_strategy = "join" if join_keys and len(columns) > 0 else "stack"

        result.data = {
            "original_columns": columns,
            "standard_columns": standard_columns,
            "mapping": mapping,
            "unit_conversion": unit_conversion,
            "unmatched_columns": unmatched,
            "project_mode": project_mode,
            "scenario": scenario,
            "join_keys": join_keys,
            "merge_strategy": merge_strategy,
        }
        return result
