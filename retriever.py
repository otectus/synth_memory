import asyncio
import numpy as np
from typing import List, Dict, Any
from collections import defaultdict

class HybridMemoryRetriever:
    def __init__(self, vector_store, graph_store, config):
        self.vs = vector_store
        self.gs = graph_store
        self.cfg = config
        self.RRF_K = 60

    async def retrieve(self, query: str, query_vec: np.ndarray, mode: str = "default") -> List[Dict[str, Any]]:
        v_k = self.cfg.retrieval.vector_k_per_mode.get(mode, self.cfg.retrieval.vector_k)
        g_depth = self.cfg.retrieval.graph_depth_per_mode.get(mode, self.cfg.retrieval.graph_depth_traversal)
        
        # Parallel Retreival Tasks
        tasks = [
            asyncio.to_thread(self.vs.search, query_vec, k=v_k * 2),
            asyncio.to_thread(self.gs.traverse_bounded, self._extract_keyword(query), depth=g_depth)
        ]
        v_hits, g_hits = await asyncio.gather(*tasks)
        
        return self._apply_rrf(v_hits or [], g_hits or [], limit=v_k)

    def _apply_rrf(self, v_list: list, g_list: list, limit: int) -> List[Dict]:
        scores = defaultdict(float)
        meta = {}
        
        for rank, item in enumerate(v_list):
            uid = item['metadata']['id']
            scores[uid] += 1.0 / (self.RRF_K + rank + 1)
            meta[uid] = item['metadata']
            meta[uid]['source'] = 'vector'

        for rank, item in enumerate(g_list):
            uid = item.get('neighbor.id') or item.get('id')
            if not uid: continue
            scores[uid] += 1.0 / (self.RRF_K + rank + 1)
            if uid not in meta:
                meta[uid] = {"id": uid, "text": item.get('neighbor.name'), "source": 'graph'}

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"score": s, "metadata": meta[i]} for i, s in sorted_ids[:limit]]

    def _extract_keyword(self, text: str) -> str:
        words = [w.strip("?!.,") for w in text.split() if w[0].isupper()]
        return words[0].lower() if words else "root"