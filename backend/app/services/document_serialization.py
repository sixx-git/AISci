"""Document ORM → API schema 序列化。"""
from __future__ import annotations

from app.schemas.project import DocumentInfo


def document_to_info(doc) -> DocumentInfo:
    """Document ORM → DocumentInfo，兼容 openalex 等新来源类型。"""
    try:
        return DocumentInfo.model_validate(doc)
    except Exception:
        data = {
            "id": doc.id,
            "project_id": doc.project_id,
            "filename": doc.filename or "unknown",
            "file_type": doc.file_type or "pdf",
            "file_size": doc.file_size or 0,
            "title": doc.title,
            "authors": doc.authors,
            "abstract": doc.abstract,
            "doi": doc.doi,
            "keywords": doc.keywords,
            "journal": doc.journal,
            "publication_date": doc.publication_date,
            "summary": doc.summary,
            "status": doc.status.value if hasattr(doc.status, "value") else doc.status,
            "error_message": doc.error_message,
            "chunk_count": doc.chunk_count,
            "source_type": doc.source_type.value if hasattr(doc.source_type, "value") else doc.source_type,
            "source_url": doc.source_url,
            "pdf_url": doc.pdf_url,
            "external_id": doc.external_id,
            "library_scope": doc.library_scope.value if hasattr(doc.library_scope, "value") else doc.library_scope,
            "import_status": doc.import_status.value if hasattr(doc.import_status, "value") else doc.import_status,
            "is_personal": doc.is_personal,
            "metadata_json": doc.metadata_json,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
        return DocumentInfo.model_validate(data)
