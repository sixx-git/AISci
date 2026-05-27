"""
项目服务层
"""
import os
import uuid
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.config import get_settings
from app.models import (
    Project,
    Document,
    Chunk,
    ProjectStatus,
    DocumentStatus,
    ChunkStatus,
    SourceType,
    ImportStatus,
    LibraryScope,
)
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectQuery

# Document Parser
from app.services.document_parser import DocumentParser, ParserBackend

settings = get_settings()


class ProjectService:
    """项目服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_project(self, data: ProjectCreate) -> Project:
        """创建项目"""
        project_id = str(uuid.uuid4())
        project = Project(
            id=project_id,
            name=data.name,
            description=data.description,
            keywords=data.keywords,
            status=ProjectStatus.DRAFT,
            created_by=data.created_by
        )
        
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        
        return project
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目详情"""
        return self.db.query(Project).filter(Project.id == project_id).first()
    
    def list_projects(
        self,
        query: ProjectQuery
    ) -> Tuple[List[Project], int]:
        """项目列表"""
        q = self.db.query(Project)
        
        # 状态筛选
        if query.status:
            q = q.filter(Project.status == query.status)
        
        # 关键词搜索
        if query.keyword:
            keyword = f"%{query.keyword}%"
            q = q.filter(
                or_(
                    Project.name.like(keyword),
                    Project.description.like(keyword),
                    Project.keywords.like(keyword)
                )
            )
        
        # 排序
        q = q.order_by(Project.created_at.desc())
        
        # 总数
        total = q.count()
        
        # 分页
        offset = (query.page - 1) * query.page_size
        projects = q.offset(offset).limit(query.page_size).all()
        
        return projects, total
    
    def update_project(self, project_id: str, data: ProjectUpdate) -> Optional[Project]:
        """更新项目"""
        project = self.get_project(project_id)
        if not project:
            return None
        
        # 更新字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        
        project.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(project)
        
        return project
    
    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        project = self.get_project(project_id)
        if not project:
            return False
        
        self.db.delete(project)
        self.db.commit()
        
        return True


