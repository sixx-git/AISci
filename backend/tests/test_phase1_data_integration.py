"""Phase 1 — DataSpec / 场景预设 / manifest / bundle 扩展"""
import csv
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.core.data_scenario_presets import (
    get_standard_columns_for_scenario,
    project_mode_to_scenario,
)
from app.schemas.data_integration import (
    build_assets_index,
    build_figure_extraction_manifest,
    empty_data_spec,
    merge_data_requirements_legacy,
)
from app.services.data_finder_bundle import build_analysis_bundle
from app.skills.data_finder.data_requirement_understanding_skill import DataRequirementUnderstandingSkill
from app.skills.data_finder.dataset_schema_alignment_skill import DatasetSchemaAlignmentSkill


class TestDataSpec(unittest.TestCase):
    def test_empty_data_spec(self):
        spec = empty_data_spec("研究蛋白质折叠", "general")
        self.assertEqual(spec["scenario"], "general")
        self.assertIn("require_provenance", spec["constraints"])

    def test_legacy_merge(self):
        spec = empty_data_spec("q", "general")
        spec["target_variables"] = ["accuracy"]
        legacy = merge_data_requirements_legacy(spec)
        self.assertEqual(legacy["expected_metrics"], ["accuracy"])

    def test_figure_manifest(self):
        manifest = build_figure_extraction_manifest({
            "figure_id": "fig_1",
            "caption": "Accuracy vs rounds",
            "chart_type": "line",
            "extraction_method": "vlm",
            "extraction_tier": "L3_vlm",
            "extraction_confidence": 0.55,
            "image_path": "/tmp/x.png",
            "review_status": "pending",
        })
        self.assertEqual(manifest["identification"]["chart_type"], "line")
        self.assertIn("validation", manifest)

    def test_assets_index(self):
        assets = build_assets_index({
            "extracted_tables": [{
                "table_id": "t1",
                "csv_path": "/a.csv",
                "columns": ["x"],
                "quality_score": 0.8,
            }],
            "figures": [{
                "figure_id": "f1",
                "extraction_confidence": 0.5,
            }],
        })
        self.assertEqual(len(assets), 2)


class TestScenarioPresets(unittest.TestCase):
    def test_fl_mode_maps_to_scenario(self):
        self.assertEqual(project_mode_to_scenario("federated_learning"), "federated_learning")

    def test_general_columns_include_data_spec(self):
        spec = {"target_variables": ["biomarker_level"], "entities_of_interest": ["patient_id"]}
        cols = get_standard_columns_for_scenario("general", spec)
        self.assertIn("biomarker_level", cols)
        self.assertIn("patient_id", cols)

    def test_fl_columns_include_fl_standard(self):
        cols = get_standard_columns_for_scenario("federated_learning", {})
        self.assertIn("client_id", cols)
        self.assertIn("global_accuracy", cols)


class TestDataRequirementSkill(unittest.IsolatedAsyncioTestCase):
    @patch("app.skills.data_finder.data_requirement_understanding_skill.settings")
    async def test_rule_fallback(self, mock_settings):
        mock_settings.USE_MOCK_LLM = True
        mock_settings.QWEN_API_KEY = ""
        skill = DataRequirementUnderstandingSkill()
        res = await skill.run(
            {
                "research_question": "Compare FedAvg and FedProx accuracy on Non-IID data",
                "project_mode": "federated_learning",
            },
            {},
        )
        self.assertTrue(res.success)
        self.assertIn("data_spec", res.data)
        targets = res.data["data_spec"]["target_variables"]
        self.assertTrue(
            "global_accuracy" in targets or "accuracy" in targets,
            msg=f"unexpected targets: {targets}",
        )

    @patch("app.skills.data_finder.data_requirement_understanding_skill.settings")
    @patch("app.services.qwen_client.qwen_structured_chat")
    async def test_llm_data_spec(self, mock_chat, mock_settings):
        mock_settings.USE_MOCK_LLM = False
        mock_settings.QWEN_API_KEY = "sk-test"
        mock_chat.return_value = {
            "research_question": "Survey attitudes",
            "entities_of_interest": ["respondent_id"],
            "target_variables": ["score"],
            "dataset_keywords": ["survey"],
            "domain_keywords": ["social"],
            "column_synonyms": {},
            "merge_strategy_hint": "stack",
        }
        skill = DataRequirementUnderstandingSkill()
        res = await skill.run(
            {"research_question": "Social survey analysis", "project_mode": "general"},
            {},
        )
        self.assertIn("respondent_id", res.data["data_spec"]["entities_of_interest"])


class TestSchemaAlignmentSkill(unittest.IsolatedAsyncioTestCase):
    async def test_align_with_data_spec(self):
        skill = DatasetSchemaAlignmentSkill()
        res = await skill.run(
            {
                "columns": ["Patient ID", "Biomarker"],
                "project_mode": "general",
                "data_spec": {
                    "scenario": "general",
                    "entities_of_interest": ["patient_id"],
                    "target_variables": ["biomarker"],
                },
            },
            {},
        )
        self.assertIn("patient_id", res.data["join_keys"])


class TestBundlePhase1(unittest.TestCase):
    def test_bundle_includes_data_spec_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            merged_dir = os.path.join(tmp, "merged")
            os.makedirs(merged_dir)
            csv_path = os.path.join(merged_dir, "m.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["method", "accuracy"])
                w.writerow(["A", "0.9"])
            results = {
                "data_spec": empty_data_spec("test", "general"),
                "figures": [{
                    "figure_id": "fig_1",
                    "caption": "Test",
                    "extraction_manifest": build_figure_extraction_manifest({
                        "figure_id": "fig_1",
                        "caption": "Test",
                    }),
                }],
                "merged": {
                    "merge_id": "merged_test",
                    "merged_csv_path": csv_path,
                    "cleaned_csv_path": csv_path,
                    "row_count": 1,
                    "columns": ["method", "accuracy"],
                },
                "provenance": [{"record_id": "r1", "source_title": "Paper"}],
            }
            meta = build_analysis_bundle("proj1", tmp, results)
            self.assertTrue(meta.get("ready"))
            self.assertIn("data_spec.json", meta.get("files", []))
            self.assertIn("figure_manifest.jsonl", meta.get("files", []))
            self.assertIn("assets_index.json", meta.get("files", []))


if __name__ == "__main__":
    unittest.main()
