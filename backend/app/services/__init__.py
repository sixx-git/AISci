"""
服务层模块
"""
from app.services.vector_store import (
    VectorStore,
    SearchResult,
    BaseEmbedding,
    SentenceTransformerEmbedding,
    get_vector_store,
    build_vector_index,
    search_vector_store
)
from app.services.qwen_client import (
    QwenClient,
    QwenError,
    QwenAPIError,
    QwenTimeoutError,
    get_qwen_client,
    qwen_chat,
    qwen_structured_chat
)
from app.services.document_service import DocumentService
from app.services.project_service import ProjectService
from app.services.research_service import ResearchService

__all__ = [
    # 向量存储
    'VectorStore',
    'SearchResult',
    'BaseEmbedding',
    'SentenceTransformerEmbedding',
    'get_vector_store',
    'build_vector_index',
    'search_vector_store',
    
    # Qwen 客户端
    'QwenClient',
    'QwenError',
    'QwenAPIError',
    'QwenTimeoutError',
    'get_qwen_client',
    'qwen_chat',
    'qwen_structured_chat',
    
    # 业务服务
    'DocumentService',
    'ProjectService',
    'ResearchService',
]
