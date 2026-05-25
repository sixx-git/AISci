"""
项目相关数据模型
包含：Project, Document, Chunk, Hypothesis, ExperimentDesign, Report, RunLog
"""
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from datetime import datetime
import uuid

from app.models.core import Base, TimestampMixin


class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    DOCUMENTS_PROCESSED = "documents_processed"
    HYPOTHESIS_GENERATED = "hypothesis_generated"
    EXPERIMENT_DESIGNED = "experiment_designed"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    """
    项目表
    存储研究项目的基本信息
    """
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(200), nullable=False, index=True, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    research_topic = Column(Text, nullable=True, comment="研究主题")
    keywords = Column(Text, nullable=True, comment="关键词，逗号分隔")
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False, index=True, comment="项目状态")
    created_by = Column(String(100), nullable=True, comment="创建者")
    priority = Column(Integer, default=5, comment="优先级（1-10）")
    config = Column(JSON, nullable=True, comment="项目配置（JSON格式）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="project", cascade="all, delete-orphan")
    hypotheses = relationship("Hypothesis", back_populates="project", cascade="all, delete-orphan")
    experiment_designs = relationship("ExperimentDesign", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")
    run_logs = relationship("RunLog", back_populates="project", cascade="all, delete-orphan")
    
    __table_args__ = {'comment': '研究项目表'}


class DocumentType(str, Enum):
    """文档类型枚举"""
    RESEARCH_PAPER = "research_paper"
    REVIEW = "review"
    THESIS = "thesis"
    REPORT = "report"
    PREPRINT = "preprint"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """文档处理状态枚举"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Document(Base):
    """
    文档表
    存储论文和其他文献的元数据
    """
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # 文件信息
    filename = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(512), nullable=False, comment="文件存储路径")
    file_type = Column(String(50), nullable=False, comment="文件类型（扩展名）")
    file_size = Column(Integer, default=0, comment="文件大小（字节）")
    mime_type = Column(String(100), nullable=True, comment="MIME类型")
    
    # 论文元数据
    title = Column(String(500), nullable=True, index=True, comment="论文标题")
    authors = Column(Text, nullable=True, comment="作者列表")
    abstract = Column(Text, nullable=True, comment="摘要")
    keywords = Column(Text, nullable=True, comment="关键词")
    publication_date = Column(DateTime, nullable=True, comment="发布日期")
    journal = Column(String(200), nullable=True, comment="期刊/会议名称")
    volume = Column(String(50), nullable=True, comment="卷")
    issue = Column(String(50), nullable=True, comment="期")
    pages = Column(String(50), nullable=True, comment="页码")
    doi = Column(String(200), nullable=True, index=True, comment="DOI编号")
    source_url = Column(String(500), nullable=True, comment="来源URL")
    
    # 处理信息
    doc_type = Column(SQLEnum(DocumentType), default=DocumentType.RESEARCH_PAPER, nullable=True, comment="文档类型")
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False, index=True, comment="处理状态")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 提取的内容
    raw_text = Column(Text, nullable=True, comment="原始提取文本")
    summary = Column(Text, nullable=True, comment="文档摘要")
    
    # 元数据
    extra_metadata = Column(JSON, nullable=True, comment="额外元数据（JSON）")
    custom_fields = Column(JSON, nullable=True, comment="自定义字段（JSON）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = {'comment': '文档表（论文等文献）'}


class ChunkStatus(str, Enum):
    """文献切片状态枚举"""
    PENDING = "pending"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class Chunk(Base):
    """
    文献切片表
    存储向量化后的文献切片
    """
    __tablename__ = "chunks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    
    # 切片信息
    chunk_index = Column(Integer, nullable=False, comment="在文档中的序号")
    content = Column(Text, nullable=False, comment="切片文本内容")
    content_preview = Column(String(500), nullable=True, comment="内容预览")
    
    # 位置信息
    start_offset = Column(Integer, nullable=True, comment="在原文档中的起始位置")
    end_offset = Column(Integer, nullable=True, comment="在原文档中的结束位置")
    start_page = Column(Integer, nullable=True, comment="起始页码")
    end_page = Column(Integer, nullable=True, comment="结束页码")
    
    # 向量化信息
    embedding_model = Column(String(100), nullable=True, comment="向量化模型名称")
    vector = Column(JSON, nullable=True, comment="向量数据（JSON存储）")
    dimension = Column(Integer, nullable=True, comment="向量维度")
    
    # 元数据
    chunk_type = Column(String(50), default="text", comment="切片类型")
    status = Column(SQLEnum(ChunkStatus), default=ChunkStatus.PENDING, nullable=False, index=True, comment="处理状态")
    tokens_count = Column(Integer, nullable=True, comment="Token数量")
    extra_metadata = Column(JSON, nullable=True, comment="额外元数据")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="chunks")
    document = relationship("Document", back_populates="chunks")
    
    __table_args__ = {'comment': '文献切片表'}


class HypothesisStatus(str, Enum):
    """假设状态枚举"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


class Hypothesis(Base):
    """
    科学假设表
    存储由AI生成的科学假设
    """
    __tablename__ = "hypotheses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # 假设内容
    title = Column(String(500), nullable=False, comment="假设标题")
    description = Column(Text, nullable=False, comment="假设详细描述")
    summary = Column(Text, nullable=True, comment="假设摘要")
    
    # 分类和标签
    category = Column(String(100), nullable=True, comment="假设分类")
    tags = Column(Text, nullable=True, comment="标签列表，逗号分隔")
    
    # 置信度和评分
    confidence_score = Column(Float, default=0.5, comment="置信度评分（0-1）")
    novelty_score = Column(Float, nullable=True, comment="创新性评分（0-1）")
    feasibility_score = Column(Float, nullable=True, comment="可行性评分（0-1）")
    
    # 来源信息
    source_documents = Column(Text, nullable=True, comment="来源文献ID列表")
    source_chunks = Column(Text, nullable=True, comment="来源切片ID列表")
    
    # 状态和版本
    version = Column(Integer, default=1, comment="版本号")
    parent_id = Column(String(36), nullable=True, comment="父假设ID（用于继承关系）")
    status = Column(SQLEnum(HypothesisStatus), default=HypothesisStatus.DRAFT, nullable=False, index=True, comment="状态")
    
    # 评估和验证
    reasoning = Column(Text, nullable=True, comment="推理和论证过程")
    evidence = Column(Text, nullable=True, comment="支持证据")
    counterarguments = Column(Text, nullable=True, comment="反驳意见")
    experiment_suggestions = Column(Text, nullable=True, comment="实验建议")
    
    # 元数据
    generated_by = Column(String(100), nullable=True, comment="生成者（系统/用户）")
    model_used = Column(String(100), nullable=True, comment="使用的模型")
    extra_metadata = Column(JSON, nullable=True, comment="额外元数据")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="hypotheses")
    
    __table_args__ = {'comment': '科学假设表'}


class ExperimentDesignStatus(str, Enum):
    """实验设计状态枚举"""
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"


class ExperimentDesign(Base):
    """
    实验设计表
    存储由AI生成的实验设计方案
    """
    __tablename__ = "experiment_designs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    hypothesis_id = Column(String(36), ForeignKey("hypotheses.id"), nullable=True, index=True, comment="关联的假设ID")
    
    # 实验基本信息
    title = Column(String(500), nullable=False, comment="实验设计标题")
    description = Column(Text, nullable=False, comment="实验描述")
    purpose = Column(Text, nullable=True, comment="实验目的")
    
    # 实验方案
    design_type = Column(String(100), nullable=True, comment="实验类型")
    variables = Column(JSON, nullable=True, comment="变量配置")
    procedure = Column(Text, nullable=True, comment="实验步骤")
    
    # 材料和设备
    materials = Column(Text, nullable=True, comment="所需材料")
    equipment = Column(Text, nullable=True, comment="所需设备")
    
    # 数据收集
    data_collection = Column(Text, nullable=True, comment="数据收集方法")
    measurement_methods = Column(Text, nullable=True, comment="测量方法")
    
    # 分析计划
    statistical_methods = Column(Text, nullable=True, comment="统计分析方法")
    expected_results = Column(Text, nullable=True, comment="预期结果")
    success_criteria = Column(Text, nullable=True, comment="成功判定标准")
    
    # 资源
    time_estimate = Column(String(100), nullable=True, comment="时间估计")
    budget_estimate = Column(Text, nullable=True, comment="预算估计")
    resources_needed = Column(Text, nullable=True, comment="所需资源")
    
    # 风险评估
    potential_pitfalls = Column(Text, nullable=True, comment="潜在问题")
    contingency_plans = Column(Text, nullable=True, comment="应急预案")
    
    # 版本和状态
    version = Column(Integer, default=1, comment="版本号")
    status = Column(SQLEnum(ExperimentDesignStatus), default=ExperimentDesignStatus.DRAFT, nullable=False, index=True, comment="状态")
    
    # 元数据
    generated_by = Column(String(100), nullable=True, comment="生成者")
    model_used = Column(String(100), nullable=True, comment="使用的模型")
    extra_metadata = Column(JSON, nullable=True, comment="额外元数据")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="experiment_designs")
    
    __table_args__ = {'comment': '实验设计表'}


