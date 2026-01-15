from datetime import datetime
import numpy as np
import pickle
import threading
from pathlib import Path
from typing import List, Dict, Any
import logging
import shutil

try:
    import faiss
except ImportError:
    faiss = None

class NoOpVectorStore:
    """No-op vector store that gracefully degrades when FAISS is unavailable."""
    def __init__(self, index_dir: Path, dimension: int):
        self.index_dir = index_dir
        self.dimension = dimension
        self.index = None
        self.log = logging.getLogger("SynthMemory")
        self._closed = False
        self.lock = threading.Lock()
        self.log.warning("[SynthMemory: VectorStore] FAISS not available. Running in degraded mode (no vector memory).")

    def add(self, vectors: np.ndarray, metas: List[Dict]):
        assert vectors.shape[1] == self.dimension, "Embedding vector shape mismatch"
        pass

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        assert query_vector.shape[0] == self.dimension, "Query vector shape mismatch"
        return []

    def get_dimension(self):
        return self.dimension

    def close(self):
        with self.lock:
            if not self._closed:
                self._closed = True

class FAISSVectorStore: 
    """
    High-performance vector store utilizing FAISS.
    Optimized for Arch Linux by using IndexFlatL2 with AVX-512 paths for smaller namespaces.
    """
    def __init__(self, index_dir: Path, dimension: int):
        self.log = logging.getLogger("SynthMemory")
        self._closed = False
        if faiss is None:
            raise ImportError("FAISS is not available. Please install faiss-cpu.")
        self.index_dir = index_dir
        self.idx_file = index_dir / "vector.index"
        self.meta_file = index_dir / "vector.meta"
        self.dimension = dimension
        self.metadata = []
        self.index = None
        self.lock = threading.Lock()
        self._load()

    def _initialize_index(self):
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(self.dimension))

    def add(self, vectors: np.ndarray, metas: List[Dict]):
        with self.lock:
            assert vectors.shape[1] == self.dimension, "Embedding vector shape mismatch"
            start_id = len(self.metadata)
            ids = np.arange(start_id, start_id + vectors.shape[0]).astype('int64')
            self.index.add_with_ids(vectors.astype('float32'), ids)
            self.metadata.extend(metas)
            self._save()

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        with self.lock:
            assert query_vector.shape[0] == self.dimension, "Query vector shape mismatch"
            if self.index.ntotal == 0: return []
            q = query_vector.astype('float32').reshape(1, -1)
            distances, indices = self.index.search(q, k)
            results = []
            for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx != -1 and idx < len(self.metadata):
                    results.append({
                        "metadata": self.metadata[idx],
                        "score": float(dist),
                        "rank": rank + 1
                    })
            return results

    def _save(self):
        self.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.idx_file))
        with open(self.meta_file, 'wb') as f:
            pickle.dump(self.metadata, f)

    def _load(self):
        if self.idx_file.exists() and self.meta_file.exists():
            self.index = faiss.read_index(str(self.idx_file))
            with open(self.meta_file, 'rb') as f:
                self.metadata = pickle.load(f)
            if self.index.d != self.dimension:
                self.log.error(f"[SynthMemory: VectorStore] Dimension mismatch: Expected {self.dimension}, got {self.index.d}. Renaming corrupted index.")
                backup_file = self.index_dir / f"vector_mismatch_{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                self.idx_file.rename(backup_file)
                self._initialize_index()
        else:
            self._initialize_index()

    def get_dimension(self):
        return self.dimension

    def close(self):
        with self.lock:
            if self._closed: return
            # FAISS indices do not strictly require closing, but we flush state here
            self._closed = True
