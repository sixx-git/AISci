"""外部数据候选 — 手动上传闭环"""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.external_candidate_service import (
    STATUS_MERGED,
    STATUS_PENDING,
    ensure_candidate_ids,
    list_manual_candidates,
)


class TestExternalCandidateIds(unittest.TestCase):
    def test_ensure_ids_and_pending_status(self):
        out = ensure_candidate_ids([
            {"dataset_name": "titanic", "availability": "catalog_only", "import_supported": False},
        ])
        self.assertTrue(out[0].get("candidate_id"))
        self.assertEqual(out[0]["user_upload_status"], STATUS_PENDING)

    def test_list_manual_filters_auto_only(self):
        manual = list_manual_candidates([
            {"candidate_id": "c1", "availability": "catalog_only", "import_supported": False},
            {"candidate_id": "c2", "availability": "search_and_import", "import_supported": True},
        ])
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual[0]["candidate_id"], "c1")


class TestExternalCandidateUpload(unittest.TestCase):
    def test_upload_and_merge(self):
        from app.services.external_candidate_service import ExternalCandidateService

        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "data_acquisition", "fl_client_metrics.csv",
        )
        self.assertTrue(os.path.exists(fixture))

        mock_df = MagicMock()
        project_dir = tempfile.mkdtemp()
        mock_df._project_dir.return_value = project_dir
        mock_df.load_results.return_value = {
            "external_candidates": [{
                "candidate_id": "cand_test",
                "dataset_name": "Kaggle Titanic",
                "url": "https://www.kaggle.com/datasets/titanic",
                "availability": "catalog_only",
                "import_supported": False,
            }],
            "extracted_tables": [],
            "provenance": [],
        }
        mock_df.save_results = MagicMock()
        mock_df.run_align_schema = AsyncMock(return_value={})
        mock_df.run_merge = AsyncMock(return_value={
            "merged": {"row_count": 3},
            "external_candidates": [{
                "candidate_id": "cand_test",
                "user_upload_status": STATUS_MERGED,
            }],
        })

        svc = ExternalCandidateService(MagicMock())
        svc._df = mock_df

        result = asyncio.run(svc.upload_and_merge(
            "proj1",
            "cand_test",
            source_path=fixture,
            original_filename="fl_client_metrics.csv",
        ))
        self.assertEqual(result["merged"]["row_count"], 3)
        mock_df.run_align_schema.assert_called_once()
        mock_df.run_merge.assert_called_once()
        save_calls = mock_df.save_results.call_args_list
        self.assertGreaterEqual(len(save_calls), 2)


if __name__ == "__main__":
    unittest.main()
