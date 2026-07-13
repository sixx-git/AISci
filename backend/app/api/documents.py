"""
文档 API
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.response import ApiResponse, success, error
from app.core.async_utils import run_blocking
from app.services.project_service import DocumentService
from app.schemas.project import (
    DocumentInfo,
    UploadResponse,
    DocumentQuery,
    ChunkInfo,
    ChunkQuery,
    ParseDocumentRequest,
    ListResponse
)
from app.services.document_serialization import document_to_info
from app.services.document_parser import ParserBackend

router = APIRouter(tags=["documents"])


def _document_to_info(doc) -> DocumentInfo:
    return document_to_info(doc)


@router.post("/upload", response_model=ApiResponse[UploadResponse])
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(None, description="项目 ID"),
    auto_parse: bool = Query(True, description="是否自动解析"),
    db: Session = Depends(get_db)
):
    """上传文档"""
    try:
        file_content = await file.read()
        
        service = DocumentService(db)
        doc, chunks = await run_blocking(
            service.upload_and_parse_document,
            filename=file.filename,
            file_content=file_content,
            project_id=project_id,
            auto_parse=auto_parse,
        )
        
        doc_info = _document_to_info(doc)
        chunks_count = len(chunks) if chunks else 0
        
        return success(
            UploadResponse(
                document=doc_info,
                chunks_count=chunks_count
            ),
            message="文档上传成功"
        )
    except Exception as e:
        return error(str(e))


@router.post("/{doc_id}/parse", response_model=ApiResponse[UploadResponse])
async def parse_document(
    doc_id: str,
    request: Optional[ParseDocumentRequest] = None,
    db: Session = Depends(get_db)
):
    """解析文档"""
    try:
        backend = ParserBackend.PYMUPDF
        if request and request.backend == "pypdf":
            backend = ParserBackend.PYPDF
        
        service = DocumentService(db)
        doc, chunks = await run_blocking(service.parse_document, doc_id, backend=backend)
        
        doc_info = _document_to_info(doc)
        chunks_count = len(chunks) if chunks else 0
        
        return success(
            UploadResponse(
                document=doc_info,
                chunks_count=chunks_count
            ),
            message="文档解析成功"
        )
    except ValueError as e:
        return error(str(e), code=404)
    except Exception as e:
        return error(str(e))


@router.get("", response_model=ApiResponse[ListResponse])
async def list_documents(
    project_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """文档列表"""
    try:
        service = DocumentService(db)
        docs, total = service.list_documents(
            project_id=project_id,
            page=page,
            page_size=page_size
        )
        
        doc_infos = [_document_to_info(d) for d in docs]
        
        return success(
            ListResponse(
                items=doc_infos,
                total=total,
                page=page,
                page_size=page_size
            )
        )
    except Exception as e:
        return error(str(e))


@router.get("/{doc_id}", response_model=ApiResponse[DocumentInfo])
async def get_document(doc_id: str, db: Session = Depends(get_db)):
    """获取文档详情"""
    try:
        service = DocumentService(db)
        doc = service.get_document(doc_id)
        
        if not doc:
            return error("文档不存在", code=404)
        
        return success(_document_to_info(doc))
    except Exception as e:
        return error(str(e))


@router.get("/{doc_id}/chunks", response_model=ApiResponse[ListResponse])
async def get_document_chunks(
    doc_id: str,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """获取文档切片"""
    try:
        service = DocumentService(db)
        chunks, total = service.get_document_chunks(
            doc_id=doc_id,
            page=page,
            page_size=page_size
        )
        
        chunk_infos = [ChunkInfo.model_validate(c) for c in chunks]
        
        return success(
            ListResponse(
                items=chunk_infos,
                total=total,
                page=page,
                page_size=page_size
            )
        )
    except Exception as e:
        return error(str(e))


@router.delete("/{doc_id}", response_model=ApiResponse)
async def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """删除文档"""
    try:
        service = DocumentService(db)
        result = await run_blocking(service.delete_document, doc_id)
        
        if not result:
            return error("文档不存在", code=404)
        
        return success(message="文档删除成功")
    except Exception as e:
        return error(str(e))
