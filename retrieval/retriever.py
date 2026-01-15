import asyncio
import numpy as np
from typing import List, Dict, Any
from collections import defaultdict

class HybridMemoryRetriever:
    """
    Implements Friction Point #2 fix: Reciprocal Rank Fusion (RRF).
    Normalizes heterogeneous scores from vector and graph stores.
    """
    def __init__(self, vector_store, graph_store, config):
        self.vs = vector_store
        self.gs = graph_store
        self.cfg = config

    async def retrieve(self, query: str, query_vec: np.ndarray, mode: str = "default") -> List[Dict[str, Any]]:
        v_k = self.cfg.retrieval.vector_k
        g_depth = self.cfg.retrieval.graph_depth_traversal
        
        # Perform parallel search via thread offloading
        # (FAISS and Kuzu C++ drivers release the GIL)
        vector_task = asyncio.to_thread(self.vs.search, query_vec, k=v_k * 2)
        
        # Heuristic entry point extraction for graph
        g_entry = ""
        words = [w.strip("?!.,") for w in query.split() if len(w) > 2 and w[0].isupper()]
        if words:
            g_entry = words[0].lower()
            
        graph_task = asyncio.to_thread(self.gs.traverse_bounded, g_entry, depth=g_depth) if g_entry else asyncio.sleep(0, [])

        v_hits, g_hits = await asyncio.gather(vector_task, graph_task)
        
        return self._rrf_merge(v_hits or [], g_hits or [], v_k)

    def _rrf_merge(self, v_hits: List[Dict], g_hits: List[Dict], limit: int) -> List[Dict[str, Any]]:
        k = self.cfg.retrieval.rrf_k_parameter
        scores = defaultdict(float)
        meta_cache = {}

        # Rank based fusion: score = 1 / (k + rank)
        for rank, hit in enumerate(v_hits):
            uid = hit['metadata']['id']
            scores[uid] += 1.0 / (k + rank + 1)
            meta_cache[uid] = hit['metadata']
            meta_cache[uid]['source'] = 'vector'

        for rank, hit in enumerate(g_hits):
            uid = hit.get('id') or hit.get('b.id')
            if not uid: continue
            scores[uid] += 1.0 / (k + rank + 1)
            if uid not in meta_cache:
                meta_cache[uid] = {
                    "id": uid, 
                    "text": hit.get('name', uid), 
                    "type": hit.get('type', 'Unknown'),
                    "source": "graph"
                }

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"id": i, "rrf_score": s, "metadata": meta_cache[i]} for i, s in sorted_ids[:limit]]