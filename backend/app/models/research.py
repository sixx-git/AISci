from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.core import Base, BaseModel


class Evidence(BaseModel):
    """
    证据链模型
    记录每条假设背后的文献事实来源，支撑"假设—事实—文献片段—原文来源"的可追踪展示
    """
    __tablename__ = "evidences"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True, comment="项目 ID")
    hypothesis_id = Column(String(36), ForeignKey("hypotheses.id"), nullable=False, index=True, comment="关联假设 ID")
    document_id = Column(String(36), nullable=True, index=True, comment="来源文档 ID")
    chunk_id = Column(String(36), nullable=True, index=True, comment="来源 Chunk ID")

    # 证据内容
    fact_text = Column(Text, nullable=False, comment="事实陈述")
    quote_text = Column(Text, nullable=True, comment="原文引用片段")
    page_number = Column(Integer, nullable=True, comment="页码")
    relevance_score = Column(Float, default=0.0, nullable=False, comment="相关度分数 0-1")
    source_title = Column(String(500), nullable=True, comment="来源论文/文档标题")

    # 元数据
    extra_metadata = Column(Text, nullable=True, comment="额外元数据（JSON）")

    # 关系
    hypothesis = relationship("Hypothesis", backref="evidences")


class ResearchProject(Base):
    __tablename__ = "research_projects"
    
    id = Column(String(36), primary_key=True, index=True)
    topic = Column(String(255), nullable=False)
    keywords = Column(Text, nullable=True)
    research_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    execution_time = Column(Float, nullable=True)


class ExperimentDesign(BaseModel):
    """
    实验设计模型
    """
    __tablename__ = "experiment_designs"
    
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    hypothesis_id = Column(String(36), ForeignKey("hypotheses.id"), nullable=False, index=True)
    hypothesis = Column(Text, nullable=False)
    
    # 实验设计内容
    methods = Column(Text, nullable=False)
    datasets = Column(Text, nullable=False)
    source_data = Column(Text, nullable=False)
    target_data = Column(Text, nullable=False)
    baselines = Column(Text, nullable=False)
    metrics = Column(Text, nullable=False)
    experimental_steps = Column(Text, nullable=False)
    expected_results = Column(Text, nullable=False)
    limitations = Column(Text, nullable=False)
    
    # 元数据
    status = Column(String(50), default="draft", nullable=False)  # draft, ready, running, completed
    priority = Column(Integer, default=3, nullable=False)  # 1-5
    
    # 关系
    project = relationship("Project", back_populates="experiment_designs")


class SmallValidation(BaseModel):
    """
    小样验证模型
    """
    __tablename__ = "small_validations"
    
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    experiment_design_id = Column(String(36), ForeignKey("experiment_designs.id"), nullable=False, index=True)
    hypothesis = Column(Text, nullable=False)
    
    # 验证内容
    has_real_data = Column(Integer, default=0, nullable=False)  # 0: no, 1: yes
    analysis_script = Column(Text, nullable=False)  # pandas 分析脚本
    simulated_data = Column(Text, nullable=True)  # 模拟数据 JSON
    simulation_assumptions = Column(Text, nullable=True)  # 模拟假设说明
    charts = Column(Text, nullable=True)  # 图表数据 JSON 列表
    statistics = Column(Text, nullable=True)  # 统计结果 JSON
    run_log = Column(Text, nullable=True)  # 运行日志
    
    # 元数据
    status = Column(String(50), default="draft", nullable=False)  # draft, generated, running, completed
    execution_time = Column(Float, nullable=True)


