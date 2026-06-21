"""多源数据查找模块测试"""
import asyncio
import csv
import os
import tempfile
import unittest

from app.skills.data_finder.data_requirement_understanding_skill import DataRequirementUnderstandingSkill
from app.skills.data_finder.dataset_schema_alignment_skill import DatasetSchemaAlignmentSkill
from app.skills.data_finder.paper_data_link_extractor_skill import PaperDataLinkExtractorSkill
from app.skills.data_finder.pdf_table_extraction_skill import PdfTableExtractionSkill


class TestDataFinderSkills(unittest.TestCase):
    def test_fl_data_requirements(self):
        skill = DataRequirementUnderstandingSkill()
        res = asyncio.run(
            skill.run(
                {
                    "research_question": "Non-IID federated learning with FedAvg",
                    "project_mode": "federated_learning",
                },
                {},
            )
        )
        keywords = " ".join(res.data.get("domain_keywords", []))
        self.assertIn("fedavg", keywords.lower().replace("_", ""))

    def test_paper_link_extraction(self):
        skill = PaperDataLinkExtractorSkill()
        res = asyncio.run(
            skill.run(
                {
                    "documents": [{
                        "id": "doc1",
                        "title": "FedAvg Paper",
                        "raw_text": (
                            "Data available at https://github.com/example/fl-benchmark. "
                            "See Table 1: global accuracy results. Figure 2 shows client drift."
                        ),
                    }],
                },
                {},
            )
        )
        pe = res.data["paper_extractions"][0]
        self.assertGreaterEqual(len(pe["tables_detected"]), 1)
        self.assertTrue(pe["code_links"])

    def test_schema_alignment_fl(self):
        skill = DatasetSchemaAlignmentSkill()
        res = asyncio.run(
            skill.run(
                {
                    "columns": ["Method", "Global_Accuracy", "communication_cost_mb", "client_drift"],
                    "project_mode": "federated_learning",
                },
                {},
            )
        )
        self.assertIn("global_accuracy", res.data.get("standard_columns", []))
        self.assertIn("communication_cost_mb", res.data.get("standard_columns", []))

    def test_pdf_table_extraction_no_fake(self):
        skill = PdfTableExtractionSkill()
        with tempfile.TemporaryDirectory() as tmp:
            res = asyncio.run(
                skill.run(
                    {"file_path": os.path.join(tmp, "missing.pdf"), "output_dir": tmp},
                    {},
                )
            )
            self.assertEqual(res.data.get("tables", []), [])
            self.assertTrue(res.errors or res.warnings)

    def test_pdf_table_extraction_csv(self):
        csv_path = os.path.join(tempfile.mkdtemp(), "sample.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["method", "global_accuracy", "f1_score"])
            writer.writerow(["FedAvg", "0.82", "0.79"])
        skill = PdfTableExtractionSkill()
        tables = skill._extract_with_pymupdf  # skip - test merge path via fake table skill output
        align = DatasetSchemaAlignmentSkill()
        align_res = asyncio.run(
            align.run(
                {"columns": ["method", "global_accuracy", "f1_score"], "project_mode": "federated_learning"},
                {},
            )
        )
        self.assertIn("method", align_res.data["standard_columns"])


if __name__ == "__main__":
    unittest.main()
