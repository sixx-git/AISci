"""文献推荐入库统计测试。"""
import unittest
from unittest.mock import MagicMock, patch

from app.services.literature_corpus_service import ensure_corpora_from_recommendations


def _mock_settings(*, use_mock=True, gate_enabled=True, import_unverified_with_abstract=True):
    s = MagicMock()
    s.LITERATURE_RECOMMEND_MAX = 12
    s.LITERATURE_IMPORT_MAX = 16
    s.LITERATURE_IMPORT_UNVERIFIED = False
    s.LITERATURE_IMPORT_UNVERIFIED_WITH_ABSTRACT = import_unverified_with_abstract
    s.LIT_RELEVANCE_GATE_ENABLED = gate_enabled
    s.LIT_PAPER_SCORE_CUTOFF = 6
    s.USE_MOCK_LLM = use_mock
    s.QWEN_API_KEY = ""
    return s


class TestLiteratureImportStats(unittest.TestCase):
    @patch("app.core.config.get_settings", return_value=_mock_settings())
    def test_ensure_corpora_empty(self, _mock_gs):
        result = ensure_corpora_from_recommendations("proj", "query", None, db=None)
        self.assertEqual(result.get("imported", 0), 0)

    @patch("app.core.config.get_settings", return_value=_mock_settings())
    @patch("app.services.literature_ingestion_service.LiteratureIngestionService")
    @patch("app.services.vector_store.build_vector_index")
    def test_ensure_corpora_imports_verified(self, mock_index, mock_service_cls, _mock_gs):
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
                    "title": "Verified Paper about query relevance",
                    "abstract": "This abstract discusses the query topic in detail for relevance.",
                    "verification_status": "verified",
                    "doi": "10.1/xyz",
                    "gate_passed": True,
                    "relevance_score": 9,
                }
            ],
            "verified_count": 1,
        }
        # 跳过真实门控打分，直接验证入库统计
        with patch(
            "app.services.literature_relevance_gate.apply_relevance_gate",
            side_effect=lambda rq, rec_out, **kwargs: {
                **(rec_out or {}),
                "papers": (rec_out or {}).get("papers") or [],
                "gate_stats": {
                    "enabled": True,
                    "candidate_count": 1,
                    "passed_count": 1,
                    "rejected_count": 0,
                },
            },
        ):
            result = ensure_corpora_from_recommendations(
                "proj", "query relevance", rec, db, auto_parse=True
            )
        self.assertEqual(result.get("imported"), 1)
        mock_index.assert_called_once()
        self.assertIn("gate_stats", result)

    @patch("app.core.config.get_settings", return_value=_mock_settings())
    @patch("app.services.literature_ingestion_service.LiteratureIngestionService")
    @patch("app.services.vector_store.build_vector_index")
    def test_ensure_corpora_imports_unverified_with_abstract(
        self, mock_index, mock_service_cls, _mock_gs
    ):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.import_arxiv_papers.return_value = {
            "results": [{"document_id": "doc-u", "duplicate": False}],
        }
        mock_service.parse_document.side_effect = ValueError("PDF 文件未下载或不存在")
        mock_service.ensure_abstract_chunks.return_value = True

        db = MagicMock()
        doc = MagicMock()
        doc.pdf_url = None
        doc.file_path = None
        db.query.return_value.filter.return_value.first.return_value = doc

        rec = {
            "papers": [
                {
                    "title": "The origin of biological homochirality",
                    "abstract": (
                        "Homochirality of biomolecules is a defining feature of life and "
                        "remains an open question in origin-of-life research."
                    ),
                    "verification_status": "unverified",
                    "gate_passed": True,
                    "relevance_score": 8,
                }
            ],
        }
        with patch(
            "app.services.literature_relevance_gate.apply_relevance_gate",
            side_effect=lambda rq, rec_out, **kwargs: {
                **(rec_out or {}),
                "papers": (rec_out or {}).get("papers") or [],
                "gate_stats": {
                    "enabled": True,
                    "candidate_count": 1,
                    "passed_count": 1,
                    "rejected_count": 0,
                },
            },
        ):
            result = ensure_corpora_from_recommendations(
                "proj", "why life needs chirality", rec, db, auto_parse=True
            )
        self.assertEqual(result.get("imported"), 1)
        self.assertEqual(result.get("abstract_indexed"), 1)
        mock_service.ensure_abstract_chunks.assert_called()
