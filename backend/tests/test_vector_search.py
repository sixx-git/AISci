"""
向量检索服务测试
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from app.services.vector_service import VectorService, _is_zvec_collection


class TestVectorService:
    """Chat VectorService（Zvec 后端）"""

    @pytest.fixture
    def mock_embedding(self):
        with patch("app.services.vector_service.SentenceTransformerEmbedding") as mock_cls:
            mock = Mock()
            mock.dimension = 384
            mock.embed = Mock(return_value=np.random.rand(1, 384).astype(np.float32))
            mock_cls.return_value = mock
            yield mock

    @pytest.fixture
    def vector_service(self, mock_embedding, tmp_path, monkeypatch):
        chat_path = str(tmp_path / "chat_vectors")
        monkeypatch.setattr(
            "app.services.vector_service.settings.VECTOR_STORE_PATH",
            chat_path,
        )
        return VectorService()

    def test_service_initialization(self, vector_service):
        assert vector_service is not None
        assert vector_service.dimension == 384

    def test_search_without_documents(self, vector_service):
        import asyncio
        context, references = asyncio.run(vector_service.search("test"))
        assert context == ""
        assert references == []

    def test_add_and_search(self, vector_service, mock_embedding):
        import asyncio

        mock_embedding.embed = Mock(
            side_effect=lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        )

        asyncio.run(vector_service.add_document("doc1", "hello world " * 30))
        context, refs = asyncio.run(vector_service.search("hello", top_k=3))
        assert context
        assert "doc1" in refs
        assert _is_zvec_collection(vector_service.collection_path)


class TestVectorSearchAPI:
    """向量搜索 API 测试"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_index_stats_endpoint(self, client, db_session, test_project):
        with patch("app.api.vector_search.read_project_index_stats") as mock_stats:
            mock_stats.return_value = {
                "project_id": str(test_project.id),
                "exists": False,
                "chunk_count": 0,
                "db_chunk_count": 0,
                "in_sync": True,
                "dimension": None,
                "embedding_model": "test-model",
                "vector_backend": "zvec",
                "index_file": None,
                "mapping_file": None,
                "legacy_faiss": False,
            }

            response = client.get(f"/api/v1/vector-search/index/{test_project.id}/stats")
            assert response.status_code == 200
            body = response.json()
            assert body["code"] == 200
            assert body["data"]["in_sync"] is True