class DocumentService:
    """文档服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = settings.UPLOAD_DIR
        
        # 确保上传目录存在
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def upload_and_parse_document(
        self,
        filename: str,
        file_content: bytes,
        project_id: Optional[str] = None,
        auto_parse: bool = True
    ) -> Tuple[Document, Optional[List[Chunk]]]:
        """
        上传并解析文档（用户手动上传 PDF）

        统一字段：
          - source_type = upload
          - library_scope = personal
          - is_personal = true
          - import_status = imported → parsed（解析后）

        解析委托给 LiteratureIngestionService.parse_document()，
        确保与 arXiv 等外部文献走同一解析管道。

        Args:
            filename: 文件名
            file_content: 文件内容
            project_id: 项目 ID
            auto_parse: 是否自动解析

        Returns:
            Tuple[Document, Optional[List[Chunk]]]
        """
        doc_id = str(uuid.uuid4())
        file_extension = os.path.splitext(filename)[1].lower()
        save_filename = f"{doc_id}{file_extension}"

        if project_id:
            upload_subdir = os.path.join(self.upload_dir, project_id)
        else:
            upload_subdir = self.upload_dir
        os.makedirs(upload_subdir, exist_ok=True)

        save_path = os.path.join(upload_subdir, save_filename)

        with open(save_path, 'wb') as f:
            f.write(file_content)

        # 创建文档记录 — 显式设置上传来源字段
        doc = Document(
            id=doc_id,
            project_id=project_id,
            filename=filename,
            file_path=save_path,
            file_type=file_extension[1:] if file_extension else "unknown",
            file_size=len(file_content),
            # ── 统一字段 ──
            source_type=SourceType.UPLOAD,
            library_scope=LibraryScope.PERSONAL,
            is_personal=True,
            import_status=ImportStatus.IMPORTED,
            # ── 处理状态 ──
            status=DocumentStatus.UPLOADED,
            created_at=datetime.now()
        )

        self.db.add(doc)
        self.db.flush()

        # 自动解析（委托给统一管道）
        chunks = None
        if auto_parse and doc.file_path.lower().endswith(".pdf"):
            try:
                from app.services.literature_ingestion_service import (
                    LiteratureIngestionService,
                )
                ing_svc = LiteratureIngestionService(self.db)
                result = ing_svc.parse_document(
                    project_id=project_id or "",
                    document_id=doc_id,
                )
                doc = ing_svc.db.query(Document).filter(Document.id == doc_id).first()
                chunks = (
                    ing_svc.db.query(Chunk)
                    .filter(Chunk.document_id == doc_id)
                    .all()
                )
            except Exception as e:
                doc.import_status = ImportStatus.FAILED
                doc.status = DocumentStatus.FAILED
                doc.error_message = str(e)
                self.db.commit()

        self.db.commit()
        self.db.refresh(doc)

        return doc, chunks
    
    def parse_document(
        self,
        doc_id: str,
        backend: ParserBackend = ParserBackend.PYMUPDF
    ) -> Tuple[Document, List[Chunk]]:
        """
        解析文档（委托给统一管道）

        为保持向后兼容保留此方法，
        实际委托给 LiteratureIngestionService.parse_document()。
        """
        from app.services.literature_ingestion_service import (
            LiteratureIngestionService,
        )

        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        ing_svc = LiteratureIngestionService(self.db)
        ing_svc.parse_document(
            project_id=doc.project_id or "",
            document_id=doc_id,
        )

        # 重新加载，获取最新状态和 Chunks
        doc = self.get_document(doc_id)
        chunks = (
            self.db.query(Chunk)
            .filter(Chunk.document_id == doc_id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        return doc, chunks
    
    def _delete_document_chunks(self, doc_id: str):
        """删除文档的所有切片"""
        self.db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
        self.db.flush()
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        return self.db.query(Document).filter(Document.id == doc_id).first()
    
    def list_documents(
        self,
        project_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Document], int]:
        """文档列表"""
        q = self.db.query(Document)
        
        if project_id:
            q = q.filter(Document.project_id == project_id)
        
        q = q.order_by(Document.created_at.desc())
        
        total = q.count()
        offset = (page - 1) * page_size
        documents = q.offset(offset).limit(page_size).all()
        
        return documents, total
    
    def get_document_chunks(
        self,
        doc_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Chunk], int]:
        """获取文档的切片"""
        q = self.db.query(Chunk).filter(Chunk.document_id == doc_id)
        q = q.order_by(Chunk.chunk_index)
        
        total = q.count()
        offset = (page - 1) * page_size
        chunks = q.offset(offset).limit(page_size).all()
        
        return chunks, total
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        doc = self.get_document(doc_id)
        if not doc:
            return False
        
        # 删除文件
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except:
                pass
        
        self.db.delete(doc)
        self.db.commit()
        
        return True
    
    # ==================== 兼容旧方法 ====================
    
    def save_document(
        self,
        filename: str,
        file_content: bytes,
        project_id: Optional[str] = None
    ) -> Document:
        """保存文档（旧方法，建议使用 upload_and_parse_document）"""
        doc, _ = self.upload_and_parse_document(
            filename=filename,
            file_content=file_content,
            project_id=project_id,
            auto_parse=False
        )
        return doc
    
    def update_document_status(
        self,
        doc_id: str,
        status: str,
        error_message: Optional[str] = None,
        content: Optional[str] = None,
        summary: Optional[str] = None
    ) -> Optional[Document]:
        """更新文档状态"""
        doc = self.get_document(doc_id)
        if not doc:
            return None
        
        doc.status = status
        if error_message:
            doc.error_message = error_message
        if content:
            doc.raw_text = content
        if summary:
            doc.summary = summary
        
        doc.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(doc)
        
        return doc
