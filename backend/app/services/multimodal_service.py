"""多模态资产解析与 Evidence Facts 服务"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.research import MultimodalAsset, Dataset
from app.schemas.research import MultimodalAssetResponse
from app.skills.multimodal import (
    QwenVlImageUnderstandingSkill,
    AudioTranscriptionSkill,
    MultimodalEvidenceBuilderSkill,
)

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".jsonl"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".webp", ".gif"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


def detect_modality(filename: str, data_type: Optional[str] = None) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_EXTENSIONS or data_type == "image":
        return "image"
    if ext in AUDIO_EXTENSIONS or (data_type == "time_series" and ext in {".wav"}):
        return "audio"
    if ext in TEXT_EXTENSIONS or data_type in ("json", "tabular"):
        return "text"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return "text"


class MultimodalService:
    def __init__(self, db: Session):
        self.db = db

    def to_response(self, asset: MultimodalAsset) -> MultimodalAssetResponse:
        facts = []
        meta = {}
        if asset.evidence_facts_json:
            try:
                facts = json.loads(asset.evidence_facts_json)
            except json.JSONDecodeError:
                facts = []
        if asset.metadata_json:
            try:
                meta = json.loads(asset.metadata_json)
            except json.JSONDecodeError:
                meta = {}
        return MultimodalAssetResponse(
            id=asset.id,
            project_id=asset.project_id,
            dataset_id=asset.dataset_id,
            file_name=asset.file_name,
            file_path=asset.file_path,
            modality=asset.modality,
            mime_type=asset.mime_type,
            extracted_text=asset.extracted_text,
            extracted_summary=asset.extracted_summary,
            evidence_facts=facts,
            metadata=meta,
            parse_status=asset.parse_status or "pending",
            use_for_hypothesis=bool(asset.use_for_hypothesis),
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        )

    def list_assets(self, project_id: str) -> List[MultimodalAsset]:
        return (
            self.db.query(MultimodalAsset)
            .filter(MultimodalAsset.project_id == project_id)
            .order_by(MultimodalAsset.created_at.desc())
            .all()
        )

    def get_asset(self, asset_id: str) -> Optional[MultimodalAsset]:
        return self.db.query(MultimodalAsset).filter(MultimodalAsset.id == asset_id).first()

    def create_and_parse(
        self,
        project_id: str,
        file_path: str,
        file_name: str,
        research_question: str = "",
        *,
        dataset_id: Optional[str] = None,
        data_type: Optional[str] = None,
        use_for_hypothesis: bool = True,
    ) -> MultimodalAsset:
        modality = detect_modality(file_name, data_type)
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        asset = MultimodalAsset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            dataset_id=dataset_id,
            file_name=file_name,
            file_path=file_path,
            modality=modality,
            mime_type=mime_type,
            parse_status="processing",
            use_for_hypothesis=use_for_hypothesis,
        )
        self.db.add(asset)
        self.db.commit()

        try:
            parsed = asyncio.run(
                self._parse_asset(asset, research_question)
            )
            asset.extracted_text = parsed.get("extracted_text")
            asset.extracted_summary = parsed.get("extracted_summary")
            asset.evidence_facts_json = json.dumps(
                parsed.get("evidence_facts") or [], ensure_ascii=False
            )
            asset.metadata_json = json.dumps(
                parsed.get("metadata") or {}, ensure_ascii=False, default=str
            )
            asset.parse_status = parsed.get("parse_status") or "completed"
        except Exception as exc:
            logger.error(f"多模态解析失败 {file_name}: {exc}", exc_info=True)
            asset.parse_status = "failed"
            asset.metadata_json = json.dumps({"error": str(exc)}, ensure_ascii=False)

        self.db.commit()
        self.db.refresh(asset)
        return asset

    async def _parse_asset(self, asset: MultimodalAsset, research_question: str) -> Dict[str, Any]:
        modality = asset.modality
        file_path = asset.file_path
        file_name = asset.file_name

        extracted_text = ""
        image_summary: Dict[str, Any] = {}
        audio_transcript: Dict[str, Any] = {}
        metadata: Dict[str, Any] = {"modality": modality}
        parse_status = "completed"

        if modality == "text":
            extracted_text = self._read_text_file(file_path)
            metadata["char_count"] = len(extracted_text)

        elif modality == "image":
            skill = QwenVlImageUnderstandingSkill()
            res = await skill.run(
                {
                    "image_path": file_path,
                    "research_question": research_question,
                    "context": file_name,
                },
                {"stage": "multimodal_image"},
            )
            image_summary = res.data or {}
            asset_summary = image_summary.get("summary") or ""
            metadata["image_understanding"] = image_summary
            if image_summary.get("metadata_only"):
                parse_status = "warning"
            if image_summary.get("warnings"):
                metadata["warnings"] = image_summary["warnings"]

        elif modality == "audio":
            skill = AudioTranscriptionSkill()
            res = await skill.run(
                {"audio_path": file_path, "research_question": research_question},
                {"stage": "multimodal_audio"},
            )
            audio_transcript = res.data or {}
            metadata["audio_analysis"] = audio_transcript
            parse_status = "warning"
            if audio_transcript.get("warnings"):
                metadata["warnings"] = audio_transcript["warnings"]

        builder = MultimodalEvidenceBuilderSkill()
        build_res = await builder.run(
            {
                "asset_id": asset.id.replace("-", "")[:12],
                "source_file": file_name,
                "research_question": research_question,
                "extracted_text": extracted_text,
                "image_summary": image_summary,
                "audio_transcript": audio_transcript,
            },
            {"stage": "multimodal_evidence"},
        )
        evidence_facts = (build_res.data or {}).get("evidence_facts") or []

        summary_parts = []
        if extracted_text:
            summary_parts.append(extracted_text[:300])
        if image_summary.get("summary"):
            summary_parts.append(image_summary["summary"][:300])
        if audio_transcript.get("summary"):
            summary_parts.append(audio_transcript["summary"][:300])

        return {
            "extracted_text": extracted_text or None,
            "extracted_summary": " | ".join(summary_parts)[:600] if summary_parts else None,
            "evidence_facts": evidence_facts,
            "metadata": metadata,
            "parse_status": parse_status if evidence_facts else ("warning" if parse_status != "failed" else parse_status),
        }

    @staticmethod
    def _read_text_file(file_path: str, max_chars: int = 12000) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in {".json", ".jsonl"}:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read(max_chars)
                return raw
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(max_chars)
        except Exception as exc:
            logger.warning(f"读取文本失败: {exc}")
            return ""

    def reparse_asset(self, asset_id: str, research_question: str = "") -> Optional[MultimodalAsset]:
        asset = self.get_asset(asset_id)
        if not asset:
            return None
        asset.parse_status = "processing"
        self.db.commit()
        parsed = asyncio.run(self._parse_asset(asset, research_question))
        asset.extracted_text = parsed.get("extracted_text")
        asset.extracted_summary = parsed.get("extracted_summary")
        asset.evidence_facts_json = json.dumps(parsed.get("evidence_facts") or [], ensure_ascii=False)
        asset.metadata_json = json.dumps(parsed.get("metadata") or {}, ensure_ascii=False, default=str)
        asset.parse_status = parsed.get("parse_status") or "completed"
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def toggle_hypothesis(self, asset_id: str) -> Optional[MultimodalAsset]:
        asset = self.get_asset(asset_id)
        if not asset:
            return None
        asset.use_for_hypothesis = not bool(asset.use_for_hypothesis)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_project_evidence_facts(self, project_id: str) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        for asset in self.list_assets(project_id):
            if not asset.use_for_hypothesis:
                continue
            if not asset.evidence_facts_json:
                continue
            try:
                items = json.loads(asset.evidence_facts_json)
                if isinstance(items, list):
                    facts.extend(items)
            except json.JSONDecodeError:
                continue
        return facts

    def get_multimodal_context(self, project_id: str) -> Dict[str, Any]:
        assets = self.list_assets(project_id)
        facts = self.get_project_evidence_facts(project_id)
        return {
            "multimodal_asset_count": len(assets),
            "multimodal_evidence_count": len(facts),
            "multimodal_evidence": facts,
            "multimodal_assets": [self.to_response(a).model_dump() for a in assets[:20]],
            "modalities_present": list({a.modality for a in assets}),
        }

    def sync_from_dataset(
        self,
        dataset: Dataset,
        research_question: str = "",
    ) -> Optional[MultimodalAsset]:
        modality = detect_modality(dataset.filename, dataset.data_type)
        if modality not in ("text", "image", "audio"):
            return None
        existing = (
            self.db.query(MultimodalAsset)
            .filter(MultimodalAsset.dataset_id == dataset.id)
            .first()
        )
        if existing:
            return existing
        return self.create_and_parse(
            project_id=dataset.project_id,
            file_path=dataset.file_path,
            file_name=dataset.filename,
            research_question=research_question,
            dataset_id=dataset.id,
            data_type=dataset.data_type,
            use_for_hypothesis=bool(dataset.use_for_hypothesis),
        )


def get_multimodal_service(db: Session) -> MultimodalService:
    return MultimodalService(db)
