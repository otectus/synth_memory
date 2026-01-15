import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any

class FAISSVectorStore:
    def __init__(self, index_dir: str, dimension: int = 1536, index_type: str = "Flat"):
        self.index_dir = Path(index_dir)
        self.idx_file = self.index_dir / "vector.index"
        self.meta_file = self.index_dir / "vector.meta"
        self.dimension = dimension
        self.index_type = index_type
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata = []
        self.index = None
        self._load()

    def _initialize_index(self):
        # For Arch Linux, IndexFlatL2 is extremely optimized via AVX-512 paths
        # We wrap in IndexIDMap to allow stable metadata association
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(self.dimension))

    def add(self, vectors: np.ndarray, metas: List[Dict]):
        # vectors: shape (N, Dim)
        num_vecs = vectors.shape[0]
        # Assign IDs based on current metadata length
        start_id = len(self.metadata)
        ids = np.arange(start_id, start_id + num_vecs).astype('int64')
        
        self.index.add_with_ids(vectors.astype('float32'), ids)
        self.metadata.extend(metas)
        self._save()

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
        
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