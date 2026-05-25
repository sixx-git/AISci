"""
健康检查 API 测试
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """创建测试客户端 fixture"""
    return TestClient(app)


class TestHealthCheck:
    """健康检查测试"""

    def test_root_endpoint(self, client):
        """测试根路径端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "name" in data["data"]
        assert "version" in data["data"]
        assert "AI Scientist" in data["message"]

    def test_health_check_endpoint(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "healthy"
        assert "version" in data["data"]
        assert "正常" in data["message"]

    def test_api_docs_available(self, client):
        """测试 API 文档是否可以访问"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_available(self, client):
        """测试 ReDoc 文档是否可以访问"""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
