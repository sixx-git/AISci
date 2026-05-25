"""
项目数据模型
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum

from app.core.database import Base


class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    """项目模型"""
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, index=True, comment="项目ID")
    name = Column(String(200), nullable=False, index=True, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False, comment="项目状态")
    keywords = Column(Text, nullable=True, comment="关键词，逗号分隔")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    created_by = Column(String(100), nullable=True, comment="创建者")


class Document(Base):
    """文档模型（增强版）"""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, index=True, comment="文档ID")
    project_id = Column(String(36), index=True, nullable=True, comment="所属项目ID")
    filename = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(512), nullable=False, comment="文件存储路径")
    file_type = Column(String(50), nullable=False, index=True, comment="文件类型")
    file_size = Column(Integer, default=0, comment="文件大小（字节）")
    
    content = Column(Text, nullable=True, comment="提取的文本内容")
    summary = Column(Text, nullable=True, comment="文档摘要")
    
    status = Column(String(50), default="pending", comment="处理状态")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="上传时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
