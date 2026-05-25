"""
项目相关 schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# ============= 请求 schemas =============

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


# ============= 响应 schemas =============

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


# ============= 文件上传相关 =============

class UploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件ID")
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小")
    status: str = Field(..., description="处理状态")


class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    project_id: Optional[str] = None
    filename: str
    file_type: str
    file_size: int
    summary: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
