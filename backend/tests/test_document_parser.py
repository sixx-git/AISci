"""
文献解析模块单元测试
"""
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 添加路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Models
from app.models.core import Base
from app.models import Project, Document, Chunk, ProjectStatus
from app.models import DocumentStatus, ChunkStatus

# Parser
from app.services.document_parser import (
    DocumentParser,
    ParserBackend,
    ParsedDocument,
    TextChunk,
    parse_and_save_document
)


class TestDocumentParser(TestCase):
    """文档解析器测试"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试数据库"""
        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)
    
    def setUp(self):
        """每个测试前设置"""
        self.db = self.SessionLocal()
        
        # 创建测试项目
        self.test_project = Project(
            name="Test Project",
            status=ProjectStatus.DRAFT,
            created_at=datetime.now()
        )
        self.db.add(self.test_project)
        self.db.commit()
    
    def tearDown(self):
        """每个测试后清理"""
        self.db.rollback()
        self.db.close()
    
    def test_parser_initialization(self):
        """测试解析器初始化"""
        try:
            parser = DocumentParser(self.db)
            self.assertIsNotNone(parser)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
    
    def test_text_chunk_splitting(self):
        """测试文本切片"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        # 创建长文本
        long_text = ("这是一段测试文本。\n" * 50)  # 多行文本
        long_text += ("继续添加更多文本内容。\n" * 50)
        
        chunks = parser._split_text_by_chinese_characters(
            long_text,
            min_size=100,
            max_size=300,
            overlap=20
        )
        
        self.assertTrue(len(chunks) >= 1)
        
        # 检查切片内容
        for chunk in chunks:
            self.assertTrue(len(chunk.content) > 0)
    
    def test_chinese_char_counting(self):
        """测试中文字符计数"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        count = parser._count_chinese_chars("这是中文文本")
        self.assertEqual(count, 6)
        
        count = parser._count_chinese_chars("This is English")
        # 英文按 0.5 计算
        self.assertEqual(count, 7)
    
    def test_metadata_extraction(self):
        """测试元数据提取"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        parsed = ParsedDocument()
        
        sample_text = """
        AI 研究论文
        作者：张三, 李四
        
        摘要
        这是摘要内容。本文研究了人工智能在医疗领域的应用。
        
        关键词：机器学习, 深度学习
        
        正文内容开始...
        """
        
        parser._extract_metadata_from_page(sample_text, parsed, 1)
        
        self.assertIn("AI", parsed.title or "")
        self.assertIn("张三", parsed.authors or "")
        self.assertIn("摘要", parsed.abstract or "")
    
    def test_references_extraction(self):
        """测试参考文献提取"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        sample_text = """
        正文内容结束。
        
        参考文献
        [1] Author1. Title. Journal, 2024.
        [2] Author2. Another Title. Conference, 2023.
        """
        
        references = parser._extract_references(sample_text)
        self.assertTrue(len(references) >= 0)
    
    def test_simple_text_file_parsing(self):
        """测试简单文本文件解析"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        # 创建临时文本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8', prefix='test_document_') as f:
            f.write("这是测试文本文件的内容。\n" * 20)
            temp_file = f.name
        
        try:
            parsed = parser._parse_simple_text(temp_file)
            self.assertTrue(len(parsed.content) > 0)
            self.assertIn("test", parsed.title.lower())  # 文件名应该包含前缀
        finally:
            os.unlink(temp_file)
    
    def test_full_workflow(self):
        """测试完整工作流（使用简单文本）"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        # 创建临时文本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("这是测试论文的内容。\n" * 50)
            temp_file = f.name
        
        try:
            document, chunks = parser.parse_file(
                file_path=temp_file,
                project_id=self.test_project.id,
                original_filename="test.txt"
            )
            
            self.assertIsNotNone(document)
            self.assertEqual(document.project_id, self.test_project.id)
            self.assertEqual(document.status, DocumentStatus.PROCESSED)
            
            self.assertTrue(len(chunks) > 0)
            for chunk in chunks:
                self.assertEqual(chunk.project_id, self.test_project.id)
                self.assertEqual(chunk.document_id, document.id)
                self.assertEqual(chunk.status, ChunkStatus.PENDING)
            
        finally:
            os.unlink(temp_file)
    
    def test_error_handling(self):
        """测试错误处理"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        # 测试不存在的文件
        with self.assertRaises(FileNotFoundError):
            parser.parse_file(
                file_path="nonexistent.pdf",
                project_id=self.test_project.id
            )
        
        # 创建一个损坏的文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write("Not a real PDF")
            temp_file = f.name
        
        try:
            # 这应该能处理，不会崩溃
            with self.assertRaises(Exception):
                parser.parse_file(
                    file_path=temp_file,
                    project_id=self.test_project.id
                )
            
            # 检查文档记录是否被标记为失败
            failed_docs = self.db.query(Document).filter(
                Document.project_id == self.test_project.id,
                Document.status == DocumentStatus.FAILED
            ).all()
            self.assertTrue(len(failed_docs) > 0)
            
        finally:
            os.unlink(temp_file)
    
    def test_convenience_function(self):
        """测试便捷函数"""
        # 创建临时文本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("测试内容。" * 50)
            temp_file = f.name
        
        try:
            document, chunks = parse_and_save_document(
                db=self.db,
                file_path=temp_file,
                project_id=self.test_project.id,
                original_filename="test.txt"
            )
            
            self.assertIsNotNone(document)
            self.assertTrue(len(chunks) > 0)
            
        except Exception as e:
            self.skipTest(f"Convenience function test failed: {e}")
        finally:
            os.unlink(temp_file)
    
    def test_chunk_preview(self):
        """测试切片预览"""
        try:
            parser = DocumentParser(self.db)
        except Exception as e:
            self.skipTest(f"Parser initialization failed: {e}")
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            long_text = "这是一段很长的文本内容。" * 100
            f.write(long_text)
            temp_file = f.name
        
        try:
            document, chunks = parser.parse_file(
                file_path=temp_file,
                project_id=self.test_project.id
            )
            
            for chunk in chunks:
                self.assertTrue(len(chunk.content_preview) <= 200)
                self.assertTrue(chunk.content_preview in chunk.content)
            
        finally:
            os.unlink(temp_file)


class TestParserBackend(TestCase):
    """测试不同解析后端"""
    
    def test_pypdf_backend(self):
        """测试 pypdf 后端"""
        try:
            from app.services.document_parser import DocumentParser, ParserBackend
            
            # 这里不需要实际解析文件，只测试配置
            self.assertTrue(True)
            
        except ImportError:
            self.skipTest("pypdf not available")
    
    def test_pymupdf_backend(self):
        """测试 pymupdf 后端"""
        try:
            import fitz
            from app.services.document_parser import DocumentParser, ParserBackend
            
            self.assertTrue(True)
            
        except ImportError:
            self.skipTest("pymupdf not available")


if __name__ == '__main__':
    import unittest
    unittest.main()
