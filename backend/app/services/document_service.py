import os
import uuid
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.schemas.documents import DocumentResponse
from app.models.documents import Document
from app.services.vector_service import VectorService
from app.core.config import get_settings

settings = get_settings()


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.vector_service = VectorService()
        self.storage_path = "./storage/documents"
        os.makedirs(self.storage_path, exist_ok=True)
    
    async def upload_document(self, file: UploadFile) -> DocumentResponse:
        document_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        save_filename = f"{document_id}{file_extension}"
        save_path = os.path.join(self.storage_path, save_filename)
        
        with open(save_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        content_text = await self._extract_text(save_path, file.filename)
        
        document = Document(
            id=document_id,
            filename=file.filename,
            file_path=save_path,
            file_type=file_extension[1:] if file_extension else "unknown",
            content=content_text,
            status="processed"
        )
        self.db.add(document)
        self.db.commit()
        
        await self.vector_service.add_document(document_id, content_text)
        
        return DocumentResponse(
            success=True,
            document_id=document_id,
            filename=file.filename,
            upload_time=datetime.now(),
            status="processed"
        )
    
    async def list_documents(self):
        documents = self.db.query(Document).all()
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "status": doc.status,
                "created_at": doc.created_at
            }
            for doc in documents
        ]
    
    async def _extract_text(self, file_path: str, filename: str) -> str:
        file_extension = os.path.splitext(filename)[1].lower()
        
        if file_extension == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return f"文件 {filename} 的内容（需添加更多解析器支持）"
