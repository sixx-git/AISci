"""文献推荐入库统计测试。"""
import unittest
from unittest.mock import MagicMock, patch

from app.services.literature_corpus_service import ensure_corpora_from_recommendations


class TestLiteratureImportStats(unittest.TestCase):
    def test_ensure_corpora_empty(self):
        result = ensure_corpora_from_recommendations("proj", "query", None, db=None)
        self.assertEqual(result.get("imported", 0), 0)

    @patch("app.services.literature_ingestion_service.LiteratureIngestionService")
    @patch("app.services.vector_store.build_vector_index")
    def test_ensure_corpora_imports_verified(self, mock_index, mock_service_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.import_arxiv_papers.return_value = {
            "results": [{"document_id": "doc-1", "duplicate": False}],
        }

        db = MagicMock()
        doc = MagicMock()
        doc.pdf_url = None
        db.query.return_value.filter.return_value.first.return_value = doc

        rec = {
            "discovery_mode": "llm_recommend_web_v3",
            "papers": [
                {
                    "title": "Verified Paper",
                    "abstract": "abstract text",
                    "verification_status": "verified",
                    "doi": "10.1/xyz",
                }
            ],
            "verified_count": 1,
        }
        result = ensure_corpora_from_recommendations("proj", "query", rec, db, auto_parse=True)
        self.assertEqual(result.get("imported"), 1)
        mock_index.assert_called_once()


if __name__ == "__main__":
    unittest.main()
