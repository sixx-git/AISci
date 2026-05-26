from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey
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
    
    # 元数据
    status = Column(String(50), default="draft", nullable=False)  # draft, testing, accepted, rejected
    priority = Column(Integer, default=3, nullable=False)  # 1-5
    confidence = Column(Float, default=0.5, nullable=False)  # 0-1
    
    # 关系
    project = relationship("Project", back_populates="hypotheses")
