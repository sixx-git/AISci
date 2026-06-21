"""垂直联邦学习（VFL）Schema 与实验计划测试"""
import asyncio
import unittest

from app.core.project_modes import ProjectMode, get_research_question_template
from app.services.federated_experiment_service import FederatedExperimentService
from app.skills.federated_experiment.federated_data_schema_skill import FederatedDataSchemaSkill


VFL_PREVIEW = [
    {
        "party_id": "bank_a",
        "entity_id": "e001",
        "feature_owner": "bank_a",
        "label_owner": "hospital_b",
        "label": 1,
        "privacy_budget": 1.0,
        "communication_round": 10,
        "prediction_accuracy": 0.88,
    },
    {
        "party_id": "bank_b",
        "entity_id": "e002",
        "feature_owner": "bank_b",
        "label_owner": "hospital_b",
        "label": 0,
        "privacy_budget": 1.0,
        "communication_round": 10,
        "prediction_accuracy": 0.85,
    },
]

VFL_COLUMNS = list(VFL_PREVIEW[0].keys())


class TestVflSchema(unittest.TestCase):
    def test_vfl_research_template(self):
        tpl = get_research_question_template(
            ProjectMode.FEDERATED_LEARNING.value, scenario="vertical_fl"
        )
        self.assertIn("垂直联邦学习", tpl["research_question"])
        self.assertIn("样本对齐", tpl["research_question"])

    def test_vfl_schema_detection(self):
        skill = FederatedDataSchemaSkill()
        result = asyncio.run(
            skill.run(
                {
                    "columns": VFL_COLUMNS,
                    "datasets": [{"preview": VFL_PREVIEW, "filename": "vfl.csv"}],
                },
                {},
            )
        )
        data = result.data
        self.assertEqual(data["fl_setting"], "vertical_fl")
        self.assertEqual(data["federated_setting"], "vertical_fl")
        self.assertTrue(data.get("vfl_detected"))
        self.assertIn("entity_id", data["alignment_keys"])
        self.assertIn("bank_a", data["feature_parties"])
        self.assertEqual(data["label_party"], "hospital_b")
        self.assertIn("privacy_budget", data["privacy_fields"])
        self.assertIn("label", data["target_candidates"])

    def test_vfl_experiment_plan_baselines(self):
        fl_context = asyncio.run(
            FederatedDataSchemaSkill().run(
                {
                    "columns": VFL_COLUMNS,
                    "datasets": [{"preview": VFL_PREVIEW}],
                },
                {},
            )
        ).data
        service = FederatedExperimentService()
        plan = asyncio.run(
            service.build_experiment_plan(
                "VFL improves accuracy under PSI alignment", fl_context
            )
        )
        baselines = plan.get("baselines", [])
        for name in ("SplitNN", "VFL-LR", "VFL-NN", "FedBCD", "SecureBoost"):
            self.assertIn(name, baselines)
        metrics = plan.get("metrics", [])
        self.assertTrue(
            any(m in metrics for m in ("accuracy", "prediction_accuracy", "f1_score"))
        )
        self.assertIn("privacy_leakage_risk", metrics)
        design = service.build_experiment_design_result("vfl hypo", fl_context, plan)
        self.assertIn("SplitNN", design.get("baselines", ""))
        self.assertEqual(design["project_mode"], ProjectMode.FEDERATED_LEARNING.value)

    def test_vfl_report_enrichment(self):
        service = FederatedExperimentService()
        fl_context = {
            "fl_setting": "vertical_fl",
            "feature_parties": ["bank_a", "bank_b"],
            "label_party": "hospital_b",
        }
        plan = asyncio.run(service.build_experiment_plan("test", fl_context))
        design = service.build_experiment_design_result("test", fl_context, plan)
        chapters = service.enrich_report_sections(
            {"problem_statement": "", "experiments": ""},
            fl_context,
            design,
            {"execution_mode": "skipped", "result_source": "none"},
        )
        combined = " ".join(str(v) for v in chapters.values())
        for kw in ("垂直联邦学习", "样本对齐", "特征方", "标签方", "隐私保护"):
            self.assertIn(kw, combined)


if __name__ == "__main__":
    unittest.main()
