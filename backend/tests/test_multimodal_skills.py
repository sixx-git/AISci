"""多模态 Skill 单元测试"""
import asyncio

from app.skills.multimodal.audio_transcription_skill import AudioTranscriptionSkill
from app.skills.multimodal.multimodal_evidence_builder_skill import MultimodalEvidenceBuilderSkill
from app.skills.multimodal.qwen_vl_image_understanding_skill import QwenVlImageUnderstandingSkill


def test_audio_skill_no_fabricated_transcript(tmp_path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 40)

    async def _run():
        skill = AudioTranscriptionSkill()
        return await skill.run(
            {"audio_path": str(wav), "research_question": "测试"},
            {},
        )

    result = asyncio.run(_run())
    data = result.data
    assert data["transcript"] == ""
    assert data.get("placeholder") is True
    assert any("未接入" in w or "Qwen-Audio" in w for w in (data.get("warnings") or []))


def test_multimodal_evidence_builder_from_text():
    async def _run():
        skill = MultimodalEvidenceBuilderSkill()
        return await skill.run(
            {
                "asset_id": "abc123",
                "source_file": "notes.txt",
                "research_question": "Ia 型超新星",
                "extracted_text": "光变曲线显示峰值后快速衰减。",
                "image_summary": {},
                "audio_transcript": {},
            },
            {},
        )

    result = asyncio.run(_run())
    facts = result.data.get("evidence_facts") or []
    assert len(facts) >= 1
    assert facts[0]["modality"] == "text"
    assert facts[0]["fact_id"].startswith("mm_")


def test_image_skill_missing_file():
    async def _run():
        skill = QwenVlImageUnderstandingSkill()
        return await skill.run(
            {"image_path": "/nonexistent/chart.png", "research_question": "test"},
            {},
        )

    result = asyncio.run(_run())
    assert result.data.get("warnings")
