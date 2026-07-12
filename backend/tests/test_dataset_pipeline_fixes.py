"""数据集处理 / Pipeline 续跑 / DB 瘦身相关回归测试。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.services.data_finder_slim import (
    resolve_report_generation_payload,
    slim_data_context,
    slim_stage_output,
)
from app.services.dataset_service import _json_dumps_bounded, _cap_statistics


def test_json_dumps_bounded_truncates_large_payload():
    huge = {"rows": [{"a": "x" * 5000} for _ in range(50)]}
    text = _json_dumps_bounded(huge, max_chars=5000)
    assert len(text) <= 5000
    parsed = json.loads(text)
    assert parsed.get("_truncated") is True


def test_cap_statistics_limits_columns():
    stats = {f"col_{i}": {"mean": i} for i in range(50)}
    capped = _cap_statistics(stats)
    assert len(capped) <= 31
    assert "_truncated_columns" in capped


def test_slim_data_context_strips_full_data_finder():
    ctx = {
        "dataset_count": 1,
        "datasets": [{"dataset_id": "d1", "filename": "a.csv", "file_path": "/tmp/a.csv", "data_type": "tabular", "n_rows": 10, "n_columns": 3, "columns": ["x"]}],
        "data_finder_results": {
            "merged": {"csv_path": "/tmp/m.csv", "row_count": 999, "row_provenance": [{"i": j} for j in range(1000)]},
            "external_candidates": [{"dataset_name": f"ds{i}"} for i in range(50)],
        },
    }
    slim = slim_data_context(ctx)
    assert slim["dataset_count"] == 1
    assert slim["datasets"][0]["filename"] == "a.csv"
    df_json = json.dumps(slim.get("data_finder_results", {}))
    assert '"row_provenance": [' not in df_json
    assert slim["data_finder_results"].get("external_candidates_count") == 50


def test_slim_small_validation_preserves_sandbox_summary():
    huge_script = "x = 1\n" * 50_000
    out = {
        "has_real_data": 1,
        "analysis_script": huge_script,
        "sandbox_execution": {
            "success": True,
            "metrics": {"primary_metric": 0.91, "accuracy": 0.91},
            "plots": [{"plot_id": "p1", "file_path": "/tmp/plot.png", "title": "对比"}],
            "artifact_dir": "/tmp/exp",
            "stdout": "ok" * 5000,
        },
        "artifacts": {
            "plots": [{"plot_id": "p1", "file_path": "/tmp/plot.png"}],
            "metrics": {"primary_metric": 0.91},
        },
    }
    slim = slim_stage_output(out, stage_key="small_validation")
    assert isinstance(slim.get("analysis_script"), dict)
    assert slim["analysis_script"].get("_truncated") is True
    assert slim["sandbox_execution"]["success"] is True
    assert slim["sandbox_execution"]["metrics"]["primary_metric"] == 0.91
    assert len(slim["sandbox_execution"]["plots"]) == 1
    assert slim["artifacts"]["plots"][0]["file_path"] == "/tmp/plot.png"
    assert len(json.dumps(slim, ensure_ascii=False)) < 120_000


def test_slim_stage_output_experiment_design_skill_outputs():
    out = {
        "methods": "m",
        "skill_outputs": {
            "dataset_discovery": {"success": True, "data": {"datasets": [{"name": f"d{i}"} for i in range(20)]}},
        },
    }
    slim = slim_stage_output(out, stage_key="experiment_design")
    ds = slim["skill_outputs"]["dataset_discovery"]["data"]["datasets"]
    assert len(ds) <= 5


def test_slim_stage_output_report_generation_keeps_chapters():
    out = {
        "title": "科学假设与研究计划",
        "paper_title": "联邦学习研究",
        "paper_abstract": "摘要" * 3000,
        "report_id": "file-123",
        "chapters": {
            "problem_statement": "问题" * 5000,
            "methods": "方法",
            "references": [{"id": i} for i in range(120)],
        },
        "plots": [{"title": f"p{i}", "file_path": f"/tmp/{i}.png"} for i in range(30)],
    }
    slim = slim_stage_output(out, stage_key="report_generation")
    assert slim["paper_title"] == "联邦学习研究"
    assert slim["chapters"]["methods"] == "方法"
    assert len(slim["chapters"]["references"]) == 80
    assert slim.get("plots_count") == 30
    assert "_truncated" not in slim


def test_resolve_report_generation_payload_prefers_memory_fallback():
    truncated = {"_truncated": True, "preview": '{"paper_title":"截断标题"}'}
    full = {"paper_title": "完整标题", "chapters": {"methods": "M"}}
    resolved = resolve_report_generation_payload(truncated, memory_fallback=full)
    assert resolved["paper_title"] == "完整标题"


def test_exec_experiment_design_passes_data_files():
    from app.services.pipeline_service import PipelineService

    svc = PipelineService(MagicMock())
    svc._stage_results = {"literature_mining": {"facts": []}}
    svc._validation_feedback_constraints = []
    svc._human_feedback_constraints = []
    svc._last_pilot_results = None

    data_context = {
        "datasets": [
            {"filename": "chembl.csv", "file_path": "/data/chembl.csv", "data_type": "tabular", "n_rows": 100, "n_columns": 5, "columns": ["smiles", "label"]},
        ],
    }
    hr = {
        "reviews": [{"hypothesis": "H1", "rationale": "r", "novelty": "1", "testability": "1", "risk": "low"}],
        "primary_index": 0,
    }

    with patch("app.services.dataset_service.DatasetService") as mock_ds_cls:
        mock_ds = MagicMock()
        mock_ds_cls.return_value = mock_ds
        mock_ds.get_project_data_context.return_value = data_context
        with patch("app.services.pipeline_service.get_experiment_design_agent") as mock_get_agent:
            agent = MagicMock()
            mock_get_agent.return_value = agent
            agent.design_experiment.return_value = {
                "methods": "test",
                "datasets": "",
                "source_data": "",
                "baselines": "",
                "metrics": "",
                "experimental_steps": "",
                "expected_results": "",
                "limitations": "",
            }
            with patch("app.core.iterative_science.build_verifiable_hypothesis_spec_for_mode", return_value={}):
                with patch("app.core.iterative_science.attach_verifiable_specs_to_hypotheses", side_effect=lambda hg, **kw: hg):
                    result = svc._exec_experiment_design(hr, project_id="p1", project_mode="general")

    call_kw = agent.design_experiment.call_args.kwargs
    assert "/data/chembl.csv" in call_kw["data_files"]
    assert call_kw.get("project_datasets")
    assert call_kw["project_datasets"][0]["filename"] == "chembl.csv"
    assert result.get("project_datasets")
    assert result.get("data_gap") == []


def test_format_dataset_schema_prompt_includes_columns():
    from app.agents.experiment_design_agent import ExperimentDesignAgent

    text = ExperimentDesignAgent._format_dataset_schema_prompt([
        {
            "filename": "chembl.csv",
            "file_path": "/data/chembl.csv",
            "data_type": "tabular",
            "n_rows": 1000000,
            "n_columns": 3,
            "missing_rate": 0.01,
            "columns": ["smiles", "label", "id"],
            "dtypes": {"smiles": "VARCHAR", "label": "DOUBLE", "id": "BIGINT"},
        },
    ])
    assert "chembl.csv" in text
    assert "smiles(VARCHAR)" in text
    assert "schema 摘要" in text
    assert "/data/chembl.csv" in text


def test_multimodal_ingest_large_file_uses_probe_metadata(tmp_path):
    import asyncio
    from unittest.mock import patch

    from app.skills.data.multimodal_ingest_skill import MultimodalDataIngestSkill

    csv_path = tmp_path / "big.csv"
    csv_path.write_text("x,y\n0,1\n1,2\n", encoding="utf-8")

    skill = MultimodalDataIngestSkill()
    with patch.object(MultimodalDataIngestSkill, "_is_large_file", return_value=True):
        result = asyncio.run(skill.run(
            input_data={
                "file_paths": [str(csv_path)],
                "known_datasets": [{
                    "filename": "big.csv",
                    "file_path": str(csv_path),
                    "data_type": "tabular",
                    "n_rows": 999999,
                    "n_columns": 2,
                    "columns": ["x", "y"],
                    "dtypes": {"x": "INTEGER", "y": "INTEGER"},
                    "preview": [{"x": 0, "y": 1}],
                    "analysis_tier": "T2",
                }],
            },
            context={"stage": "experiment_design"},
        ))

    assert result.success
    datasets = result.data.get("datasets") or []
    assert len(datasets) == 1
    ds = datasets[0]
    assert ds.get("ingest_mode") == "probe_metadata"
    assert ds.get("columns") == ["x", "y"]
    assert ds.get("n_rows") == 999999
    assert not ds.get("sample_data")
