"""Batch 6 — Feedback Hub / Data Catalog / Entity Resolution / Multimodal ER"""
import csv
import os
import tempfile
import unittest

from app.services.feedback_hub_service import FeedbackHubService
from app.skills.data_finder.entity_resolution_skill import EntityResolutionSkill
from app.skills.evidence_reasoning._utils import fact_to_evidence, is_verifiable_source


class TestBatch6FeedbackHub(unittest.TestCase):
    def test_submit_and_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = FeedbackHubService()
            svc.storage_root = tmp
            pid = "test-proj"
            res = svc.submit_feedback(
                pid,
                source="provenance",
                message="列 age 单位应为年",
                target="data_finder",
            )
            self.assertTrue(res["global_constraints"])
            constraints = svc.get_active_constraints(pid)
            self.assertGreaterEqual(len(constraints), 1)

    def test_record_hitl_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = FeedbackHubService()
            svc.storage_root = tmp
            pid = "hitl-proj"
            res = svc.record_hitl_feedback(
                pid,
                stage="hypothesis_review",
                message="加强对照实验描述",
            )
            self.assertEqual(res["entry"]["source"], "hitl")
            self.assertEqual(res["entry"]["target"], "hypothesis")
            constraints = svc.get_active_constraints(pid)
            self.assertTrue(any("对照实验" in c for c in constraints))


class TestBatch6MultimodalEvidence(unittest.TestCase):
    def test_multimodal_fact_verifiable(self):
        fact = {
            "fact_id": "mm_1",
            "modality": "image",
            "asset_id": "asset_abc",
            "content": "图表显示准确率随轮次上升",
            "source_paper_title": "Multimodal asset",
        }
        self.assertTrue(is_verifiable_source(fact, []))
        ev = fact_to_evidence(fact, "support", "federated learning", [])
        self.assertIsNotNone(ev)
        self.assertEqual(ev.get("source_type"), "multimodal")


class TestBatch6EntityResolution(unittest.IsolatedAsyncioTestCase):
    async def test_entity_match_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "a.csv")
            p2 = os.path.join(tmp, "b.csv")
            with open(p1, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["client_id", "acc"])
                w.writerow(["c1", "0.9"])
                w.writerow(["c2", "0.8"])
            with open(p2, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["client_id", "loss"])
                w.writerow(["c1", "0.1"])
                w.writerow(["c3", "0.2"])

            skill = EntityResolutionSkill()
            res = await skill.run(
                {
                    "tables": [
                        {"table_id": "t1", "csv_path": p1, "columns": ["client_id", "acc"]},
                        {"table_id": "t2", "csv_path": p2, "columns": ["client_id", "loss"]},
                    ],
                    "alignments": [],
                },
                {},
            )
            data = res.data or {}
            self.assertFalse(data.get("skipped"))
            self.assertGreater(data.get("match_rate", 0), 0)


if __name__ == "__main__":
    unittest.main()
