from sqlalchemy import Column, String, Text, DateTime, Integer, Float
from sqlalchemy.sql import func
from app.core.database import Base


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
