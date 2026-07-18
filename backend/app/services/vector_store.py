"""
向量存储服务
提供 RAG 向量检索功能，按 project_id 存储独立的 Zvec Collection（嵌入式向量库）
"""
import logging
import shutil
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.project import Chunk, Document, ChunkStatus, DocumentStatus
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()

VECTOR_FIELD = "embedding"
COLLECTION_NAME = "literature_chunks"


def _document_publication_year(doc: Document) -> Optional[int]:
    """从 publication_date 或 metadata_json 提取发表年份。"""
    meta = doc.metadata_json or {}
    year = meta.get("year")
    if year is not None:
        try:
            return int(year)
        except (ValueError, TypeError):
            pass
    if doc.publication_date:
        return doc.publication_date.year
    return None


def _l2_normalize(arr: np.ndarray) -> np.ndarray:
    """L2 归一化（配合 IP 度量等价于余弦相似度）。"""
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return arr / norms


def _is_zvec_collection(path) -> bool:
    from pathlib import Path
    p = Path(path)
    if not p.is_dir():
        return False
    return any(p.glob("manifest.*"))


def _is_legacy_faiss_index(path) -> bool:
    from pathlib import Path
    p = Path(path)
    return (p / "index.faiss").exists() or (p / "mapping.json").exists()


@dataclass
class SearchResult:
    """搜索结果（含完整文献元数据，供引用）"""
    chunk_id: str
    document_id: str
    content: str
    page_number: Optional[int]
    source_title: Optional[str]
    similarity_score: float
    authors: Optional[str] = None
    year: Optional[int] = None
    source_type: Optional[str] = None
    doi: Optional[str] = None
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    fallback: bool = False


