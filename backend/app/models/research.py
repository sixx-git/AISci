from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.core import BaseModel


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


class ResearchReport(BaseModel):
    """
    研究报告模型
    """
    __tablename__ = "research_reports"
    
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    hypothesis_id = Column(String(36), ForeignKey("hypotheses.id"), nullable=True)
    experiment_design_id = Column(String(36), ForeignKey("experiment_designs.id"), nullable=True)
    small_validation_id = Column(String(36), ForeignKey("small_validations.id"), nullable=True)
    
    # 文件相关
    report_id = Column(String(36), nullable=True)  # 报告文件 ID
    pdf_generated = Column(Integer, default=0, nullable=False)  # 0: no, 1: yes
    
    # 报告内容
    title = Column(String(500), nullable=False)
    paper_title = Column(String(500), nullable=False)
    paper_abstract = Column(Text, nullable=False)
    markdown_content = Column(Text, nullable=False)
    
    # 章节内容
    problem_statement = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    technical_details = Column(Text, nullable=False)
    datasets = Column(Text, nullable=False)
    source = Column(Text, nullable=False)
    target = Column(Text, nullable=False)
    methods = Column(Text, nullable=False)
    experiments = Column(Text, nullable=False)
    results = Column(Text, nullable=False)
    references = Column(Text, nullable=False)
    
    # 元数据
    status = Column(String(50), default="draft", nullable=False)  # draft, generated, published
    version = Column(Integer, default=1, nullable=False)


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
