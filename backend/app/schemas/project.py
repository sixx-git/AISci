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


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    status: Optional[ProjectStatus] = Field(None, description="项目状态")
    keywords: Optional[str] = Field(None, description="关键词，逗号分隔")


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
    summary: Optional[str] = None
    status: DocumentStatus
    error_message: Optional[str] = None
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
    INDEXED = "indexed"
    PROCESSED = "processed"


class ChunkInfo(BaseModel):
    """切片信息"""
    id: str
    document_id: str
    chunk_index: int
    content: Optional[str] = None
    content_preview: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
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
