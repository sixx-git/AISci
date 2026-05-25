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
