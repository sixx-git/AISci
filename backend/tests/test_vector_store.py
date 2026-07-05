"""
向量存储服务单元测试（Zvec 后端）
"""
import tempfile
import shutil
from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class MockEmbedding:
    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    def embed(self, texts):
        return np.random.randn(len(texts), self._dimension).astype(np.float32)

    @property
    def dimension(self):
        return self._dimension


class TestVectorStore(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

        self.settings_patch = patch("app.services.vector_store.settings")
        self.mock_settings = self.settings_patch.start()
        self.mock_settings.VECTOR_INDEXES_PATH = self.temp_dir
        self.mock_settings.EMBEDDING_MODEL = "test-model"
        self.mock_settings.VECTOR_BACKEND = "zvec"

        self.session_patch = patch("app.services.vector_store.SessionLocal")
        self.mock_session_cls = self.session_patch.start()
        self.mock_session = MagicMock()
        self.mock_session_cls.return_value = self.mock_session

        self.st_patch = patch("app.services.vector_store.SentenceTransformerEmbedding")
        self.mock_st_cls = self.st_patch.start()
        self.mock_st_cls.return_value = MockEmbedding(384)

        from app.services.vector_store import VectorStore
        self.VectorStore = VectorStore

    def _cleanup(self):
        self.settings_patch.stop()
        self.session_patch.stop()
        self.st_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        store = self.VectorStore(embedding=MockEmbedding(384))
        self.assertIsNotNone(store)
        self.assertEqual(store.embedding.dimension, 384)

    def test_get_project_stats_without_db(self):
        from app.services.vector_store import read_project_index_stats
        stats = read_project_index_stats("nonexistent")
        self.assertFalse(stats["exists"])
        self.assertEqual(stats["chunk_count"], 0)
        self.assertEqual(stats["vector_backend"], "zvec")

    def test_search_no_index_raises(self):
        store = self.VectorStore(embedding=MockEmbedding(384))
        with self.assertRaises(ValueError):
            store.search("nonexistent-project", "test query", top_k=5)

    def test_delete_project_index(self):
        import zvec
        from zvec import CollectionSchema, VectorSchema, FieldSchema, DataType, Doc

        project_id = "test-project"
        path = str(Path(self.temp_dir) / project_id)
        schema = CollectionSchema(
            name="literature_chunks",
            vectors=VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 4),
            fields=[FieldSchema("content", DataType.STRING)],
        )
        col = zvec.create_and_open(path=path, schema=schema)
        col.insert(Doc(id="c1", vectors={"embedding": [0.1, 0.2, 0.3, 0.4]}, fields={"content": "x"}))
        col.destroy()

        store = self.VectorStore(embedding=MockEmbedding(384))
        store._collections[project_id] = zvec.create_and_open(
            path=path,
            schema=schema,
        )
        store._collections[project_id].insert(
            Doc(id="c1", vectors={"embedding": [0.1, 0.2, 0.3, 0.4]}, fields={"content": "x"})
        )

        success = store.delete_project_index(project_id)
        self.assertTrue(success)
        self.assertNotIn(project_id, store._collections)

    @patch("app.services.vector_store.Chunk")
    @patch("app.services.vector_store.Document")
    def test_build_index_incremental_empty(self, mock_document, mock_chunk):
        store = self.VectorStore(embedding=MockEmbedding(384))
        self.mock_session.query.return_value.join.return_value.filter.return_value.filter.return_value.all.return_value = []
        added = store.build_index("proj-1", db=self.mock_session, rebuild=False)
        self.assertEqual(added, 0)


class TestSearchResult(TestCase):
    def test_search_result_creation(self):
        from app.services.vector_store import SearchResult

        result = SearchResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="这是一段测试内容",
            page_number=1,
            source_title="测试文档",
            similarity_score=0.95,
        )
        self.assertEqual(result.chunk_id, "chunk-1")
        self.assertEqual(result.similarity_score, 0.95)


class TestSyncHelpers(TestCase):
    def test_sync_delegates_to_rebuild(self):
        with patch("app.services.vector_store.get_vector_store") as mock_get:
            mock_store = MagicMock()
            mock_get.return_value = mock_store
            mock_store.build_index.return_value = 3

            from app.services.vector_store import sync_project_index
            db = MagicMock()
            count = sync_project_index("proj-1", db=db)

            mock_store.build_index.assert_called_once_with("proj-1", db, rebuild=True)
            self.assertEqual(count, 3)
