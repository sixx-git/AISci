"""可验证假设、结构化 replan 与 Campaign 迭代测试"""
import asyncio
import unittest

from app.core.iterative_science import (
    VFL_ALIGNMENT_MIN_RATE,
    actions_to_feedback_constraints,
    build_campaign_lineage_text,
    build_structured_replan_actions,
    build_verifiable_hypothesis_spec,
    check_vfl_alignment_gate,
)
from app.services.latex_export_service import build_latex_document, get_latex_template_dir
from app.skills.federated_experiment.federated_replanning_skill import FederatedReplanningSkill


VFL_PREVIEW = [
    {"entity_id": "e1", "party_id": "a", "feature_owner": "a", "label_owner": "h", "label": 1},
    {"entity_id": "e2", "party_id": "b", "feature_owner": "b", "label_owner": "h", "label": 0},
]


class TestIterativeScience(unittest.TestCase):
    def test_vfl_alignment_gate_pass(self):
        gate = check_vfl_alignment_gate(
            {"fl_setting": "vertical_fl", "alignment_keys": ["entity_id"]},
            [{"preview": VFL_PREVIEW}],
        )
        self.assertTrue(gate["passed"])
        self.assertGreaterEqual(gate["alignment_success_rate"], VFL_ALIGNMENT_MIN_RATE)

    def test_vfl_alignment_gate_fail_missing_keys(self):
        gate = check_vfl_alignment_gate({"fl_setting": "vertical_fl"}, [])
        self.assertFalse(gate["passed"])

    def test_structured_replan_actions_skipped(self):
        actions = build_structured_replan_actions(
            {"execution_mode": "skipped"},
            {"fl_setting": "vertical_fl"},
        )
        self.assertTrue(any(a.get("priority") == "critical" for a in actions))
        self.assertTrue(all(a.get("expected_check") for a in actions))

    def test_actions_to_feedback_constraints(self):
        actions = [{"parameter": "privacy_budget", "to_value": 1.0, "expected_check": "risk↓", "rationale": "test"}]
        lines = actions_to_feedback_constraints(actions)
        self.assertEqual(len(lines), 1)
        self.assertIn("验收条件", lines[0])

    def test_campaign_subsections_for_latex(self):
        spec = build_verifiable_hypothesis_spec("VFL hypo", {"baselines": ["SplitNN"]}, {"fl_setting": "vertical_fl"})
        subs = build_campaign_lineage_text(
            {"execution_mode": "simulation", "best_method": "SplitNN", "metric_comparison": []},
            build_structured_replan_actions({"execution_mode": "simulation", "best_method": "SplitNN"}, {"fl_setting": "vertical_fl"}),
            verifiable_spec=spec,
        )
        self.assertIn("### 可验证科学假设表述", subs["methods"])
        self.assertIn("### 下一轮结构化 Replan Actions", subs["experiments"])

        latex = build_latex_document(
            result={
                "paper_title": "VFL Campaign Test",
                "paper_abstract": "摘要",
                "chapters": {
                    "problem_statement": "问题",
                    "rationale": "思路",
                    "technical_details": "技术",
                    "datasets": "数据",
                    "source": "源",
                    "target": "目标",
                    "methods": subs["methods"],
                    "experiments": subs["experiments"],
                    "results": subs["results"],
                },
            },
            template_dir=get_latex_template_dir(),
        )
        self.assertIn("\\section{待研究问题}", latex)
        self.assertIn("\\section{实验设计}", latex)
        self.assertNotIn("\\section{Campaign", latex)
        self.assertIn("\\subsection{可验证科学假设表述}", latex)
        self.assertIn("\\subsection{下一轮结构化 Replan Actions}", latex)

    def test_replanning_skill_returns_actions(self):
        skill = FederatedReplanningSkill()
        res = asyncio.run(
            skill.run(
                {
                    "pilot_result": {"execution_mode": "gate_blocked", "alignment_gate": {"passed": False}},
                    "fl_setting": "vertical_fl",
                    "fl_context": {"fl_setting": "vertical_fl"},
                },
                {},
            )
        )
        self.assertGreater(len(res.data.get("replan_actions", [])), 0)
        self.assertTrue(res.data.get("has_critical_actions"))

    def test_pareto_frontier(self):
        from app.core.iterative_science import compute_pareto_frontier, evaluate_pilot_improvement, needs_federated_campaign_refinement

        comp = [
            {"method": "A", "global_accuracy": 0.9, "communication_cost_mb": 200},
            {"method": "B", "global_accuracy": 0.85, "communication_cost_mb": 100},
            {"method": "C", "global_accuracy": 0.88, "communication_cost_mb": 150},
        ]
        pf = compute_pareto_frontier(comp)
        self.assertGreaterEqual(len(pf["frontier"]), 1)

        needs, reasons = needs_federated_campaign_refinement(
            {"federated_pilot": {"execution_mode": "simulation", "replan_actions": []}}
        )
        self.assertTrue(needs)

        imp = evaluate_pilot_improvement(
            {"execution_mode": "skipped", "metric_comparison": []},
            {"execution_mode": "simulation", "metric_comparison": [{"method": "X", "global_accuracy": 0.7}]},
        )
        self.assertTrue(imp["improved"])


if __name__ == "__main__":
    unittest.main()
