"""OpenAlex 来源文献应能正常出现在文档列表 API。"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.document_serialization import document_to_info
from app.schemas.project import DocumentSourceType


def test_document_to_info_accepts_openalex_source():
    doc = SimpleNamespace(
        id="doc-1",
        project_id="p1",
        filename="FEEL paper",
        file_path="",
        file_type="pdf",
        file_size=0,
        title="FEEL: FEderated LEarning Framework",
        authors="Author A",
        abstract="abstract",
        doi=None,
        keywords=None,
        journal=None,
        publication_date=None,
        summary=None,
        status=SimpleNamespace(value="processed"),
        error_message=None,
        chunk_count=3,
        source_type=SimpleNamespace(value="openalex"),
        source_url="https://example.com",
        pdf_url=None,
        external_id="W123",
        library_scope=SimpleNamespace(value="project"),
        import_status=SimpleNamespace(value="imported"),
        is_personal=False,
        metadata_json=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at=None,
    )
    info = document_to_info(doc)
    assert info.source_type == DocumentSourceType.OPENALEX
    assert "FEEL" in (info.title or "")
