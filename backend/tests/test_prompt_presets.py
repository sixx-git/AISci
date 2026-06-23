"""Prompt 范式预设测试"""
import unittest

from app.services.prompt_preset_service import PromptPresetService, EXCLUDED_PRESET_STAGES


class TestPromptPresets(unittest.TestCase):
    def setUp(self):
        self.svc = PromptPresetService()

    def test_catalog_general_excludes_pack_d(self):
        catalog = self.svc.get_catalog(project_mode="general")
        pack_ids = [p["id"] for p in catalog["packs"]]
        self.assertIn("pack_a", pack_ids)
        self.assertIn("pack_b", pack_ids)
        self.assertIn("pack_c", pack_ids)
        self.assertNotIn("pack_d", pack_ids)
        self.assertIn("report_generation", catalog["excluded_stages"])

    def test_catalog_federated_includes_pack_d(self):
        catalog = self.svc.get_catalog(project_mode="federated_learning")
        pack_ids = [p["id"] for p in catalog["packs"]]
        self.assertIn("pack_d", pack_ids)

    def test_load_pack_a_hypothesis_bold_idea(self):
        data = self.svc.get_preset_content("pack_a", "hypothesis_generation", "bold_idea")
        self.assertIn("AI Scientist", data["content"])
        self.assertIn("{{research_question}}", data["content"])

    def test_report_generation_excluded(self):
        with self.assertRaises(ValueError):
            self.svc.get_preset_content("pack_c", "report_generation", "anything")

    def test_pack_d_only_three_stages(self):
        catalog = self.svc.get_catalog(project_mode="federated_learning")
        pack_d = next(p for p in catalog["packs"] if p["id"] == "pack_d")
        self.assertEqual(
            set(pack_d["stages"].keys()),
            {"hypothesis_generation", "experiment_design", "small_validation"},
        )

    def test_excluded_stages_constant(self):
        self.assertIn("report_generation", EXCLUDED_PRESET_STAGES)


if __name__ == "__main__":
    unittest.main()
