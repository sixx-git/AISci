"""自动 discovery：默认不下载 PDF，优先摘要索引。"""
from unittest.mock import MagicMock, patch

from app.services.literature_corpus_service import ensure_corpora_from_recommendations


def test_ensure_corpora_skips_pdf_download_when_abstract_present():
    db = MagicMock()
    doc = MagicMock()
    doc.abstract = "A" * 80
    doc.pdf_url = "https://arxiv.org/pdf/1234.5678.pdf"
    doc.file_path = None
    db.query.return_value.filter.return_value.first.return_value = doc

    service = MagicMock()
    service.import_arxiv_papers.return_value = {
        "results": [{"document_id": "doc-1", "duplicate": False}]
    }
    service.ensure_abstract_chunks.return_value = True

    rec = {
        "papers": [
            {
                "title": "Paper",
                "verification_status": "partial",
                "abstract": "A" * 80,
                "arxiv_id": "1234.5678",
                "source": "arxiv",
                "relevance_score": 8,
                "gate_passed": True,
            }
        ],
        "verified_count": 0,
        "partial_count": 1,
        "unverified_count": 0,
        "research_domain": "FL",
    }

    with patch(
        "app.services.literature_corpus_service._literature_import_settings",
        return_value=(8, False, True, False),
    ), patch(
        "app.services.literature_relevance_gate.apply_relevance_gate",
        side_effect=lambda _q, out, **_k: dict(out or {}),
    ), patch(
        "app.services.literature_ingestion_service.LiteratureIngestionService",
        return_value=service,
    ), patch(
        "app.services.vector_store.build_vector_index",
    ):
        meta = ensure_corpora_from_recommendations("proj", "RQ", rec, db, max_import=4)

    service.download_arxiv_pdf.assert_not_called()
    service.ensure_abstract_chunks.assert_called()
    assert meta["imported"] == 1
    assert meta.get("download_pdf") is False
    assert meta["abstract_indexed"] >= 1
