"""Phase 2 — 外部数据源 / 表格抽取 / join 合并 / registry"""
import asyncio
import csv
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.services.data_sources.registry import search_all
from app.skills.data_finder.dataset_merge_skill import DatasetMergeSkill
from app.skills.data_finder.tabular_file_extraction_skill import TabularFileExtractionSkill


class TestTabularExtraction(unittest.TestCase):
    def test_csv_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "sample.csv")
            with open(src, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "value"])
                writer.writeheader()
                writer.writerows([{"id": "1", "value": "10"}, {"id": "2", "value": "20"}])

            skill = TabularFileExtractionSkill()
            res = asyncio.run(skill.run(
                {"file_path": src, "source_title": "Test CSV", "output_dir": tmp},
                {},
            ))
            tables = res.data.get("tables") or []
            self.assertEqual(len(tables), 1)
            self.assertEqual(tables[0]["row_count"], 2)
            self.assertIn("id", tables[0]["columns"])


class TestDatasetMergeJoin(unittest.TestCase):
    def test_join_merge_by_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            t1 = os.path.join(tmp, "a.csv")
            t2 = os.path.join(tmp, "b.csv")
            with open(t1, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["patient_id", "age"])
                w.writeheader()
                w.writerow({"patient_id": "P1", "age": "30"})
            with open(t2, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["patient_id", "score"])
                w.writeheader()
                w.writerow({"patient_id": "P1", "score": "0.9"})

            tables = [
                {"table_id": "t1", "csv_path": t1, "source_title": "A"},
                {"table_id": "t2", "csv_path": t2, "source_title": "B"},
            ]
            alignments = [
                {"table_id": "t1", "mapping": {"patient_id": "patient_id", "age": "age"}, "join_keys": ["patient_id"]},
                {"table_id": "t2", "mapping": {"patient_id": "patient_id", "score": "score"}, "join_keys": ["patient_id"]},
            ]
            skill = DatasetMergeSkill()
            res = asyncio.run(skill.run(
                {
                    "tables": tables,
                    "alignments": alignments,
                    "provenance": [],
                    "output_dir": tmp,
                    "merge_strategy": "join",
                },
                {},
            ))
            self.assertEqual(res.data.get("merge_strategy"), "join")
            self.assertEqual(res.data.get("row_count"), 1)
            merged_path = res.data.get("merged_csv_path")
            self.assertTrue(merged_path and os.path.exists(merged_path))
            with open(merged_path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("patient_id"), "P1")
            self.assertIn("age", rows[0])
            self.assertTrue("score" in rows[0] or "score_t1" in rows[0])


class TestRegistrySearch(unittest.TestCase):
    def test_search_all_uses_connectors(self):
        fake_hit = type("Hit", (), {
            "to_dict": lambda self: {
                "dataset_name": "demo-dataset",
                "source_platform": "huggingface",
                "url": "https://hf.co/datasets/demo",
            },
        })()

        class FakeConn:
            name = "HuggingFace"

            async def search(self, query, spec, limit=5):
                return [fake_hit]

            async def fetch(self, candidate, output_dir):
                return []

        with patch("app.services.data_sources.registry.get_connectors", return_value=[FakeConn()]):
            out = asyncio.run(search_all("protein folding", {"dataset_keywords": ["protein"]}))
        self.assertGreaterEqual(out["count"], 1)
        self.assertEqual(out["candidates"][0]["dataset_name"], "demo-dataset")


if __name__ == "__main__":
    unittest.main()