class Hypothesis(BaseModel):
    """
    科学假设模型
    """
    __tablename__ = "hypotheses"
    
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    research_question = Column(Text, nullable=False)
    
    # 假设内容
    hypothesis = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    novelty = Column(Text, nullable=False)
    testability = Column(Text, nullable=False)
    required_data = Column(Text, nullable=False)
    possible_method = Column(Text, nullable=False)
    risk = Column(Text, nullable=False)
    
    # 事实绑定
    supporting_fact_ids = Column(Text, nullable=True, comment="关联的文献事实 ID 列表（JSON 数组）")
    evidence_level = Column(String(20), default="medium", nullable=False, comment="证据级别: high / medium / low")
    
    # 元数据
    status = Column(String(50), default="draft", nullable=False)  # draft, testing, accepted, rejected
    priority = Column(Integer, default=3, nullable=False)  # 1-5
    confidence = Column(Float, default=0.5, nullable=False)  # 0-1
    
    # 问题对齐
    alignment_score = Column(Integer, nullable=True, default=None, comment="问题对齐度 0-100")
    off_topic = Column(Boolean, nullable=True, default=None, comment="是否偏题")
    off_topic_reason = Column(Text, nullable=True, default=None, comment="偏题原因")
    matched_keywords = Column(Text, nullable=True, default=None, comment="匹配到的关键词（JSON 数组）")
    missing_keywords = Column(Text, nullable=True, default=None, comment="缺失的关键词（JSON 数组）")

    # 新增字段：假设与数据/问题的强关联
    question_alignment = Column(Text, nullable=True, default=None, comment="假设与研究问题的对齐说明")
    dataset_field_refs = Column(Text, nullable=True, default=None, comment="引用的数据集字段（JSON 数组）")
    data_evidence_ids = Column(Text, nullable=True, default=None, comment="引用的数据证据 ID（JSON 数组）")
    validation_target = Column(Text, nullable=True, default=None, comment="验证目标指标，如 Accuracy/F1/AUC")
    expected_measurable_effect = Column(Text, nullable=True, default=None, comment="预期的可量化效果")
    
    # 关系
    project = relationship("Project", back_populates="hypotheses")


class Dataset(BaseModel):
    """
    多模态数据集模型
    记录用户上传的观测数据、实验数据、临床数据等，支持 CSV/Excel/JSON/图像/时间序列等格式
    """
    __tablename__ = "datasets"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True, comment="所属项目 ID")
    filename = Column(String(500), nullable=False, comment="原始文件名")
    file_path = Column(String(1000), nullable=False, comment="存储路径")
    file_size = Column(Integer, nullable=True, comment="文件大小 (bytes)")
    data_type = Column(String(50), default="unknown", nullable=False, comment="数据类型: tabular/image/time_series/json/pdf/unknown")
    source_type = Column(String(50), default="upload", nullable=False, comment="来源: upload/history/public")
    n_rows = Column(Integer, nullable=True, comment="行数/样本数")
    n_columns = Column(Integer, nullable=True, comment="列数/字段数")
    columns_json = Column(Text, nullable=True, comment="列名列表（JSON 数组）")
    dtypes_json = Column(Text, nullable=True, comment="字段类型（JSON 对象）")
    missing_count = Column(Integer, nullable=True, comment="缺失值总数")
    missing_rate = Column(Float, nullable=True, comment="缺失率 0-1")
    statistics_json = Column(Text, nullable=True, comment="统计信息（JSON 对象）")
    preview_json = Column(Text, nullable=True, comment="前 N 行预览（JSON 数组）")
    preprocessing_status = Column(String(50), default="pending", nullable=False, comment="预处理状态: pending/processing/completed/failed")
    use_for_hypothesis = Column(Boolean, default=True, nullable=False, comment="是否用于假设生成")
    extra_metadata = Column(Text, nullable=True, comment="额外元数据（JSON）")

    project = relationship("Project", back_populates="datasets")


class MultimodalAsset(BaseModel):
    """
    多模态科研资产 — 文本/图像/音频及其解析结果与 evidence facts
    """
    __tablename__ = "multimodal_assets"

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=True, index=True, comment="关联 Dataset 记录")
    file_name = Column(String(500), nullable=False, comment="文件名")
    file_path = Column(String(1000), nullable=False, comment="存储路径")
    modality = Column(String(20), nullable=False, comment="text/image/audio")
    mime_type = Column(String(100), nullable=True, comment="MIME 类型")
    extracted_text = Column(Text, nullable=True, comment="文本提取/转写全文")
    extracted_summary = Column(Text, nullable=True, comment="摘要")
    evidence_facts_json = Column(Text, nullable=True, comment="Evidence Facts JSON 数组")
    metadata_json = Column(Text, nullable=True, comment="解析元数据 JSON")
    parse_status = Column(String(50), default="pending", nullable=False, comment="pending/completed/failed/warning")
    use_for_hypothesis = Column(Boolean, default=True, nullable=False, comment="是否用于假设生成")

    project = relationship("Project", backref="multimodal_assets")
    dataset = relationship("Dataset", backref="multimodal_assets")
