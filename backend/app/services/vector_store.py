"""
向量存储服务
提供 RAG 向量检索功能，按 project_id 存储独立的 FAISS 索引
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import faiss
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.project import Chunk, Document, ChunkStatus, DocumentStatus
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SearchResult:
    """搜索结果（含完整文献元数据，供引用）"""
    chunk_id: str
    document_id: str
    content: str
    page_number: Optional[int]
    source_title: Optional[str]
    similarity_score: float
    # ── 文献引用元数据 ──
    authors: Optional[str] = None
    year: Optional[int] = None
    source_type: Optional[str] = None
    doi: Optional[str] = None
    external_id: Optional[str] = None
    source_url: Optional[str] = None


class BaseEmbedding:
    """基础 Embedding 抽象"""

    def embed(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        raise NotImplementedError


class SentenceTransformerEmbedding(BaseEmbedding):
    """Sentence-Transformers Embedding"""

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
    按 project_id 分区存储：
      storage/vector_indexes/{project_id}/index.faiss
      storage/vector_indexes/{project_id}/mapping.json
    """

    def __init__(
        self,
        embedding: Optional[BaseEmbedding] = None,
        base_path: Optional[str] = None
    ):
        self.base_path = Path(base_path or settings.VECTOR_INDEXES_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.embedding = embedding or SentenceTransformerEmbedding()

        # 内存缓存
        self._indexes: Dict[str, faiss.Index] = {}
        self._mappings: Dict[str, List[Dict[str, Any]]] = {}
        self._chunk_id_index: Dict[str, Dict[str, int]] = {}  # {project_id: {chunk_id: faiss_index}}

        self._load_all()
        logger.info(f"VectorStore initialized at {self.base_path}")

    # ─────────── 路径 ───────────

    def _project_dir(self, project_id: str) -> Path:
        """项目索引目录"""
        p = self.base_path / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _index_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "index.faiss"

    def _mapping_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "mapping.json"

    # ─────────── 加载/保存 ───────────

    def _load_all(self):
        """加载所有已存在的项目索引"""
        for d in self.base_path.iterdir():
            if not d.is_dir():
                continue
            project_id = d.name
            try:
                self._load_project(project_id)
                logger.info(f"Loaded index: {project_id}")
            except Exception as e:
                logger.error(f"Failed to load index {project_id}: {e}")

    def _load_project(self, project_id: str):
        idx_path = self._index_path(project_id)
        map_path = self._mapping_path(project_id)

        if not idx_path.exists() or not map_path.exists():
            return

        self._indexes[project_id] = faiss.read_index(str(idx_path))

        with open(map_path, "r", encoding="utf-8") as f:
            self._mappings[project_id] = json.load(f)

        # 重建 chunk_id → faiss index 查找
        self._chunk_id_index[project_id] = {
            item["chunk_id"]: i for i, item in enumerate(self._mappings[project_id])
        }

    def _save_project(self, project_id: str):
        if project_id not in self._indexes:
            logger.warning(f"No index for project {project_id}")
            return

        idx_path = self._index_path(project_id)
        map_path = self._mapping_path(project_id)

        faiss.write_index(self._indexes[project_id], str(idx_path))

        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(self._mappings[project_id], f, ensure_ascii=False, indent=2)

        logger.info(f"Saved index: {project_id} ({len(self._mappings[project_id])} chunks)")

    # ─────────── 构建索引 ───────────

    def _get_or_create_index(self, project_id: str) -> faiss.Index:
        if project_id not in self._indexes:
            self._indexes[project_id] = faiss.IndexFlatIP(self.embedding.dimension)
            self._mappings[project_id] = []
            self._chunk_id_index[project_id] = {}
            logger.info(f"Created new index: {project_id}")
        return self._indexes[project_id]

    def build_index(
        self,
        project_id: str,
        db: Optional[Session] = None
    ) -> int:
        """
        构建项目向量索引 —— 将项目下所有已处理的 Chunk 向量化并入库

        Returns:
            添加的 Chunk 数量，0 表示没有新数据
        """
        session = db or SessionLocal()
        own_session = db is None

        try:
            # 查询该项目的所有 Chunk（已处理状态）
            rows = (
                session.query(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .filter(Chunk.project_id == project_id)
                .filter(Document.status == DocumentStatus.PROCESSED)  # 只取已解析的文档
                .all()
            )

            if not rows:
                logger.warning(f"Project {project_id} has no chunks to index")
                return 0

            # 过滤掉已存在于索引中的 chunk
            existing_ids = set(self._chunk_id_index.get(project_id, {}).keys())
            new_rows = [(c, d) for c, d in rows if c.id not in existing_ids]

            if not new_rows:
                logger.info(f"Project {project_id}: all {len(rows)} chunks already indexed")
                return 0

            logger.info(f"Project {project_id}: indexing {len(new_rows)} new chunks")

            # 向量化
            texts = [c.content for c, _ in new_rows]
            embeddings = self.embedding.embed(texts)
            faiss.normalize_L2(embeddings)

            # 添加到 FAISS
            index = self._get_or_create_index(project_id)
            start_idx = len(self._mappings[project_id])
            index.add(embeddings.astype(np.float32))

            # 更新 mapping
            for i, (chunk, doc) in enumerate(new_rows):
                item = {
                    "chunk_id": chunk.id,
                    "document_id": doc.id,
                    "content": chunk.content,
                    "page_number": chunk.page_number or chunk.start_page,
                    "source_title": doc.title or doc.filename,
                    # ── 文献引用元数据 ──
                    "authors": doc.authors,
                    "year": doc.year,
                    "source_type": doc.source_type.value if doc.source_type else None,
                    "doi": doc.doi,
                    "external_id": doc.external_id,
                    "source_url": doc.source_url,
                    "faiss_index": start_idx + i,
                }
                self._mappings[project_id].append(item)
                self._chunk_id_index[project_id][chunk.id] = start_idx + i

            # 保存
            self._save_project(project_id)

            # 更新 Chunk 状态
            for chunk, _ in new_rows:
                chunk.status = ChunkStatus.READY
                chunk.embedding_model = settings.EMBEDDING_MODEL
                chunk.dimension = self.embedding.dimension

            session.commit()
            logger.info(f"Project {project_id}: built index with {len(new_rows)} chunks")
            return len(new_rows)

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to build index for {project_id}: {e}", exc_info=True)
            raise
        finally:
            if own_session:
                session.close()

    # ─────────── 搜索 ───────────

    def search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        db: Optional[Session] = None
    ) -> List[SearchResult]:
        """
        向量搜索

        Returns:
            SearchResult 列表，按相似度降序
        """
        if project_id not in self._indexes:
            raise ValueError(f"项目 {project_id} 尚未构建向量索引，请先构建索引")

        mapping = self._mappings.get(project_id)
        if not mapping:
            raise ValueError(f"项目 {project_id} 没有已索引的切片")

        index = self._indexes[project_id]

        # 查询向量化
        q_emb = self.embedding.embed([query])
        faiss.normalize_L2(q_emb)

        k = min(top_k, len(mapping))
        scores, indices = index.search(q_emb.astype(np.float32), k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or int(idx) >= len(mapping):
                continue
            item = mapping[int(idx)]
            results.append(SearchResult(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                content=item["content"],
                page_number=item.get("page_number"),
                source_title=item.get("source_title"),
                similarity_score=round(float(score), 4),
                # ── 文献引用元数据 ──
                authors=item.get("authors"),
                year=item.get("year"),
                source_type=item.get("source_type"),
                doi=item.get("doi"),
                external_id=item.get("external_id"),
                source_url=item.get("source_url"),
            ))

        logger.info(f"Search {project_id}: {len(results)} results for '{query[:50]}...'")
        return results

    # ─────────── 管理 ───────────

    def delete_project_index(self, project_id: str) -> bool:
        try:
            self._indexes.pop(project_id, None)
            self._mappings.pop(project_id, None)
            self._chunk_id_index.pop(project_id, None)

            for f in [self._index_path(project_id), self._mapping_path(project_id)]:
                if f.exists():
                    f.unlink()

            d = self._project_dir(project_id)
            if d.exists() and not any(d.iterdir()):
                d.rmdir()

            logger.info(f"Deleted index: {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index {project_id}: {e}", exc_info=True)
            return False

    def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        if project_id not in self._indexes:
            return {
                "project_id": project_id,
                "exists": False,
                "chunk_count": 0,
            }
        return {
            "project_id": project_id,
            "exists": True,
            "chunk_count": len(self._mappings.get(project_id, [])),
            "dimension": self.embedding.dimension,
            "embedding_model": settings.EMBEDDING_MODEL,
            "index_file": str(self._index_path(project_id)),
            "mapping_file": str(self._mapping_path(project_id)),
        }

    def has_index(self, project_id: str) -> bool:
        return project_id in self._indexes and len(self._mappings.get(project_id, [])) > 0


# ─────────── 单例 ───────────

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def build_vector_index(project_id: str, db: Optional[Session] = None) -> int:
    """便捷函数：构建向量索引"""
    return get_vector_store().build_index(project_id, db)


def search_vector_store(
    project_id: str,
    query: str,
    top_k: int = 5,
    db: Optional[Session] = None
) -> List[SearchResult]:
    """便捷函数：向量搜索"""
    return get_vector_store().search(project_id, query, top_k, db)