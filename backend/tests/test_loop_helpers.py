"""Loop Engineering 辅助函数测试"""
from app.core.quality_scoring import enrich_quality_trend_entry
from app.services.loops.closed_loop_helpers import (
    build_data_gap_loop_payload,
    infer_quality_trend_entries,
    summarize_gap_loop,
)


def test_summarize_gap_loop_empty():
    assert summarize_gap_loop(None)["rounds"] == 0


def test_build_data_gap_loop_payload_with_scores():
    gap_loop = [
        {"round": 1, "score_before": 55, "score_after": 72, "import_meta": {"imported_count": 1}},
    ]
    payload = build_data_gap_loop_payload(gap_loop, {"rounds": 1})
    assert payload["executed_rounds"] == 1
    assert payload["quality_trend_entry"]["stage"] == "data_gap_loop"
    assert "72" in payload["summary"]


def test_infer_quality_trend_from_overall():
    entries = infer_quality_trend_entries("ensemble_review", {"overall": 7.5, "round": 2})
    assert len(entries) == 1
    assert entries[0]["score"] == 7.5


def test_infer_quality_trend_evidence_loop():
    entries = infer_quality_trend_entries("evidence_reasoning_loop", {"rounds": 2})
    assert entries[0]["stage"] == "evidence_reasoning"


def test_enrich_gap_loop_cqs():
    raw = {"stage": "data_gap_loop", "score": 72, "raw_score": 72}
    enriched = enrich_quality_trend_entry(raw, "data_gap_loop", {})
    assert enriched["cqs"] == 72.0
