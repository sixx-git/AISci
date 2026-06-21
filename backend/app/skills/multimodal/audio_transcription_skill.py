"""音频转写与分析 — 占位实现，不编造转写内容"""
from __future__ import annotations

import logging
import os
import wave
from pathlib import Path
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


class AudioTranscriptionSkill(BaseSkill):
    name = "AudioTranscription"
    description = "音频转写与科研要点提取（当前为占位，需接入 Qwen-Audio/Whisper）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        audio_path = input_data.get("audio_path") or ""
        research_question = input_data.get("research_question") or ""

        if not audio_path or not os.path.exists(audio_path):
            result.data = self._empty_output(["音频路径无效或文件不存在"])
            result.add_error("audio_path 无效")
            return result

        ext = Path(audio_path).suffix.lower()
        if ext not in AUDIO_EXTENSIONS:
            result.data = self._empty_output([f"不支持的音频格式: {ext}"])
            result.add_warning(f"不支持的音频格式: {ext}")
            return result

        meta = self._read_audio_metadata(audio_path, ext)
        warnings: List[str] = [
            "当前未接入 Qwen-Audio / Whisper 转写服务，无法生成 transcript；"
            "请手动上传转写文本或后续接入真实音频模型。"
        ]

        result.data = {
            "modality": "audio",
            "transcript": "",
            "summary": (
                f"音频文件 {Path(audio_path).name} 已上传"
                + (f"，时长约 {meta.get('duration_sec')}s" if meta.get("duration_sec") else "")
                + "；转写未执行。"
            ),
            "key_points": [],
            "research_evidence": [],
            "warnings": warnings,
            "metadata": meta,
            "research_question": research_question[:200],
            "placeholder": True,
        }
        return result

    @staticmethod
    def _read_audio_metadata(audio_path: str, ext: str) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "filename": Path(audio_path).name,
            "size_bytes": os.path.getsize(audio_path),
            "format": ext.lstrip("."),
        }
        if ext == ".wav":
            try:
                with wave.open(audio_path, "rb") as wf:
                    meta["channels"] = wf.getnchannels()
                    meta["sample_rate"] = wf.getframerate()
                    meta["frames"] = wf.getnframes()
                    if wf.getframerate():
                        meta["duration_sec"] = round(wf.getnframes() / wf.getframerate(), 2)
            except Exception as exc:
                meta["read_error"] = str(exc)
        return meta

    @staticmethod
    def _empty_output(warnings: List[str]) -> Dict[str, Any]:
        return {
            "modality": "audio",
            "transcript": "",
            "summary": "",
            "key_points": [],
            "research_evidence": [],
            "warnings": warnings,
            "placeholder": True,
        }
