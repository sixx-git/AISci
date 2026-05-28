"""
项目相关 schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============= 项目相关 =============

class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectCreate(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    keywords: Optional[str] = Field(None, description="关键词，逗号分隔")
    created_by: Optional[str] = Field(None, description="创建者")
    # 研究问题字段
    research_question: Optional[str] = Field(None, description="研究问题")
    research_domain: Optional[str] = Field(None, description="研究领域")
    research_goal: Optional[str] = Field(None, description="研究目标")
    research_background: Optional[str] = Field(None, description="已知背景")
    data_source: Optional[str] = Field(None, description="数据来源")
    constraints: Optional[str] = Field(None, description="限制条件")
    expected_output: Optional[str] = Field(None, description="期望输出")


class ProjectUpdate(BaseModel):
    """更新项目请求（部分字段更新）"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    status: Optional[ProjectStatus] = Field(None, description="项目状态")
    keywords: Optional[str] = Field(None, description="关键词，逗号分隔")
    # 研究问题字段（可选更新）
    research_question: Optional[str] = Field(None, description="研究问题")
    research_domain: Optional[str] = Field(None, description="研究领域")
    research_goal: Optional[str] = Field(None, description="研究目标")
    research_background: Optional[str] = Field(None, description="已知背景")
    data_source: Optional[str] = Field(None, description="数据来源")
    constraints: Optional[str] = Field(None, description="限制条件")
    expected_output: Optional[str] = Field(None, description="期望输出")


class ProjectQuery(BaseModel):
    """项目查询请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    status: Optional[ProjectStatus] = Field(None, description="项目状态筛选")
    keyword: Optional[str] = Field(None, description="关键词搜索")


class ProjectBase(BaseModel):
    """项目基础信息"""
    id: str
    name: str
    description: Optional[str] = None
    status: ProjectStatus
    keywords: Optional[str] = None
    # 研究问题字段
    research_question: Optional[str] = None
    research_domain: Optional[str] = None
    research_goal: Optional[str] = None
    research_background: Optional[str] = None
    data_source: Optional[str] = None
    constraints: Optional[str] = None
    expected_output: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProjectDetail(ProjectBase):
    """项目详情"""
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ProjectList(ProjectBase):
    """项目列表项"""
    created_at: datetime
    document_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


# ============= 文档相关 =============

class DocumentStatus(str, Enum):
    """文档状态枚举"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class DocumentType(str, Enum):
    """文档类型枚举"""
    RESEARCH_PAPER = "research_paper"
    BOOK = "book"
    REPORT = "report"
    OTHER = "other"


class DocumentSourceType(str, Enum):
    """文献来源类型枚举"""
    UPLOAD = "upload"
    ARXIV = "arxiv"
    GOOGLE_SCHOLAR_IMPORT = "google_scholar_import"
    BIBTEX = "bibtex"
    MANUAL = "manual"


class DocumentImportStatus(str, Enum):
    """文献导入状态枚举"""
    DISCOVERED = "discovered"
    IMPORTED = "imported"
    PDF_DOWNLOADED = "pdf_downloaded"
    PARSED = "parsed"
    INDEXED = "indexed"
    FAILED = "failed"


class LibraryScope(str, Enum):
    """文献库范围枚举"""
    BASE = "base"
    PROJECT = "project"
    PERSONAL = "personal"


class DocumentCreate(BaseModel):
    """创建/导入文档请求"""
    project_id: str = Field(..., description="所属项目ID")
    filename: str = Field(..., max_length=255)
    title: Optional[str] = Field(None, max_length=500)
    authors: Optional[str] = Field(None)
    abstract: Optional[str] = Field(None)
    doi: Optional[str] = Field(None, max_length=200)
    source_url: Optional[str] = Field(None, max_length=500)
    pdf_url: Optional[str] = Field(None, max_length=500)
    external_id: Optional[str] = Field(None, max_length=200, description="外部ID（arXiv ID / DOI）")
    source_type: DocumentSourceType = Field(default=DocumentSourceType.UPLOAD)
    library_scope: LibraryScope = Field(default=LibraryScope.PERSONAL)
    import_status: DocumentImportStatus = Field(default=DocumentImportStatus.IMPORTED)
    is_personal: bool = Field(default=True)
    doc_type: Optional[DocumentType] = Field(None)
    metadata_json: Optional[dict] = Field(None, description="原始元数据JSON")


class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    project_id: Optional[str] = None
    filename: str
    file_type: str
    file_size: int
    title: Optional[str] = None
    authors: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    keywords: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[datetime] = None
    summary: Optional[str] = None
    status: DocumentStatus
    error_message: Optional[str] = None
    chunk_count: Optional[int] = Field(None, description="切片数量")
    # 多来源文献库字段
    source_type: Optional[DocumentSourceType] = None
    source_url: Optional[str] = None
    pdf_url: Optional[str] = None
    external_id: Optional[str] = None
    library_scope: Optional[LibraryScope] = None
    import_status: Optional[DocumentImportStatus] = None
    is_personal: Optional[bool] = None
    metadata_json: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentQuery(BaseModel):
    """文档查询请求"""
    project_id: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UploadResponse(BaseModel):
    """文件上传响应"""
    document: DocumentInfo
    chunks_count: Optional[int] = None


class ParseDocumentRequest(BaseModel):
    """解析文档请求"""
    backend: Optional[str] = Field("pymupdf", description="解析后端: pymupdf 或 pypdf")


# ============= 切片相关 =============

class ChunkStatus(str, Enum):
    """切片状态枚举"""
    PENDING = "pending"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class ChunkInfo(BaseModel):
    """切片信息"""
    id: str
    document_id: str
    chunk_index: int
    content: Optional[str] = None
    content_preview: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    page_number: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    chunk_type: Optional[str] = None
    status: ChunkStatus
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChunkQuery(BaseModel):
    """切片查询请求"""
    document_id: str
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ============= 列表响应 =============

class ListResponse(BaseModel):
    """列表响应"""
    items: list
    total: int
    page: int
    page_size: int
