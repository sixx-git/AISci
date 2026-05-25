"""
向量存储服务
提供 RAG 向量检索功能
"""
import os
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import faiss
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.project import Chunk, Document, ChunkStatus
from app.core.database import SessionLocal

# 配置日志
logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SearchResult:
    """搜索结果数据类"""
    chunk_id: str
    content: str
    document_id: str
    document_title: Optional[str]
    document_filename: Optional[str]
    start_page: Optional[int]
    end_page: Optional[int]
    similarity: float
    score: float


class BaseEmbedding:
    """基础 Embedding 抽象类"""
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        向量化文本列表
        
        Args:
            texts: 文本列表
            
        Returns:
            向量矩阵 (num_texts, dimension)
        """
        raise NotImplementedError
    
    @property
    def dimension(self) -> int:
        """向量维度"""
        raise NotImplementedError


class SentenceTransformerEmbedding(BaseEmbedding):
    """Sentence-Transformers Embedding 实现"""
    
    def __init__(self, model_name: Optional[str] = None):
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name or settings.EMBEDDING_MODEL
        logger.info(f"Loading embedding model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded, dimension: {self._dimension}")
    
    def embed(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(texts, show_progress_bar=False)
    
    @property
    def dimension(self) -> int:
        return self._dimension


class VectorStore:
    """
    FAISS 向量存储管理器
    按 project_id 分区存储向量索引
    """
    
    def __init__(
        self,
        embedding: Optional[BaseEmbedding] = None,
        base_path: Optional[str] = None
    ):
        """
        初始化向量存储
        
        Args:
            embedding: Embedding 实例，默认使用 SentenceTransformer
            base_path: 索引存储基础路径
        """
        self.base_path = Path(base_path or settings.VECTOR_STORE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Embedding
        self.embedding = embedding or SentenceTransformerEmbedding()
        
        # 存储各项目的索引和映射
        self._indexes: Dict[str, faiss.Index] = {}
        self._chunk_maps: Dict[str, List[str]] = {}  # {project_id: [chunk_id, ...]}
        self._chunk_info: Dict[str, Dict[str, Any]] = {}  # {chunk_id: {document_title, ...}}
        
        # 加载已存在的索引
        self._load_all_indexes()
        
        logger.info(f"VectorStore initialized at {self.base_path}")
    
    def _get_project_index_path(self, project_id: str) -> Tuple[Path, Path]:
        """
        获取项目索引的文件路径
        
        Args:
            project_id: 项目ID
            
        Returns:
            (index_file, metadata_file)
        """
        index_file = self.base_path / f"{project_id}.index"
        metadata_file = self.base_path / f"{project_id}.meta.pkl"
        return index_file, metadata_file
    
    def _load_all_indexes(self):
        """加载所有已存在的项目索引"""
        for index_file in self.base_path.glob("*.index"):
            project_id = index_file.stem
            try:
                self._load_project_index(project_id)
                logger.info(f"Loaded index for project: {project_id}")
            except Exception as e:
                logger.error(f"Failed to load index for project {project_id}: {e}")
    
    def _load_project_index(self, project_id: str):
        """
        加载指定项目的索引
        
        Args:
            project_id: 项目ID
        """
        index_file, metadata_file = self._get_project_index_path(project_id)
        
        if index_file.exists() and metadata_file.exists():
            # 加载 FAISS 索引
            index = faiss.read_index(str(index_file))
            self._indexes[project_id] = index
            
            # 加载元数据
            with open(metadata_file, "rb") as f:
                metadata = pickle.load(f)
                self._chunk_maps[project_id] = metadata.get("chunk_ids", [])
                self._chunk_info.update(metadata.get("chunk_info", {}))
    
    def _save_project_index(self, project_id: str):
        """
        保存指定项目的索引
        
        Args:
            project_id: 项目ID
        """
        index_file, metadata_file = self._get_project_index_path(project_id)
        
        if project_id not in self._indexes:
            logger.warning(f"No index for project {project_id} to save")
            return
        
        # 保存 FAISS 索引
        faiss.write_index(self._indexes[project_id], str(index_file))
        
        # 保存元数据
        chunk_info_subset = {
            cid: self._chunk_info[cid] 
            for cid in self._chunk_maps.get(project_id, [])
            if cid in self._chunk_info
        }
        
        metadata = {
            "project_id": project_id,
            "chunk_ids": self._chunk_maps.get(project_id, []),
            "chunk_info": chunk_info_subset,
            "dimension": self.embedding.dimension,
            "embedding_model": settings.EMBEDDING_MODEL
        }
        
        with open(metadata_file, "wb") as f:
            pickle.dump(metadata, f)
        
        logger.info(f"Saved index for project: {project_id} ({len(metadata['chunk_ids'])} chunks)")
    
    def _get_or_create_index(self, project_id: str) -> faiss.Index:
        """
        获取或创建项目的 FAISS 索引
        
        Args:
            project_id: 项目ID
            
        Returns:
            FAISS 索引实例
        """
        if project_id not in self._indexes:
            # 创建新索引，使用 Inner Product (余弦相似度)
            index = faiss.IndexFlatIP(self.embedding.dimension)
            self._indexes[project_id] = index
            self._chunk_maps[project_id] = []
            logger.info(f"Created new index for project: {project_id}")
        
        return self._indexes[project_id]
    
    def add_chunks(
        self,
        project_id: str,
        db: Optional[Session] = None
    ) -> int:
        """
        将项目的所有 Chunk 添加到向量索引
        
        Args:
            project_id: 项目ID
            db: 数据库会话，可选
            
        Returns:
            添加的 Chunk 数量
        """
        session = db or SessionLocal()
        try:
            # 查询该项目所有未向量化的 Chunk
            chunks = (
                session.query(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .filter(Chunk.project_id == project_id)
                .filter(Chunk.status != ChunkStatus.READY)
                .all()
            )
            
            if not chunks:
                # 检查是否有已经向量化但索引中没有的
                chunks = (
                    session.query(Chunk, Document)
                    .join(Document, Chunk.document_id == Document.id)
                    .filter(Chunk.project_id == project_id)
                    .all()
                )
                existing_chunk_ids = set(self._chunk_maps.get(project_id, []))
                chunks = [c for c in chunks if c[0].id not in existing_chunk_ids]
                
                if not chunks:
                    logger.info(f"No new chunks to add for project {project_id}")
                    return 0
            
            logger.info(f"Found {len(chunks)} chunks to add for project {project_id}")
            
            # 准备数据
            chunk_texts = []
            chunk_ids = []
            chunk_info_list = []
            
            for chunk, doc in chunks:
                chunk_texts.append(chunk.content)
                chunk_ids.append(chunk.id)
                
                chunk_info_list.append({
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "document_id": doc.id,
                    "document_title": doc.title,
                    "document_filename": doc.filename,
                    "start_page": chunk.start_page,
                    "end_page": chunk.end_page
                })
            
            # 向量化
            logger.info(f"Embedding {len(chunk_texts)} chunks...")
            embeddings = self.embedding.embed(chunk_texts)
            
            # 归一化向量（用于余弦相似度）
            faiss.normalize_L2(embeddings)
            
            # 添加到索引
            index = self._get_or_create_index(project_id)
            index.add(embeddings.astype(np.float32))
            
            # 更新映射
            if project_id not in self._chunk_maps:
                self._chunk_maps[project_id] = []
            
            for chunk_id, chunk_info in zip(chunk_ids, chunk_info_list):
                self._chunk_maps[project_id].append(chunk_id)
                self._chunk_info[chunk_id] = chunk_info
            
            # 保存索引
            self._save_project_index(project_id)
            
            # 更新数据库中的 Chunk 状态
            for chunk, _ in chunks:
                chunk.status = ChunkStatus.READY
                chunk.embedding_model = settings.EMBEDDING_MODEL
                chunk.dimension = self.embedding.dimension
            
            session.commit()
            
            logger.info(f"Successfully added {len(chunks)} chunks to project {project_id}")
            return len(chunks)
        
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add chunks for project {project_id}: {e}", exc_info=True)
            raise
        finally:
            if not db:
                session.close()
    
    def search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        db: Optional[Session] = None
    ) -> List[SearchResult]:
        """
        在项目向量索引中搜索相关 Chunk
        
        Args:
            project_id: 项目ID
            query: 查询文本
            top_k: 返回前 K 个结果
            db: 数据库会话，可选
            
        Returns:
            SearchResult 列表，按相似度降序排列
        """
        if project_id not in self._indexes:
            logger.warning(f"No index found for project {project_id}")
            return []
        
        if len(self._chunk_maps.get(project_id, [])) == 0:
            logger.warning(f"No chunks in index for project {project_id}")
            return []
        
        try:
            # 向量化查询
            query_embedding = self.embedding.embed([query])
            faiss.normalize_L2(query_embedding)
            
            # 搜索
            index = self._indexes[project_id]
            scores, indices = index.search(query_embedding.astype(np.float32), top_k)
            
            # 构建结果
            results = []
            chunk_ids = self._chunk_maps[project_id]
            
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(chunk_ids):
                    continue
                
                chunk_id = chunk_ids[idx]
                
                if chunk_id in self._chunk_info:
                    info = self._chunk_info[chunk_id]
                    results.append(SearchResult(
                        chunk_id=chunk_id,
                        content=info["content"],
                        document_id=info["document_id"],
                        document_title=info["document_title"],
                        document_filename=info["document_filename"],
                        start_page=info["start_page"],
                        end_page=info["end_page"],
                        similarity=float(score),
                        score=float(score)
                    ))
            
            logger.info(f"Search completed for project {project_id}, found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Search failed for project {project_id}: {e}", exc_info=True)
            raise
    
    def delete_project_index(self, project_id: str) -> bool:
        """
        删除项目的向量索引
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否成功
        """
        if project_id not in self._indexes:
            return True
        
        try:
            # 删除内存中的数据
            del self._indexes[project_id]
            
            chunk_ids = self._chunk_maps.get(project_id, [])
            for chunk_id in chunk_ids:
                if chunk_id in self._chunk_info:
                    del self._chunk_info[chunk_id]
            
            if project_id in self._chunk_maps:
                del self._chunk_maps[project_id]
            
            # 删除磁盘文件
            index_file, metadata_file = self._get_project_index_path(project_id)
            
            if index_file.exists():
                index_file.unlink()
            
            if metadata_file.exists():
                metadata_file.unlink()
            
            logger.info(f"Deleted index for project: {project_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete index for project {project_id}: {e}", exc_info=True)
            return False
    
    def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目索引统计信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            统计信息字典
        """
        if project_id not in self._indexes:
            return {
                "project_id": project_id,
                "exists": False,
                "chunk_count": 0
            }
        
        index = self._indexes[project_id]
        return {
            "project_id": project_id,
            "exists": True,
            "chunk_count": len(self._chunk_maps.get(project_id, [])),
            "dimension": self.embedding.dimension,
            "index_type": type(index).__name__,
            "embedding_model": settings.EMBEDDING_MODEL
        }


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    获取 VectorStore 单例
    
    Returns:
        VectorStore 实例
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# 便捷函数
def add_chunks_to_vector_store(project_id: str, db: Optional[Session] = None) -> int:
    """便捷函数：添加 Chunk 到向量索引"""
    return get_vector_store().add_chunks(project_id, db)


def search_vector_store(
    project_id: str,
    query: str,
    top_k: int = 5,
    db: Optional[Session] = None
) -> List[SearchResult]:
    """便捷函数：向量搜索"""
    return get_vector_store().search(project_id, query, top_k, db)
