"""化学结构文件抽取测试"""
import asyncio
import os
import tempfile
import unittest

from app.skills.data_finder.chem_structure_extraction_skill import ChemStructureExtractionSkill
from app.skills.data_finder.file_format_registry import is_allowed_upload_filename


class TestChemStructureExtraction(unittest.TestCase):
    def test_allowed_upload_filenames(self):
        self.assertTrue(is_allowed_upload_filename("chembl_37.sdf.gz"))
        self.assertTrue(is_allowed_upload_filename("compounds.sdf"))
        self.assertTrue(is_allowed_upload_filename("library.mol"))
        self.assertTrue(is_allowed_upload_filename("data.csv"))

    def test_sdf_gz_sample(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sample = os.path.join(repo_root, "chembl_37.sdf.gz")
        if not os.path.exists(sample):
            self.skipTest("chembl_37.sdf.gz 不在仓库根目录")

        with tempfile.TemporaryDirectory() as tmp:
            skill = ChemStructureExtractionSkill()
            res = asyncio.run(skill.run(
                {
                    "file_path": sample,
                    "filename": "chembl_37.sdf.gz",
                    "source_title": "ChEMBL 37",
                    "output_dir": tmp,
                    "max_records": 20,
                },
                {},
            ))
            tables = res.data.get("tables") or []
            self.assertEqual(len(tables), 1)
            self.assertGreaterEqual(tables[0]["row_count"], 1)
            self.assertIn("record_id", tables[0]["columns"])
            self.assertTrue(os.path.exists(tables[0]["csv_path"]))


if __name__ == "__main__":
    unittest.main()
