"""联邦数据 Schema 识别 Skill — 含 VFL 垂直联邦字段结构"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import (
    FL_METRICS_FIELDS,
    HETEROGENEOUS_FL_FIELDS,
    HORIZONTAL_FL_FIELDS,
    ProjectMode,
    VFL_METRICS,
    VERTICAL_FL_ALIGNMENT_KEYS,
    VERTICAL_FL_FEATURE_OWNER_FIELDS,
    VERTICAL_FL_FIELDS,
    VERTICAL_FL_LABEL_OWNER_FIELDS,
    VERTICAL_FL_PRIVACY_FIELDS,
)
from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment._utils import match_fields, unique_preserve, unique_values_from_preview
from app.skills.federated_experiment.federated_scenario_recognition_skill import (
    FederatedScenarioRecognitionSkill,
)


class FederatedDataSchemaSkill(BaseSkill):
    name = "FederatedDataSchema"
    description = "识别联邦实验 CSV 字段结构（含 vertical_fl）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        columns: List[str] = input_data.get("columns", []) or []
        datasets: List[Dict[str, Any]] = input_data.get("datasets") or []

        scenario_skill = FederatedScenarioRecognitionSkill()
        scenario_res = await scenario_skill.run({"columns": columns}, context)
        fl_setting = scenario_res.data.get("fl_setting", "unknown")

        client_fields = unique_preserve(
            match_fields(columns, HORIZONTAL_FL_FIELDS + HETEROGENEOUS_FL_FIELDS)
        )
        party_fields = unique_preserve(match_fields(columns, VERTICAL_FL_FIELDS))
        metrics_fields = unique_preserve(match_fields(columns, FL_METRICS_FIELDS))
        detected_fields = unique_preserve(client_fields + party_fields + metrics_fields)

        alignment_keys = unique_preserve(match_fields(columns, VERTICAL_FL_ALIGNMENT_KEYS))
        privacy_fields = unique_preserve(match_fields(columns, VERTICAL_FL_PRIVACY_FIELDS))
        feature_owner_cols = unique_preserve(match_fields(columns, VERTICAL_FL_FEATURE_OWNER_FIELDS))
        label_owner_cols = unique_preserve(match_fields(columns, VERTICAL_FL_LABEL_OWNER_FIELDS))

        target_candidates = metrics_fields[:]
        metrics_candidates = list(VFL_METRICS) if fl_setting == "vertical_fl" else metrics_fields[:]
        for pref in (
            "prediction_accuracy", "global_accuracy", "accuracy", "f1_score", "auc",
            "alignment_success_rate", "label",
        ):
            for col in columns:
                if col.lower().replace(" ", "_") == pref and col not in target_candidates:
                    target_candidates.insert(0, col)
            if pref in [m.lower() for m in metrics_candidates]:
                continue
            matched = match_fields(columns, [pref])
            if matched:
                for m in matched:
                    if m not in metrics_candidates:
                        metrics_candidates.insert(0, m)

        parties: List[str] = []
        feature_parties: List[str] = []
        label_party = ""
        preview_rows: List[Dict[str, Any]] = []
        for ds in datasets:
            preview_rows.extend((ds.get("preview") or [])[:50])

        party_col = next((c for c in party_fields if match_fields([c], ["party_id"])), None)
        if not party_col and party_fields:
            party_col = party_fields[0]
        if party_col:
            parties = unique_values_from_preview(preview_rows, party_col)

        fo_col = next((c for c in feature_owner_cols if c), None)
        if fo_col:
            feature_parties = unique_values_from_preview(preview_rows, fo_col) or parties[:]

        lo_col = next((c for c in label_owner_cols if c), None)
        if lo_col:
            lo_vals = unique_values_from_preview(preview_rows, lo_col, limit=3)
            label_party = lo_vals[0] if lo_vals else ""

        payload: Dict[str, Any] = {
            "project_mode": ProjectMode.FEDERATED_LEARNING.value,
            "fl_setting": fl_setting,
            "federated_setting": fl_setting,
            "detected_fields": detected_fields,
            "client_fields": client_fields,
            "party_fields": party_fields,
            "metrics_fields": metrics_fields,
            "target_candidates": target_candidates[:10],
            "metrics_candidates": metrics_candidates[:12],
            "parties": parties,
            "feature_parties": feature_parties or parties,
            "label_party": label_party,
            "alignment_keys": alignment_keys,
            "privacy_fields": privacy_fields,
        }

        if fl_setting == "vertical_fl":
            payload["vfl_detected"] = True
            if not alignment_keys:
                result.add_warning("VFL 场景建议 CSV 包含 entity_id 或 aligned_id 用于样本对齐")

        result.data = payload
        return result
