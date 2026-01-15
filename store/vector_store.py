import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any

class FAISSVectorStore: 
    """
    High-performance vector store utilizing FAISS.
    Optimized for Arch Linux by using IndexFlatL2 with AVX-512 paths for smaller namespaces.
    """
    def __init__(self, index_dir: Path, dimension: int = 1536):
        self.index_dir = index_dir
        self.idx_file = index_dir / "vector.index"
        self.meta_file = index_dir / "vector.meta"
        self.dimension = dimension
        self.metadata = []
        self.index = None
        self._load()

    def _initialize_index(self):
        # Wrapping IndexFlatL2 in IndexIDMap for persistent identifier support
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(self.dimension))

    def add(self, vectors: np.ndarray, metas: List[Dict]):
        # vectors shape: (N, Dim)
        start_id = len(self.metadata)
        ids = np.arange(start_id, start_id + vectors.shape[0]).astype('int64')
        
        self.index.add_with_ids(vectors.astype('float32'), ids)
        self.metadata.extend(metas)
        self._save()

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
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
        else:
            self._initialize_index()