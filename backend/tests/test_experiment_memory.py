"""跨会话实验记忆单测（独立 mem_store，不依赖项目投影）。"""
from unittest.mock import MagicMock, patch

from app.services.experiment_memory import (
    build_record_from_shaxiang_experiment,
    format_guidance,
    maybe_save_from_shaxiang,
    retrieve_guidance,
)


def _exp(exp_id="sx-1", acc_base=0.5, acc_best=0.7):
    return {
        "id": exp_id,
        "shaxiang_experiment_id": exp_id,
        "project_id": "proj-mem",
        "title": "FL fall detection",
        "hypothesis": "Federated learning with synthetic data improves fall detection accuracy.",
        "research_goal": "Improve elderly fall detection under FL",
        "status": "completed",
        "initial_plan": {"title": "train FL classifier"},
        "iterations": [
            {"metrics": {"accuracy": acc_base}, "status": "success"},
            {"metrics": {"accuracy": acc_best}, "status": "success"},
        ],
    }


def test_build_record_labels_positive():
    with patch("app.services.experiment_memory._settings") as st:
        st.return_value = MagicMock(
            EXPERIMENT_MEMORY_AGGREGATION="best",
            EXPERIMENT_MEMORY_IMPROVE_THRESHOLD=0.05,
        )
        rec = build_record_from_shaxiang_experiment(_exp(), scope_key="proj-mem")
    assert rec is not None
    assert rec.label == 1
    assert rec.primary_metric in ("accuracy",)
    assert rec.success is True


def test_save_and_retrieve_without_projection(tmp_path):
    mem_dir = tmp_path / "experiment_memory"
    with patch("app.services.experiment_memory._settings") as st:
        st.return_value = MagicMock(
            EXPERIMENT_MEMORY_SAVE_ENABLED=True,
            EXPERIMENT_MEMORY_RETRIEVE_ENABLED=True,
            EXPERIMENT_MEMORY_DIR=str(mem_dir),
            EXPERIMENT_MEMORY_AGGREGATION="best",
            EXPERIMENT_MEMORY_IMPROVE_THRESHOLD=0.05,
            EXPERIMENT_MEMORY_TOP_K=5,
            EXPERIMENT_MEMORY_ALPHA=1.0,
        )
        with patch("app.services.experiment_memory._memory_root", return_value=mem_dir):
            saved = maybe_save_from_shaxiang(_exp("sx-ok", 0.4, 0.8), scope_key="proj-a")
            assert saved is not None
            # 失败方向
            maybe_save_from_shaxiang(_exp("sx-bad", 0.8, 0.5), scope_key="proj-a")
            pack = retrieve_guidance(
                "proj-a",
                "federated learning fall detection synthetic data",
            )
    assert pack["enabled"] is True
    assert pack["count"] >= 1
    assert "Historical" in pack["guidance"] or "Reference" in pack["guidance"] or "Avoid" in pack["guidance"]
    # 确认写在独立 mem_store，而非 iterative_experiments
    assert (mem_dir / "proj-a" / "records.json").exists()
    assert not (tmp_path / "iterative_experiments").exists()


def test_save_disabled_noop(tmp_path):
    with patch("app.services.experiment_memory._settings") as st:
        st.return_value = MagicMock(
            EXPERIMENT_MEMORY_SAVE_ENABLED=False,
            EXPERIMENT_MEMORY_DIR=str(tmp_path / "mem"),
        )
        assert maybe_save_from_shaxiang(_exp(), scope_key="p") is None


def test_format_guidance_sections():
    text = format_guidance(
        [
            {"label": 1, "hypothesis": "Good H", "primary_metric": "accuracy"},
            {"label": -1, "hypothesis": "Bad H", "primary_metric": "accuracy"},
        ]
    )
    assert "Reference" in text
    assert "Avoid" in text
    assert "Good H" in text
    assert "Bad H" in text
