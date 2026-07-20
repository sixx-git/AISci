"""FL Starter Pack 服务与挂载测试。"""
from __future__ import annotations

from app.core.data_scenario_presets import get_standard_columns_for_scenario, project_mode_to_scenario
from app.core.project_modes import normalize_project_mode
from app.services.fl_pack_service import FlPackService, get_fl_pack_service
from app.services.prompt_preset_service import PromptPresetService


def test_fl_pack_available_and_seed_facts():
    svc = get_fl_pack_service()
    assert svc.available()
    facts = svc.load_seed_facts()
    assert len(facts) >= 40
    assert any("FedAvg" in str(f.get("method") or "") or "fedavg" in str(f.get("fact_id") or "").lower() for f in facts)
    for dom in (
        "llm_ft",
        "smart_care",
        "smart_transport",
        "finance_risk",
        "edge_mobile",
        "iot_industrial",
        "privacy_crypto",
        "fl_cv",
        "fl_nlp",
        "fl_multilingual",
        "fl_blockchain",
        "fl_rl",
        "fl_continual",
        "fl_lora_hetero",
    ):
        assert any(f.get("domain") == dom for f in facts), f"missing domain {dom}"


def test_domain_filter_keeps_core():
    svc = get_fl_pack_service()
    llm_only = svc.load_seed_facts(domains=["llm_ft"])
    assert llm_only
    assert all(f.get("domain") in ("fl_core", "llm_ft") for f in llm_only)
    assert any(f.get("domain") == "llm_ft" for f in llm_only)
    assert any(f.get("domain") == "fl_core" for f in llm_only)
    care = svc.mount_to_project_config({}, fl_setting="hfl", domains=["smart_care"])
    assert "smart_care" in (care.get("fl_domains") or [])
    assert care["fl_pack"]["seed_facts_count"] >= 5


def test_dataset_hints_and_scripts():
    svc = get_fl_pack_service()
    hints = svc.dataset_guidance_hints()
    assert len(hints) >= 3
    assert any(h.get("download_url") for h in hints)
    scripts = svc.load_scripts()
    assert any(s.get("exists") for s in scripts)
    ctx = svc.scripts_context_for_llm()
    assert "FedAvg" in ctx or "hfl" in ctx.lower() or "脚本" in ctx


def test_project_mode_and_scenario():
    assert normalize_project_mode("federated_learning") == "federated_learning"
    assert project_mode_to_scenario("federated_learning") == "federated_learning"
    cols = get_standard_columns_for_scenario("federated_learning")
    assert "client_id" in cols
    assert "global_accuracy" in cols


def test_catalog_pack_d_only_for_fl():
    svc = PromptPresetService()
    general = svc.get_catalog(project_mode="general")
    assert "pack_d" not in [p["id"] for p in general["packs"]]
    fl = svc.get_catalog(project_mode="federated_learning")
    assert "pack_d" in [p["id"] for p in fl["packs"]]
    assert fl["default_pack_id"] == "pack_d"


def test_infer_fl_context_hfl_and_vfl():
    hfl = FlPackService.infer_fl_context_from_columns(
        ["client_id", "label", "x1"], project_mode="federated_learning"
    )
    assert hfl["fl_setting"] == "horizontal_fl"
    vfl = FlPackService.infer_fl_context_from_columns(
        ["entity_id", "party_id", "feat_a"], project_mode="federated_learning"
    )
    assert vfl["fl_setting"] == "vertical_fl"
    gate = get_fl_pack_service().maybe_attach_vfl_gate(vfl)
    assert gate.get("gate") == "vfl_alignment"


def test_local_fedavg_pilot_runs():
    out = get_fl_pack_service().run_local_fedavg_pilot(timeout_sec=90)
    assert out.get("success") is True
    assert isinstance(out.get("metrics"), dict)
    assert "global_accuracy" in out["metrics"] or "primary_metric" in out["metrics"]


def test_hfl_vfl_seed_split_and_normalized_fields():
    svc = get_fl_pack_service()
    hfl = svc.load_seed_facts(fl_setting="hfl")
    vfl = svc.load_seed_facts(fl_setting="vfl")
    assert hfl and vfl
    assert any(f.get("source_chunk_id") and f.get("document_id") and f.get("content") for f in hfl)
    # VFL 不应混入明显 HFL-only attack 综述（setting=hfl）
    assert not any("backdoor" in str(f.get("method") or "").lower() for f in vfl)
    vfl_scripts = svc.list_script_templates(fl_setting="vfl", limit=5)
    assert any("vfl" in (s.get("setting") or "") or "vfl" in (s.get("path") or "") for s in vfl_scripts)


def test_mount_respects_fl_setting():
    cfg = get_fl_pack_service().mount_to_project_config({}, fl_setting="vfl")
    assert cfg["fl_setting"] == "vfl"
    assert cfg["fl_pack"]["fl_setting"] == "vfl"
    assert cfg["fl_pack"]["seed_facts_count"] == len(cfg["fl_pack"]["seed_facts"])
    for f in cfg["fl_pack"]["seed_facts"]:
        assert f.get("content")
        assert f.get("source_chunk_id")


def test_standard_non_iid_experiment_profile():
    svc = get_fl_pack_service()
    profile = svc.get_experiment_profile("standard_non_iid")
    assert profile.get("id") == "standard_non_iid"
    assert (profile.get("partition") or {}).get("method") == "dirichlet"
    assert "FedProx" in ((profile.get("baselines") or {}).get("required") or [])
    ctx = svc.build_experiment_paradigm_context(fl_setting="hfl", profile_id="standard_non_iid")
    assert "dirichlet" in ctx.lower() or "Dirichlet" in ctx
    assert "FedProx" in ctx
    cfg = svc.mount_to_project_config({}, fl_setting="hfl", profile_id="standard_non_iid")
    assert cfg["fl_experiment_profile"] == "standard_non_iid"
    assert cfg["fl_pack"].get("experiment_paradigm_context")
    templates = svc.list_script_templates(fl_setting="hfl", limit=3, profile_id="standard_non_iid")
    ids = " ".join(str(t.get("id") or "") for t in templates)
    assert "dirichlet" in ids or "baseline_compare" in ids


def test_dirichlet_and_baseline_scripts_exist_and_run():
    import json
    import subprocess
    import sys

    root = get_fl_pack_service().root / "scripts"
    dirichlet = root / "hfl_dirichlet_partition.py"
    compare = root / "hfl_baseline_compare_pilot.py"
    assert dirichlet.is_file() and compare.is_file()
    csv_path = root / "_test_dirichlet.csv"
    metrics_path = root / "_test_dirichlet_metrics.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(dirichlet),
            "--alpha",
            "0.1",
            "--clients",
            "5",
            "--rows",
            "200",
            "--out_csv",
            str(csv_path),
            "--out_metrics",
            str(metrics_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert data.get("partition_method") == "dirichlet"
    compare_out = root / "_test_baseline_metrics.json"
    proc2 = subprocess.run(
        [
            sys.executable,
            str(compare),
            "--clients",
            "5",
            "--rows",
            "200",
            "--rounds",
            "3",
            "--out",
            str(compare_out),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert proc2.returncode == 0, proc2.stderr
    m2 = json.loads(compare_out.read_text(encoding="utf-8"))
    assert "FedProx" in (m2.get("baselines") or [])
    assert "methods" in m2