class BaseEmbedding:
    """基础 Embedding 抽象"""

    def embed(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        raise NotImplementedError


def _load_sentence_transformer(model_name: str, *, local_only: bool = True):
    """加载 SentenceTransformer，兼容 2.x（local_files_only 走 model_kwargs）与新版 API。"""
    from sentence_transformers import SentenceTransformer

    st_kwargs: Dict[str, Any] = {}
    if local_only:
        st_kwargs = {
            "model_kwargs": {"local_files_only": True},
            "tokenizer_kwargs": {"local_files_only": True},
        }
    try:
        return SentenceTransformer(model_name, **st_kwargs)
    except TypeError:
        if st_kwargs:
            return SentenceTransformer(model_name)
        raise


class SentenceTransformerEmbedding(BaseEmbedding):
    """Sentence-Transformers Embedding"""

    def __init__(self, model_name: Optional[str] = None):
        import os

        endpoint = (settings.HF_ENDPOINT or "").strip().rstrip("/")
        if endpoint:
            os.environ["HF_ENDPOINT"] = endpoint

        self.model_name = model_name or settings.EMBEDDING_MODEL
        logger.info(f"Loading embedding model: {self.model_name}")
        try:
            self._model = _load_sentence_transformer(self.model_name, local_only=True)
        except (OSError, ValueError) as exc:
            logger.warning(
                "本地未找到 embedding 模型 %s，尝试在线下载: %s",
                self.model_name,
                exc,
            )
            self._model = _load_sentence_transformer(self.model_name, local_only=False)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded, dimension: {self._dimension}")

    def embed(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(texts, show_progress_bar=False)

    @property
    def dimension(self) -> int:
        return self._dimension


QWEN_EMBEDDING_MODELS = frozenset({
    "text-embedding-v3",
    "text-embedding-v4",
    "text-embedding-v2",
    "text-embedding-v1",
})


class QwenDashScopeEmbedding(BaseEmbedding):
    """DashScope 千问文本向量（OpenAI 兼容 /embeddings，复用 QWEN_API_KEY）。"""

    BATCH_SIZE = 10
    DEFAULT_DIMENSION = 1024

    def __init__(self, model_name: Optional[str] = None, dimension: Optional[int] = None):
        from openai import OpenAI

        from app.core.llm_runtime import get_effective_api_key, get_effective_base_url

        raw = (model_name or settings.EMBEDDING_MODEL or "").strip()
        if raw in QWEN_EMBEDDING_MODELS:
            self.model_name = raw
        else:
            self.model_name = "text-embedding-v3"
            if raw and raw not in QWEN_EMBEDDING_MODELS:
                logger.info(
                    "EMBEDDING_BACKEND=qwen，将 %s 映射为 %s",
                    raw,
                    self.model_name,
                )

        dim_cfg = dimension if dimension is not None else settings.EMBEDDING_DIMENSION
        self._dimension = int(dim_cfg) if dim_cfg and int(dim_cfg) > 0 else self.DEFAULT_DIMENSION
        self._client = None

        if settings.USE_MOCK_LLM:
            logger.info("Mock LLM 模式：千问 embedding 使用确定性伪向量")
            return

        api_key = get_effective_api_key()
        if not api_key:
            raise ValueError(
                "EMBEDDING_BACKEND=qwen 需要配置 QWEN_API_KEY（与对话模型共用）"
            )
        from app.services.qwen_client import build_dashscope_http_client

        self._client = OpenAI(
            api_key=api_key,
            base_url=get_effective_base_url(),
            http_client=build_dashscope_http_client(timeout=180.0),
        )
        logger.info(
            "千问 embedding 已就绪: model=%s, dimension=%s",
            self.model_name,
            self._dimension,
        )

    def _mock_embed(self, texts: List[str]) -> np.ndarray:
        out = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            seed = abs(hash(f"{self.model_name}:{text}")) % (2**32)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(self._dimension).astype(np.float32)
            out[i] = vec / max(np.linalg.norm(vec), 1e-12)
        return out

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)

        if settings.USE_MOCK_LLM or self._client is None:
            return self._mock_embed(texts)

        from openai import APIError, APIConnectionError, APITimeoutError

        all_rows: List[List[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = [
                t if isinstance(t, str) and t.strip() else " "
                for t in texts[start : start + self.BATCH_SIZE]
            ]
            kwargs: Dict[str, Any] = {
                "model": self.model_name,
                "input": batch,
                "encoding_format": "float",
            }
            if self.model_name in ("text-embedding-v3", "text-embedding-v4"):
                kwargs["dimensions"] = self._dimension

            try:
                resp = self._client.embeddings.create(**kwargs)
            except (APIError, APIConnectionError, APITimeoutError) as exc:
                raise RuntimeError(f"千问 embedding API 调用失败: {exc}") from exc

            ordered = sorted(resp.data, key=lambda item: item.index)
            for item in ordered:
                all_rows.append(list(item.embedding))

        arr = np.asarray(all_rows, dtype=np.float32)
        if arr.ndim == 2 and arr.shape[1] > 0:
            self._dimension = int(arr.shape[1])
        return arr

    @property
    def dimension(self) -> int:
        return self._dimension


def create_embedding(model_name: Optional[str] = None) -> BaseEmbedding:
    """按 EMBEDDING_BACKEND 创建 embedding 实现。"""
    backend = (settings.EMBEDDING_BACKEND or "sentence_transformers").strip().lower()
    if backend in ("qwen", "dashscope", "openai"):
        return QwenDashScopeEmbedding(model_name=model_name)
    return SentenceTransformerEmbedding(model_name=model_name)


def _build_collection_schema(dimension: int):
    import zvec
    from zvec import CollectionSchema, VectorSchema, FieldSchema, DataType, FlatIndexParam

    return CollectionSchema(
        name=COLLECTION_NAME,
        vectors=VectorSchema(
            VECTOR_FIELD,
            DataType.VECTOR_FP32,
            dimension,
            index_param=FlatIndexParam(),
        ),
        fields=[
            FieldSchema("document_id", DataType.STRING),
            FieldSchema("content", DataType.STRING),
            FieldSchema("page_number", DataType.INT32, nullable=True),
            FieldSchema("source_title", DataType.STRING, nullable=True),
            FieldSchema("authors", DataType.STRING, nullable=True),
            FieldSchema("year", DataType.INT32, nullable=True),
            FieldSchema("source_type", DataType.STRING, nullable=True),
            FieldSchema("doi", DataType.STRING, nullable=True),
            FieldSchema("external_id", DataType.STRING, nullable=True),
            FieldSchema("source_url", DataType.STRING, nullable=True),
            FieldSchema("fallback", DataType.BOOL, nullable=True),
        ],
    )


def _chunk_to_doc(chunk: Chunk, doc: Document, vector: List[float]):
    from zvec import Doc

    return Doc(
        id=chunk.id,
        vectors={VECTOR_FIELD: vector},
        fields={
            "document_id": doc.id,
            "content": chunk.content,
            "page_number": chunk.page_number or chunk.start_page,
            "source_title": doc.title or doc.filename,
            "authors": doc.authors,
            "year": _document_publication_year(doc),
            "source_type": doc.source_type.value if doc.source_type else None,
            "doi": doc.doi,
            "external_id": doc.external_id,
            "source_url": doc.source_url,
            "fallback": bool((doc.metadata_json or {}).get("fallback", False)) if doc.metadata_json else False,
        },
    )


def _doc_to_search_result(doc) -> SearchResult:
    fields = doc.fields or {}
    return SearchResult(
        chunk_id=doc.id,
        document_id=fields.get("document_id") or "",
        content=fields.get("content") or "",
        page_number=fields.get("page_number"),
        source_title=fields.get("source_title"),
        similarity_score=round(float(getattr(doc, "score", 0.0) or 0.0), 4),
        authors=fields.get("authors"),
        year=fields.get("year"),
        source_type=fields.get("source_type"),
        doi=fields.get("doi"),
        external_id=fields.get("external_id"),
        source_url=fields.get("source_url"),
        fallback=bool(fields.get("fallback", False)),
    )


class VectorStore:
    """
    Zvec 向量存储管理器
    按 project_id 分区存储：
      storage/vector_indexes/{project_id}/   ← Zvec Collection 目录
    """

    def __init__(
        self,
        embedding: Optional[BaseEmbedding] = None,
        base_path: Optional[str] = None,
    ):
        from pathlib import Path

        self.base_path = Path(base_path or settings.VECTOR_INDEXES_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self._embedding = embedding
        self._collections: Dict[str, Any] = {}
        self._collection_lock = threading.Lock()

        self._load_all()
        logger.info(f"VectorStore (Zvec) initialized at {self.base_path}")

    @property
    def embedding(self) -> BaseEmbedding:
        if self._embedding is None:
            self._embedding = create_embedding()
        return self._embedding

    def _project_dir(self, project_id: str):
        from pathlib import Path

        self.base_path.mkdir(parents=True, exist_ok=True)
        return self.base_path / project_id

    def _collection_path(self, project_id: str) -> str:
        return str(self._project_dir(project_id))

    def _ensure_zvec_create_path(self, path: str) -> None:
        """Zvec create_and_open 要求路径不存在；清理空目录或残留非 Zvec 目录。"""
        from pathlib import Path

        p = Path(path)
        if not p.exists():
            return
        if _is_zvec_collection(p):
            return
        shutil.rmtree(p, ignore_errors=True)

    def _load_all(self):
        for d in self.base_path.iterdir():
            if not d.is_dir():
                continue
            if _is_zvec_collection(d):
                logger.info(f"Found Zvec collection: {d.name}")

    def _open_collection(self, project_id: str, *, create: bool = False):
        import zvec

        if project_id in self._collections:
            return self._collections[project_id]

        path = self._collection_path(project_id)
        with self._collection_lock:
            if project_id in self._collections:
                return self._collections[project_id]

            if _is_zvec_collection(path):
                col = zvec.open(path)
            elif create:
                self._ensure_zvec_create_path(path)
                schema = _build_collection_schema(self.embedding.dimension)
                col = zvec.create_and_open(path=path, schema=schema)
            else:
                return None

            self._collections[project_id] = col
            return col

    def _reset_project_index(self, project_id: str) -> None:
        col = self._collections.pop(project_id, None)
        path = self._project_dir(project_id)
        try:
            if col is not None:
                col.destroy()
        except Exception as exc:
            logger.warning("Zvec destroy failed project=%s: %s", project_id, exc)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        # 勿 mkdir：Zvec create_and_open 要求目标路径不存在

    def _collection_doc_count(self, project_id: str) -> int:
        col = self._collections.get(project_id)
        if col is not None:
            return int(col.stats.doc_count)
        path = self._collection_path(project_id)
        if not _is_zvec_collection(path):
            return 0
        try:
            import zvec
            col = zvec.open(path)
            return int(col.stats.doc_count)
        except Exception:
            return 0

    def build_index(
        self,
        project_id: str,
        db: Optional[Session] = None,
        *,
        rebuild: bool = False,
    ) -> int:
        if rebuild:
            self._reset_project_index(project_id)

        session = db or SessionLocal()
        own_session = db is None

        try:
            rows = (
                session.query(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .filter(Chunk.project_id == project_id)
                .filter(Document.status == DocumentStatus.PROCESSED)
                .all()
            )

            if not rows:
                logger.warning(f"Project {project_id} has no chunks to index")
                return 0

            if rebuild:
                new_rows = rows
            else:
                new_rows = [(c, d) for c, d in rows if c.status != ChunkStatus.READY]

            if not new_rows:
                logger.info(f"Project {project_id}: all {len(rows)} chunks already indexed")
                return 0

            logger.info(
                f"Project {project_id}: indexing {len(new_rows)} chunks"
                + (" (full rebuild)" if rebuild else " (incremental)")
            )

            texts = [c.content for c, _ in new_rows]
            embeddings = _l2_normalize(self.embedding.embed(texts).astype(np.float32))

            col = self._open_collection(project_id, create=True)
            if col is None:
                raise RuntimeError(f"无法打开/创建 Zvec collection: {project_id}")

            docs = []
            for i, (chunk, doc) in enumerate(new_rows):
                docs.append(
                    _chunk_to_doc(chunk, doc, embeddings[i].tolist())
                )

            col.upsert(docs)

            for chunk, _ in new_rows:
                chunk.status = ChunkStatus.READY
                chunk.embedding_model = settings.EMBEDDING_MODEL
                chunk.dimension = self.embedding.dimension

            session.commit()
            logger.info(f"Project {project_id}: indexed {len(new_rows)} chunks in Zvec")
            return len(new_rows)

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to build index for {project_id}: {e}", exc_info=True)
            raise
        finally:
            if own_session:
                session.close()

    def search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        db: Optional[Session] = None,
    ) -> List[SearchResult]:
        if _is_legacy_faiss_index(self._project_dir(project_id)) and not _is_zvec_collection(
            self._project_dir(project_id)
        ):
            raise ValueError(
                f"项目 {project_id} 使用旧版 FAISS 索引，请在文献库点击「同步向量索引」重建"
            )

        col = self._open_collection(project_id, create=False)
        if col is None or col.stats.doc_count == 0:
            raise ValueError(f"项目 {project_id} 尚未构建向量索引，请先构建索引")

        from zvec import Query

        q_emb = _l2_normalize(self.embedding.embed([query]).astype(np.float32))
        k = min(top_k, int(col.stats.doc_count))
        hits = col.query(
            queries=Query(VECTOR_FIELD, vector=q_emb[0].tolist()),
            topk=k,
            output_fields=[
                "document_id", "content", "page_number", "source_title",
                "authors", "year", "source_type", "doi", "external_id",
                "source_url", "fallback",
            ],
        )

        results = [_doc_to_search_result(h) for h in hits]
        logger.info(f"Search {project_id}: {len(results)} results for '{query[:50]}...'")
        return results

    def delete_project_index(self, project_id: str) -> bool:
        try:
            self._reset_project_index(project_id)
            logger.info(f"Deleted Zvec index: {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index {project_id}: {e}", exc_info=True)
            return False

    def get_project_stats(self, project_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        return read_project_index_stats(project_id, db=db)

    def has_index(self, project_id: str) -> bool:
        return self._collection_doc_count(project_id) > 0


_vector_store: Optional[VectorStore] = None
_vector_store_lock = threading.Lock()


def read_project_index_stats(project_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """轻量读取项目索引统计（不加载 embedding 模型）。"""
    from pathlib import Path

    base = Path(settings.VECTOR_INDEXES_PATH) / project_id
    legacy = _is_legacy_faiss_index(base)
    zvec_exists = _is_zvec_collection(base)

    indexed_count = 0
    if zvec_exists:
        try:
            indexed_count = get_vector_store()._collection_doc_count(project_id)
        except Exception as exc:
            logger.warning("读取 Zvec stats 失败 project=%s: %s", project_id, exc)

    stats: Dict[str, Any] = {
        "project_id": project_id,
        "exists": indexed_count > 0,
        "chunk_count": indexed_count,
        "dimension": None,
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_backend": settings.VECTOR_BACKEND,
        "index_file": str(base) if zvec_exists else None,
        "mapping_file": None,
        "legacy_faiss": legacy and not zvec_exists,
    }

    if db is None:
        return stats

    db_chunk_count = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.project_id == project_id)
        .filter(Document.status == DocumentStatus.PROCESSED)
        .count()
    )
    stats["db_chunk_count"] = db_chunk_count
    stats["in_sync"] = indexed_count == db_chunk_count
    return stats


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        with _vector_store_lock:
            if _vector_store is None:
                _vector_store = VectorStore()
    return _vector_store


def delete_project_index_files(project_id: str) -> bool:
    global _vector_store
    try:
        if _vector_store is not None:
            return _vector_store.delete_project_index(project_id)

        from pathlib import Path
        base = Path(settings.VECTOR_INDEXES_PATH) / project_id
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
            logger.info("Deleted vector index files: %s", project_id)
            return True
        return False
    except Exception as e:
        logger.error("Failed to delete index files %s: %s", project_id, e, exc_info=True)
        return False


def build_vector_index(project_id: str, db: Optional[Session] = None, *, rebuild: bool = False) -> int:
    return get_vector_store().build_index(project_id, db, rebuild=rebuild)


def sync_project_index(project_id: str, db: Optional[Session] = None) -> int:
    return get_vector_store().build_index(project_id, db, rebuild=True)


def schedule_project_index_sync(
    project_id: str,
    *,
    document_id: Optional[str] = None,
) -> None:
    from app.models.project import Document, ImportStatus

    def _worker() -> None:
        from app.core.database import SessionLocal

        session = SessionLocal()
        try:
            count = sync_project_index(project_id, db=session)
            if document_id:
                doc = (
                    session.query(Document)
                    .filter(Document.id == document_id, Document.project_id == project_id)
                    .first()
                )
                if doc and doc.import_status != ImportStatus.FAILED:
                    doc.import_status = ImportStatus.INDEXED
                    session.commit()
            logger.info("后台索引同步完成 project=%s chunks=%s", project_id, count)
        except Exception as exc:
            logger.warning("后台索引同步失败 project=%s: %s", project_id, exc)
            if document_id:
                try:
                    doc = (
                        session.query(Document)
                        .filter(Document.id == document_id, Document.project_id == project_id)
                        .first()
                    )
                    if doc:
                        doc.error_message = (doc.error_message or "") + f"; 后台索引失败: {exc}"
                        session.commit()
                except Exception:
                    session.rollback()
        finally:
            session.close()

    threading.Thread(
        target=_worker,
        name=f"index-sync-{project_id[:8]}",
        daemon=True,
    ).start()


def search_vector_store(
    project_id: str,
    query: str,
    top_k: int = 5,
    db: Optional[Session] = None,
) -> List[SearchResult]:
    return get_vector_store().search(project_id, query, top_k, db)
