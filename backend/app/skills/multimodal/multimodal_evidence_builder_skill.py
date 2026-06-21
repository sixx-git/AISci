"""多模态证据链构建 — 将文本/图像/音频解析结果转为 Evidence Facts"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.core.config import get_settings
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()


class MultimodalEvidenceBuilderSkill(BaseSkill):
    name = "MultimodalEvidenceBuilder"
    description = "从多模态解析结果构建可引用的 evidence facts"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = input_data.get("research_question") or ""
        source_file = input_data.get("source_file") or "unknown"
        asset_id = input_data.get("asset_id") or uuid.uuid4().hex[:8]

        extracted_text = input_data.get("extracted_text") or ""
        image_summary = input_data.get("image_summary") or {}
        audio_transcript = input_data.get("audio_transcript") or {}

        facts: List[Dict[str, Any]] = []

        if extracted_text and str(extracted_text).strip():
            facts.extend(
                self._facts_from_text(
                    str(extracted_text).strip(),
                    source_file,
                    asset_id,
                    research_question,
                )
            )

        if isinstance(image_summary, dict) and image_summary.get("summary"):
            facts.extend(
                self._facts_from_image(image_summary, source_file, asset_id, research_question)
            )

        if isinstance(audio_transcript, dict):
            transcript = (audio_transcript.get("transcript") or "").strip()
            if transcript:
                facts.extend(
                    self._facts_from_audio(audio_transcript, source_file, asset_id, research_question)
                )
            elif audio_transcript.get("summary") and not audio_transcript.get("placeholder"):
                pass
            elif audio_transcript.get("placeholder"):
                for w in audio_transcript.get("warnings") or []:
                    result.add_warning(str(w))

        if not facts and settings.QWEN_API_KEY and not settings.USE_MOCK_LLM:
            facts = self._llm_build_facts(input_data, source_file, asset_id, research_question)

        result.data = {"evidence_facts": facts, "fact_count": len(facts)}
        if not facts:
            result.add_warning("未能从多模态内容提取 evidence facts（可能缺少 VLM/转写）")
        return result

    def _facts_from_text(
        self,
        text: str,
        source_file: str,
        asset_id: str,
        research_question: str,
    ) -> List[Dict[str, Any]]:
        chunks = [text[i : i + 400] for i in range(0, min(len(text), 1200), 400)]
        facts = []
        for idx, chunk in enumerate(chunks):
            facts.append(
                self._make_fact(
                    asset_id=asset_id,
                    idx=idx,
                    modality="text",
                    fact_text=chunk,
                    source_file=source_file,
                    confidence=0.75,
                    relevance=research_question[:120],
                )
            )
        return facts

    def _facts_from_image(
        self,
        image_summary: Dict[str, Any],
        source_file: str,
        asset_id: str,
        research_question: str,
    ) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        summary = image_summary.get("summary") or ""
        if summary and not image_summary.get("metadata_only"):
            facts.append(
                self._make_fact(
                    asset_id=asset_id,
                    idx=0,
                    modality="image",
                    fact_text=summary,
                    source_file=source_file,
                    confidence=0.8 if image_summary.get("possible_research_evidence") else 0.65,
                    relevance=research_question[:120],
                    extra={
                        "chart_type": image_summary.get("chart_type"),
                        "axis_labels": image_summary.get("axis_labels"),
                    },
                )
            )

        for i, ev in enumerate(image_summary.get("possible_research_evidence") or []):
            if not ev:
                continue
            facts.append(
                self._make_fact(
                    asset_id=asset_id,
                    idx=i + 1,
                    modality="image",
                    fact_text=str(ev),
                    source_file=source_file,
                    confidence=0.85,
                    relevance=research_question[:120],
                )
            )

        for i, trend in enumerate(image_summary.get("key_trends") or []):
            if not trend:
                continue
            facts.append(
                self._make_fact(
                    asset_id=asset_id,
                    idx=100 + i,
                    modality="image",
                    fact_text=f"图像趋势: {trend}",
                    source_file=source_file,
                    confidence=0.7,
                    relevance=research_question[:120],
                )
            )
        return facts

    def _facts_from_audio(
        self,
        audio_data: Dict[str, Any],
        source_file: str,
        asset_id: str,
        research_question: str,
    ) -> List[Dict[str, Any]]:
        facts = []
        transcript = audio_data.get("transcript") or ""
        if transcript:
            facts.append(
                self._make_fact(
                    asset_id=asset_id,
                    idx=0,
                    modality="audio",
                    fact_text=transcript[:800],
                    source_file=source_file,
                    confidence=0.8,
                    relevance=research_question[:120],
                )
            )
        for i, pt in enumerate(audio_data.get("research_evidence") or []):
            facts.append(
                self._make_fact(
                    asset_id=asset_id,
                    idx=i + 1,
                    modality="audio",
                    fact_text=str(pt),
                    source_file=source_file,
                    confidence=0.75,
                    relevance=research_question[:120],
                )
            )
        return facts

    @staticmethod
    def _make_fact(
        *,
        asset_id: str,
        idx: int,
        modality: str,
        fact_text: str,
        source_file: str,
        confidence: float,
        relevance: str,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        fid = f"mm_{asset_id}_{idx:03d}"
        fact = {
            "fact_id": fid,
            "modality": modality,
            "fact_text": fact_text,
            "content": fact_text,
            "source_file": source_file,
            "source_type": "multimodal_asset",
            "source_paper_title": f"{source_file} ({modality})",
            "confidence": round(confidence, 3),
            "relevance_to_question": relevance,
            "relevance_score": round(confidence * 0.9, 3),
        }
        if extra:
            fact["extra"] = extra
        return fact

    @staticmethod
    def _llm_build_facts(
        input_data: Dict[str, Any],
        source_file: str,
        asset_id: str,
        research_question: str,
    ) -> List[Dict[str, Any]]:
        try:
            raw = qwen_structured_chat(
                prompt=(
                    f"研究问题: {research_question}\n"
                    f"源文件: {source_file}\n"
                    f"文本: {(input_data.get('extracted_text') or '')[:800]}\n"
                    f"图像摘要: {input_data.get('image_summary')}\n"
                    "请输出 evidence_facts 数组，每项含 fact_text, modality, confidence(0-1), relevance_to_question。"
                    "不得编造未提供的内容。"
                ),
                schema_example={"evidence_facts": []},
                prompt_version="multimodal_evidence_builder",
            )
            items = raw.get("evidence_facts") or []
            facts = []
            for i, item in enumerate(items[:5]):
                if not item.get("fact_text"):
                    continue
                facts.append(
                    MultimodalEvidenceBuilderSkill._make_fact(
                        asset_id=asset_id,
                        idx=i,
                        modality=item.get("modality") or "text",
                        fact_text=item["fact_text"],
                        source_file=source_file,
                        confidence=float(item.get("confidence") or 0.6),
                        relevance=item.get("relevance_to_question") or research_question[:120],
                    )
                )
            return facts
        except Exception as exc:
            logger.warning(f"LLM multimodal evidence 构建失败: {exc}")
            return []
