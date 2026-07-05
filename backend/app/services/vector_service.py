"""
Chat 专用向量服务（Zvec 嵌入式 Collection）

与项目级 vector_store 分离，用于会话级/全局临时文档 RAG。
"""
import logging
import os
import shutil
from typing import List, Tuple, Optional, Any

import numpy as np

from app.core.config import get_settings
from app.services.vector_store import SentenceTransformerEmbedding, _l2_normalize

logger = logging.getLogger(__name__)
settings = get_settings()

CHAT_VECTOR_FIELD = "embedding"
CHAT_COLLECTION_NAME = "chat_chunks"


def _is_zvec_collection(path: str) -> bool:
    return os.path.isdir(path) and os.path.exists(os.path.join(path, "manifest.0"))


def _is_legacy_faiss_index(path: str) -> bool:
    return os.path.exists(f"{path}.index") or os.path.exists(f"{path}.pkl")


def _build_chat_schema(dimension: int):
    import zvec
    from zvec import CollectionSchema, VectorSchema, FieldSchema, DataType, FlatIndexParam

    return CollectionSchema(
        name=CHAT_COLLECTION_NAME,
        vectors=VectorSchema(
            CHAT_VECTOR_FIELD,
            DataType.VECTOR_FP32,
            dimension,
            index_param=FlatIndexParam(),
        ),
        fields=[
            FieldSchema("doc_id", DataType.STRING),
            FieldSchema("content", DataType.STRING),
        ],
    )


class VectorService:
    """Chat 临时文档向量库（Zvec Collection，路径由 VECTOR_STORE_PATH 指定）。"""

    def __init__(self):
        self.collection_path = settings.VECTOR_STORE_PATH
        parent = os.path.dirname(self.collection_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self._embedding: Optional[SentenceTransformerEmbedding] = None
        self._collection: Optional[Any] = None

        if _is_legacy_faiss_index(self.collection_path) and not _is_zvec_collection(self.collection_path):
            logger.warning(
                "检测到旧版 FAISS Chat 索引 (%s.index)，请重新导入文档以写入 Zvec",
                self.collection_path,
            )

    @property
    def embedding(self) -> SentenceTransformerEmbedding:
        if self._embedding is None:
            self._embedding = SentenceTransformerEmbedding()
        return self._embedding

    @property
    def dimension(self) -> int:
        return self.embedding.dimension

    def _open_collection(self, *, create: bool = False):
        import zvec

        if self._collection is not None:
            return self._collection

        if _is_zvec_collection(self.collection_path):
            self._collection = zvec.open(self.collection_path)
            return self._collection

        if create:
            schema = _build_chat_schema(self.dimension)
            self._collection = zvec.create_and_open(path=self.collection_path, schema=schema)
            return self._collection

        return None

    async def add_document(self, doc_id: str, content: str) -> None:
        from zvec import Doc

        chunks = self._split_text(content)
        if not chunks:
            return

        embeddings = _l2_normalize(self.embedding.embed(chunks).astype(np.float32))
        col = self._open_collection(create=True)
        if col is None:
            raise RuntimeError("无法创建 Chat Zvec collection")

        docs = [
            Doc(
                id=f"{doc_id}_{i}",
                vectors={CHAT_VECTOR_FIELD: embeddings[i].tolist()},
                fields={"doc_id": doc_id, "content": chunk},
            )
            for i, chunk in enumerate(chunks)
        ]
        col.upsert(docs)

    async def search(self, query: str, top_k: int = 5) -> Tuple[str, List[str]]:
        col = self._open_collection(create=False)
        if col is None or col.stats.doc_count == 0:
            return "", []

        from zvec import Query

        q_emb = _l2_normalize(self.embedding.embed([query]).astype(np.float32))
        k = min(top_k, int(col.stats.doc_count))
        hits = col.query(
            queries=Query(CHAT_VECTOR_FIELD, vector=q_emb[0].tolist()),
            topk=k,
            output_fields=["doc_id", "content"],
        )

        results = []
        references = []
        for hit in hits:
            fields = hit.fields or {}
            content = fields.get("content")
            doc_id = fields.get("doc_id")
            if content:
                results.append(content)
            if doc_id:
                references.append(doc_id)

        return "\n\n".join(results), list(set(references))

    def clear(self) -> None:
        """清空 Chat 向量库。"""
        if self._collection is not None:
            try:
                self._collection.destroy()
            except Exception as exc:
                logger.warning("销毁 Chat Zvec collection 失败: %s", exc)
            self._collection = None

        if os.path.isdir(self.collection_path):
            shutil.rmtree(self.collection_path, ignore_errors=True)

    def _split_text(self, text: str) -> List[str]:
        chunk_size = settings.CHUNK_SIZE
        chunk_overlap = settings.CHUNK_OVERLAP

        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0

        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1

            if current_length >= chunk_size:
                chunks.append(" ".join(current_chunk))
                if chunk_overlap > 0 and current_chunk:
                    overlap_words = (
                        current_chunk[-chunk_overlap:]
                        if len(current_chunk) > chunk_overlap
                        else current_chunk
                    )
                    current_chunk = overlap_words.copy()
                    current_length = sum(len(w) + 1 for w in current_chunk)
                else:
                    current_chunk = []
                    current_length = 0

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks
