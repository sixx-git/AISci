"""
Pytest 配置文件
提供测试用的 fixtures 和配置
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.core import Base
from app.models import Project, Document, Chunk, ProjectStatus, DocumentStatus, ChunkStatus
from datetime import datetime


@pytest.fixture(scope="session")
def db_engine():
    """创建测试数据库引擎（内存 SQLite）"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """创建数据库会话 fixture"""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_project(db_session):
    """创建测试项目 fixture"""
    project = Project(
        name="Test Project",
        description="A test project for AI Scientist",
        research_question="What is the impact of urban green space on heat island effect?",
        status=ProjectStatus.DRAFT,
        created_at=datetime.now()
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_document(db_session, test_project):
    """创建测试文档 fixture"""
    document = Document(
        project_id=test_project.id,
        filename="test_document.md",
        title="Test Document",
        status=DocumentStatus.PROCESSED,
        created_at=datetime.now()
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture
def test_chunks(db_session, test_document):
    """创建测试文本块 fixture"""
    chunks_data = [
        {
            "text": "城市热岛效应是指城市中心温度高于郊区的现象。",
            "chunk_index": 0,
            "embedding": [0.1, 0.2, 0.3]
        },
        {
            "text": "绿化覆盖率与热岛强度呈负相关关系。",
            "chunk_index": 1,
            "embedding": [0.4, 0.5, 0.6]
        }
    ]
    
    chunks = []
    for data in chunks_data:
        chunk = Chunk(
            document_id=test_document.id,
            text=data["text"],
            chunk_index=data["chunk_index"],
            embedding=data["embedding"],
            status=ChunkStatus.EMBEDDED,
            created_at=datetime.now()
        )
        chunks.append(chunk)
        db_session.add(chunk)
    
    db_session.commit()
    for chunk in chunks:
        db_session.refresh(chunk)
    
    return chunks
