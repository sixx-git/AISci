"""假设演化候选池单测（1B：不覆盖主假设）。"""
from copy import deepcopy
from unittest.mock import MagicMock, patch

from app.skills.reasoning.hypothesis_evolution_skill import (
    attach_evolution_to_review,
    evolve_hypothesis_candidates,
)


def _reviews():
    return [
        {
            "hypothesis": "Federated learning with synthetic fall data improves elderly safety.",
            "overall_score": 8.2,
            "suggestions": ["clarify domain gap"],
        },
        {
            "hypothesis": "Use GAN to generate rare fall events for FL training.",
            "overall_score": 7.1,
        },
    ]


def test_evolve_disabled_skips():
    reviews = _reviews()
    before = deepcopy(reviews)
    with patch("app.core.config.get_settings") as gs:
        gs.return_value = MagicMock(
            HYPOTHESIS_EVOLUTION_ENABLED=False,
            HYPOTHESIS_EVOLUTION_TOP_K=5,
            HYPOTHESIS_EVOLUTION_STRATEGIES="simplify,out_of_box",
        )
        out = evolve_hypothesis_candidates(
            research_question="FL fall detection",
            reviews=reviews,
            primary_index=0,
            enabled=False,
        )
    assert out["enabled"] is False
    assert out["default_unchanged"] is True
    assert out["candidates"] == []
    assert reviews == before


def test_evolve_produces_candidates_without_mutating_reviews():
    reviews = _reviews()
    before = deepcopy(reviews)

    def fake_llm(*, prompt, schema_example=None, prompt_version="", **kwargs):
        if "simplify" in str(prompt_version):
            return {
                "hypothesis": "Simplified FL fall claim.",
                "rationale": "easier pilot",
                "parent_indices": [0],
            }
        return {
            "hypothesis": "Analogy-based new FL sensing hypothesis.",
            "rationale": "out of box",
            "parent_indices": [0, 1],
        }

    with patch("app.core.config.get_settings") as gs:
        gs.return_value = MagicMock(
            HYPOTHESIS_EVOLUTION_ENABLED=True,
            HYPOTHESIS_EVOLUTION_TOP_K=5,
            HYPOTHESIS_EVOLUTION_STRATEGIES="simplify,out_of_box",
        )
        with patch(
            "app.services.qwen_client.qwen_structured_chat",
            side_effect=fake_llm,
        ):
            with patch(
                "app.services.prompt_loader.get_prompt_loader"
            ) as gpl:
                loader = MagicMock()
                loader.render_template.side_effect = (
                    lambda name, vars: f"prompt {name} {vars.get('hypothesis','')}"
                )
                gpl.return_value = loader
                out = evolve_hypothesis_candidates(
                    research_question="federated fall detection",
                    reviews=reviews,
                    primary_index=0,
                    pro_con_evolution={"revision_points": ["fix domain gap"]},
                )

    assert out["enabled"] is True
    assert out["default_unchanged"] is True
    strategies = {c["strategy"] for c in out["candidates"]}
    assert "simplify" in strategies
    assert "out_of_box" in strategies
    assert reviews == before  # 输入未被原地改写


def test_attach_evolution_does_not_change_primary_hypothesis():
    review = {
        "reviews": [{"hypothesis": "Original H0", "overall_score": 8}],
        "primary_index": 0,
        "skill_outputs": {},
    }
    evo = {
        "enabled": True,
        "candidates": [
            {
                "candidate_id": "evo_simplify_0",
                "strategy": "simplify",
                "hypothesis": "Simplified",
            }
        ],
        "default_unchanged": True,
    }
    attached = attach_evolution_to_review(review, evo)
    assert attached["reviews"][0]["hypothesis"] == "Original H0"
    assert attached["skill_outputs"]["hypothesis_evolution"]["candidates"]


def test_select_evolved_hypothesis_writes_primary():
    from app.services.stage_human_loop_service import StageHumanLoopService

    reviews = [{"hypothesis": "Original H0", "overall_score": 8}]
    output = {
        "reviews": reviews,
        "primary_index": 0,
        "skill_outputs": {
            "hypothesis_evolution": {
                "enabled": True,
                "candidates": [
                    {
                        "candidate_id": "evo_simplify_0",
                        "strategy": "simplify",
                        "hypothesis": "Adopted simplified hypothesis",
                    }
                ],
                "default_unchanged": True,
            }
        },
    }

    stage_exec = MagicMock()
    stage_exec.output_data = output
    stage_exec.extra_metadata = {}

    run = MagicMock()
    run.id = "db-id"
    run.run_id = "run-1"
    run.project_id = "proj-1"
    run.extra_metadata = {"pipeline_checkpoint": {"results": {"hypothesis_review": output}}}

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.first.return_value = stage_exec

    svc = StageHumanLoopService(db)
    with patch.object(svc, "save_human_edit", return_value=stage_exec) as save:
        with patch.object(svc, "_get_run", return_value=run):
            result = svc.select_evolved_hypothesis(
                "run-1", candidate_id="evo_simplify_0"
            )

    assert result["hypothesis"] == "Adopted simplified hypothesis"
    assert result["previous_hypothesis"] == "Original H0"
    assert stage_exec.output_data["reviews"][0]["hypothesis"] == "Adopted simplified hypothesis"
    assert (
        stage_exec.output_data["skill_outputs"]["hypothesis_evolution"]["selected_candidate_id"]
        == "evo_simplify_0"
    )
    save.assert_called_once()
