import asyncio
import numpy as np
from typing import List, Dict, Any, Callable
from collections import defaultdict

class HybridMemoryRetriever:
    """
    Reciprocal Rank Fusion (RRF) retriever.
    """
    def __init__(self, vector_store, graph_store, config, extractor_fn: Callable = None):
        self.vs = vector_store
        self.gs = graph_store
        self.cfg = config
        self.extractor_fn = extractor_fn
        self.log = logging.getLogger("SynthMemory")

    async def retrieve(self, query: str, query_vec: np.ndarray, mode: str = "default") -> List[Dict[str, Any]]:
        v_k = self.cfg.retrieval.vector_k
        g_depth = self.cfg.retrieval.graph_depth_traversal
        vector_task = asyncio.to_thread(self.vs.search, query_vec, k=v_k * 2)
        
        g_entry = ""
        if self.extractor_fn:
            try:
                # Get timeout from config, defaulting to 2.0s if missing
                timeout_sec = getattr(self.cfg.performance, 'ner_extraction_timeout_ms', 2000) / 1000.0
                
                # Watchdog: Offload NER to thread, but enforce hard deadline
                entities = await asyncio.wait_for(
                    asyncio.to_thread(self.extractor_fn, query), 
                    timeout=timeout_sec
                )
                if isinstance(entities, list) and len(entities) > 0:
                    first = entities[0]
                    if isinstance(first, dict) and 'text' in first:
                        g_entry = first['text'].lower()
            except asyncio.TimeoutError:
                # Fallback: proceed with vector-only search if NER is too slow
                self.log.warning(f"[SynthMemory: Retriever] NER extraction timed out (>{timeout_sec:.1f}s). Proceeding with Vector-Only recall.")
                pass
            except Exception as e:
                # Explicit logging for non-timeout errors to aid diagnostics
                self.log.debug(f"[SynthMemory: Retriever] Extraction error: {e}")
                pass
        
        graph_task = asyncio.to_thread(self.gs.traverse_bounded, g_entry, depth=g_depth) if g_entry else asyncio.sleep(0, [])
        v_hits, g_hits = await asyncio.gather(vector_task, graph_task)
        return self._rrf_merge(v_hits or [], g_hits or [])

    def _rrf_merge(self, v_hits: List[Dict], g_hits: List[Dict]) -> List[Dict[str, Any]]:
        k = self.cfg.retrieval.rrf_k_parameter
        scores = defaultdict(float)
        meta_cache = {}

        for rank, hit in enumerate(v_hits):
            uid = hit['metadata']['id']
            scores[uid] += 1.0 / (k + rank + 1)
            meta_cache[uid] = hit['metadata']
            meta_cache[uid]['source'] = 'vector'

        for rank, hit in enumerate(g_hits):
            uid = hit.get('id')
            if not uid: continue
            scores[uid] += 1.0 / (k + rank + 1)
            if uid not in meta_cache:
                meta_cache[uid] = {
                    "id": uid, 
                    "text": hit.get('name', uid), 
                    "type": hit.get('type', 'Unknown'),
                    "source": "graph"
                }

        # Fusion Window: Use actual hit counts, capped to context ceiling
        baseline_limit = int(self.cfg.retrieval.vector_k) if self.cfg else 5
        # Ensure we don't bloat the context if graph returns many nodes, but allow graph to expand beyond vector_k slightly
        limit = min(baseline_limit + len(g_hits), baseline_limit * 2)
        
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"id": i, "rrf_score": s, "metadata": meta_cache[i]} for i, s in sorted_ids[:limit]]
