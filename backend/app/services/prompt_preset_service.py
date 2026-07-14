"""Prompt 范式预设库 — 读取 presets/manifest.json 与模板文件"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.prompt_override_service import get_prompt_override_service

_PRESETS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "presets"
_MANIFEST_PATH = _PRESETS_DIR / "manifest.json"

EXCLUDED_PRESET_STAGES = frozenset({"report_generation"})


class PromptPresetService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._manifest: Optional[Dict[str, Any]] = None

    def _load_manifest(self) -> Dict[str, Any]:
        if self._manifest is None:
            if not _MANIFEST_PATH.is_file():
                raise FileNotFoundError(f"缺少预设清单: {_MANIFEST_PATH}")
            self._manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        return self._manifest

    def reload_manifest(self) -> None:
        self._manifest = None

    def get_catalog(self, *, project_mode: str = "general") -> Dict[str, Any]:
        manifest = self._load_manifest()
        packs: List[Dict[str, Any]] = []
        for pack in manifest.get("packs", []):
            if pack.get("requires_federated"):
                continue
            packs.append({
                "id": pack["id"],
                "label": pack["label"],
                "description": pack.get("description", ""),
                "reference": pack.get("reference"),
                "recommended_pipeline_mode": pack.get("recommended_pipeline_mode"),
                "requires_federated": bool(pack.get("requires_federated")),
                "stages": pack.get("stages", {}),
            })
        return {
            "version": manifest.get("version", 1),
            "excluded_stages": list(manifest.get("excluded_stages", [])),
            "excluded_reason": manifest.get("excluded_reason", ""),
            "packs": packs,
            "default_pack_id": "pack_c",
        }

    def get_preset_content(self, pack_id: str, stage: str, variant_id: str) -> Dict[str, Any]:
        if stage in EXCLUDED_PRESET_STAGES:
            raise ValueError(f"阶段 {stage} 不提供范式预设")
        manifest = self._load_manifest()
        pack = next((p for p in manifest.get("packs", []) if p["id"] == pack_id), None)
        if not pack:
            raise ValueError(f"未知范式包: {pack_id}")
        stage_variants = (pack.get("stages") or {}).get(stage) or []
        variant = next((v for v in stage_variants if v["id"] == variant_id), None)
        if not variant:
            raise ValueError(f"未知变体: {pack_id}/{stage}/{variant_id}")
        rel_file = variant["file"]
        path = _PRESETS_DIR / rel_file.replace("/", "\\") if "\\" in rel_file else _PRESETS_DIR / rel_file
        if not path.is_file():
            raise FileNotFoundError(path)
        content = path.read_text(encoding="utf-8")
        return {
            "pack_id": pack_id,
            "pack_label": pack.get("label"),
            "stage": stage,
            "variant_id": variant_id,
            "variant_label": variant.get("label"),
            "description": variant.get("description"),
            "content": content,
        }

    def apply_preset(
        self,
        project_id: str,
        pack_id: str,
        variant_id: str,
        *,
        stage: Optional[str] = None,
        apply_all_stages: bool = False,
    ) -> Dict[str, Any]:
        if not self.db:
            raise RuntimeError("apply_preset 需要数据库会话")
        if stage and stage in EXCLUDED_PRESET_STAGES:
            raise ValueError("报告生成阶段不可应用范式预设")
        manifest = self._load_manifest()
        pack = next((p for p in manifest.get("packs", []) if p["id"] == pack_id), None)
        if not pack:
            raise ValueError(f"未知范式包: {pack_id}")

        stages_map: Dict[str, List[Dict[str, Any]]] = pack.get("stages") or {}
        targets: List[str] = []
        if apply_all_stages:
            targets = list(stages_map.keys())
        elif stage:
            if not variant_id:
                raise ValueError("单阶段应用须提供 variant_id")
            if stage not in stages_map:
                raise ValueError(f"范式包 {pack_id} 不包含阶段 {stage}")
            targets = [stage]
        else:
            raise ValueError("须指定 stage 或 apply_all_stages=true")

        override_svc = get_prompt_override_service(self.db)
        applied: List[Dict[str, str]] = []
        for st in targets:
            variants = stages_map.get(st) or []
            if not variants:
                continue
            if apply_all_stages:
                var = variants[0]
            else:
                var = next((v for v in variants if v["id"] == variant_id), None)
                if not var:
                    raise ValueError(f"变体 {variant_id} 不适用于阶段 {st}")
            rel = var["file"]
            path = _PRESETS_DIR / rel
            template = path.read_text(encoding="utf-8")
            override_svc.save_override(project_id, st, template)
            applied.append({
                "stage": st,
                "variant_id": var["id"],
                "variant_label": var.get("label", ""),
            })

        return {
            "project_id": project_id,
            "pack_id": pack_id,
            "variant_id": variant_id,
            "applied": applied,
            "count": len(applied),
        }


def get_prompt_preset_service(db: Optional[Session] = None) -> PromptPresetService:
    return PromptPresetService(db)
