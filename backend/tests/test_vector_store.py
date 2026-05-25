"""
向量存储服务单元测试
"""
import os
import tempfile
import shutil
from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

import numpy as np

# 添加路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class MockEmbedding:
    """Mock Embedding 类"""
    
    def __init__(self, dimension: int = 384):
        self._dimension = dimension
    
    def embed(self, texts):
        """生成随机向量用于测试"""
        return np.random.randn(len(texts), self._dimension).astype(np.float32)
    
    @property
    def dimension(self):
        return self._dimension


class TestVectorStore(TestCase):
    """VectorStore 单元测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)
        
        # Patch 配置
        self.settings_patch = patch('app.services.vector_store.settings')
        self.mock_settings = self.settings_patch.start()
        self.mock_settings.VECTOR_STORE_PATH = self.temp_dir
        self.mock_settings.EMBEDDING_MODEL = "test-model"
        
        # Mock database session
        self.session_patch = patch('app.services.vector_store.SessionLocal')
        self.mock_session_cls = self.session_patch.start()
        self.mock_session = MagicMock()
        self.mock_session_cls.return_value = self.mock_session
        
        # Patch SentenceTransformer
        self.st_patch = patch('app.services.vector_store.SentenceTransformerEmbedding')
        self.mock_st_cls = self.st_patch.start()
        self.mock_st = MockEmbedding(384)
        self.mock_st_cls.return_value = self.mock_st
        
        from app.services.vector_store import VectorStore
        self.VectorStore = VectorStore
    
    def tearDown(self):
        """清理测试环境"""
        self.settings_patch.stop()
        self.session_patch.stop()
        self.st_patch.stop()
    
    def test_initialization(self):
        """测试初始化"""
        store = self.VectorStore(embedding=MockEmbedding(384))
        self.assertIsNotNone(store)
        self.assertEqual(store.embedding.dimension, 384)
        self.assertEqual(len(store._indexes), 0)
    
    def test_get_or_create_index(self):
        """测试获取或创建索引"""
        store = self.VectorStore(embedding=MockEmbedding(384))
        
        project_id = "test-project-1"
        
        # 第一次应该创建新索引
        index = store._get_or_create_index(project_id)
        self.assertIsNotNone(index)
        self.assertIn(project_id, store._indexes)
        
        # 第二次应该返回相同索引
        index2 = store._get_or_create_index(project_id)
        self.assertEqual(index, index2)
    
    def test_get_project_stats(self):
        """测试获取项目统计"""
        store = self.VectorStore(embedding=MockEmbedding(384))
        
        # 不存在的项目
        stats = store.get_project_stats("nonexistent")
        self.assertFalse(stats["exists"])
        self.assertEqual(stats["chunk_count"], 0)
        
        # 存在的项目
        project_id = "test-project"
        store._get_or_create_index(project_id)
        
        stats = store.get_project_stats(project_id)
        self.assertTrue(stats["exists"])
        self.assertEqual(stats["project_id"], project_id)
    
    @patch('app.services.vector_store.Chunk')
    @patch('app.services.vector_store.Document')
    def test_search_no_index(self, mock_document, mock_chunk):
        """测试无索引时的搜索"""
        store = self.VectorStore(embedding=MockEmbedding(384))
        
        results = store.search("nonexistent-project", "test query", top_k=5)
        self.assertEqual(len(results), 0)
    
    def test_delete_project_index(self):
        """测试删除项目索引"""
        store = self.VectorStore(embedding=MockEmbedding(384))
        
        project_id = "test-project"
        store._get_or_create_index(project_id)
        
        # 先保存到磁盘
        store._save_project_index(project_id)
        
        # 验证文件存在
        index_file = Path(self.temp_dir) / f"{project_id}.index"
        meta_file = Path(self.temp_dir) / f"{project_id}.meta.pkl"
        self.assertTrue(index_file.exists())
        self.assertTrue(meta_file.exists())
        
        # 删除
        success = store.delete_project_index(project_id)
        self.assertTrue(success)
        
        # 验证内存中的数据已删除
        self.assertNotIn(project_id, store._indexes)
        
        # 验证磁盘文件已删除
        self.assertFalse(index_file.exists())
        self.assertFalse(meta_file.exists())


class TestSearchResult(TestCase):
    """SearchResult 数据类测试"""
    
    def test_search_result_creation(self):
        """测试 SearchResult 创建"""
        from app.services.vector_store import SearchResult
        
        result = SearchResult(
            chunk_id="chunk-1",
            content="这是一段测试内容",
            document_id="doc-1",
            document_title="测试文档",
            document_filename="test.pdf",
            start_page=1,
            end_page=2,
            similarity=0.95,
            score=0.95
        )
        
        self.assertEqual(result.chunk_id, "chunk-1")
        self.assertEqual(result.content, "这是一段测试内容")
        self.assertEqual(result.document_title, "测试文档")
        self.assertEqual(result.similarity, 0.95)


if __name__ == '__main__':
    import unittest
    unittest.main()
