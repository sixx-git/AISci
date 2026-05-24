import os
import numpy as np
import faiss
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings

settings = get_settings()


class VectorService:
    def __init__(self):
        self.index_path = settings.FAISS_INDEX_PATH
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.dimension = 384
        
        self.index = None
        self.documents = []
        self._load_index()
    
    def _load_index(self):
        if os.path.exists(f"{self.index_path}.index"):
            self.index = faiss.read_index(f"{self.index_path}.index")
            import pickle
            if os.path.exists(f"{self.index_path}.pkl"):
                with open(f"{self.index_path}.pkl", "rb") as f:
                    self.documents = pickle.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
    
    def _save_index(self):
        faiss.write_index(self.index, f"{self.index_path}.index")
        import pickle
        with open(f"{self.index_path}.pkl", "wb") as f:
            pickle.dump(self.documents, f)
    
    async def add_document(self, doc_id: str, content: str):
        chunks = self._split_text(content)
        embeddings = self.model.encode(chunks)
        
        for i, chunk in enumerate(chunks):
            self.documents.append({
                "id": f"{doc_id}_{i}",
                "doc_id": doc_id,
                "content": chunk,
                "embedding": embeddings[i]
            })
        
        self.index.add(np.array(embeddings).astype('float32'))
        self._save_index()
    
    async def search(self, query: str, top_k: int = 5) -> Tuple[str, List[str]]:
        if len(self.documents) == 0:
            return "", []
        
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        results = []
        references = []
        for i in indices[0]:
            if i < len(self.documents):
                results.append(self.documents[i]["content"])
                references.append(self.documents[i]["doc_id"])
        
        context = "\n\n".join(results)
        return context, list(set(references))
    
    def _split_text(self, text: str, chunk_size: int = 500) -> List[str]:
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1
            
            if current_length >= chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