class ReportStatus(str, Enum):
    """报告状态枚举"""
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Report(Base):
    """
    最终报告表
    存储AI生成的最终研究报告
    """
    __tablename__ = "reports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # 报告基本信息
    title = Column(String(500), nullable=False, comment="报告标题")
    summary = Column(Text, nullable=True, comment="报告摘要")
    authors = Column(Text, nullable=True, comment="作者列表")
    
    # 报告内容
    introduction = Column(Text, nullable=True, comment="引言")
    literature_review = Column(Text, nullable=True, comment="文献综述")
    methodology = Column(Text, nullable=True, comment="研究方法")
    results = Column(Text, nullable=True, comment="研究结果")
    discussion = Column(Text, nullable=True, comment="讨论")
    conclusion = Column(Text, nullable=True, comment="结论")
    future_work = Column(Text, nullable=True, comment="未来工作")
    
    # 参考文献
    references = Column(Text, nullable=True, comment="参考文献")
    
    # 完整内容
    full_content = Column(Text, nullable=True, comment="完整报告内容（Markdown/HTML）")
    
    # 附件
    attachments = Column(JSON, nullable=True, comment="附件列表（JSON）")
    
    # 版本和状态
    version = Column(Integer, default=1, comment="版本号")
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.DRAFT, nullable=False, index=True, comment="状态")
    language = Column(String(20), default="zh-CN", comment="语言")
    
    # 元数据
    generated_by = Column(String(100), nullable=True, comment="生成者")
    model_used = Column(String(100), nullable=True, comment="使用的模型")
    extra_metadata = Column(JSON, nullable=True, comment="额外元数据")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="reports")
    
    __table_args__ = {'comment': '研究报告表'}


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(str, Enum):
    """日志类别枚举"""
    SYSTEM = "system"
    DOCUMENT_PROCESSING = "document_processing"
    VECTORIZATION = "vectorization"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    EXPERIMENT_DESIGN = "experiment_design"
    REPORT_GENERATION = "report_generation"
    USER_ACTION = "user_action"
    API_CALL = "api_call"


class RunLog(Base):
    """
    运行日志表
    存储系统运行日志
    """
    __tablename__ = "run_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    
    # 日志信息
    level = Column(SQLEnum(LogLevel), default=LogLevel.INFO, nullable=False, index=True, comment="日志级别")
    category = Column(SQLEnum(LogCategory), default=LogCategory.SYSTEM, nullable=False, index=True, comment="日志类别")
    message = Column(Text, nullable=False, comment="日志消息")
    
    # 关联实体
    document_id = Column(String(36), nullable=True, comment="关联文档ID")
    hypothesis_id = Column(String(36), nullable=True, comment="关联假设ID")
    experiment_design_id = Column(String(36), nullable=True, comment="关联实验设计ID")
    report_id = Column(String(36), nullable=True, comment="关联报告ID")
    
    # 详细数据
    details = Column(JSON, nullable=True, comment="详细数据（JSON）")
    extra_metadata = Column(JSON, nullable=True, comment="元数据（JSON）")
    
    # 执行信息
    execution_time_ms = Column(Integer, nullable=True, comment="执行时间（毫秒）")
    success = Column(Boolean, default=True, comment="是否成功")
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_stacktrace = Column(Text, nullable=True, comment="错误堆栈")
    
    # 用户信息
    user_id = Column(String(100), nullable=True, comment="用户ID")
    user_action = Column(String(100), nullable=True, comment="用户操作")
    
    # 系统信息
    component = Column(String(100), nullable=True, comment="组件名称")
    module = Column(String(100), nullable=True, comment="模块名称")
    function = Column(String(100), nullable=True, comment="函数名称")
    line_number = Column(Integer, nullable=True, comment="行号")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project", back_populates="run_logs")
    
    __table_args__ = {'comment': '运行日志表'}
