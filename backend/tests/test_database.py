"""
数据库初始化和操作测试
"""
import pytest
from sqlalchemy import inspect
from datetime import datetime

from app.models.core import Base
from app.models import (
    Project, Document, Chunk, ChatMessage,
    Pipeline, PipelineStage,
    ProjectStatus, DocumentStatus, ChunkStatus
)
from app.core.database import init_db, create_tables


class TestDatabaseInit:
    """数据库初始化测试"""

    def test_database_connection(self, db_engine):
        """测试数据库连接"""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()
        assert len(tables) > 0

    def test_tables_created(self, db_engine):
        """测试数据库表是否创建成功"""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()
        
        # 检查必要的表是否存在
        required_tables = ['projects', 'documents', 'chunks', 
                          'chat_messages', 'pipelines', 'pipeline_stages']
        for table in required_tables:
            assert table in tables


class TestProjectModel:
    """项目模型测试"""

    def test_create_project(self, db_session):
        """测试创建项目"""
        project = Project(
            name="Test Project",
            description="This is a test project",
            research_question="What is X?",
            status=ProjectStatus.DRAFT,
            created_at=datetime.now()
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.status == ProjectStatus.DRAFT

    def test_update_project(self, db_session, test_project):
        """测试更新项目"""
        test_project.name = "Updated Project"
        test_project.status = ProjectStatus.IN_PROGRESS
        db_session.commit()
        db_session.refresh(test_project)
        
        assert test_project.name == "Updated Project"
        assert test_project.status == ProjectStatus.IN_PROGRESS

    def test_delete_project(self, db_session, test_project):
        """测试删除项目"""
        project_id = test_project.id
        db_session.delete(test_project)
        db_session.commit()
        
        project = db_session.query(Project).get(project_id)
        assert project is None


class TestDocumentModel:
    """文档模型测试"""

    def test_create_document(self, db_session, test_project):
        """测试创建文档"""
        document = Document(
            project_id=test_project.id,
            filename="test.md",
            title="Test Document",
            status=DocumentStatus.PENDING,
            created_at=datetime.now()
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        assert document.id is not None
        assert document.project_id == test_project.id
        assert document.filename == "test.md"

    def test_project_document_relationship(self, db_session, test_project, test_document):
        """测试项目和文档的关系"""
        assert test_document.project_id == test_project.id
        db_session.refresh(test_project)
        assert len(test_project.documents) >= 1


class TestChunkModel:
    """文本块模型测试"""

    def test_create_chunk(self, db_session, test_document):
        """测试创建文本块"""
        chunk = Chunk(
            document_id=test_document.id,
            text="This is a test chunk of text.",
            chunk_index=0,
            status=ChunkStatus.PENDING,
            created_at=datetime.now()
        )
        db_session.add(chunk)
        db_session.commit()
        db_session.refresh(chunk)
        
        assert chunk.id is not None
        assert chunk.document_id == test_document.id

    def test_document_chunk_relationship(self, db_session, test_document, test_chunks):
        """测试文档和文本块的关系"""
        db_session.refresh(test_document)
        assert len(test_document.chunks) >= len(test_chunks)
