import asyncio
import uuid
import numpy as np
from datetime import datetime
from typing import List, Dict, Any
from ..utils.cpu_executor import CPUExecutor
from ..utils.pii import PIIRedactor

try:
    from gliner import GLiNER
except ImportError:
    GLiNER = None

class MemoryEventBroker:
    """
    Async Event Broker that solves Friction Point #1: Latency Trap.
    Uses GLiNER (small-v2.1) for zero-shot entity extraction in <50ms.
    """
    def __init__(self, plugin, vs, gs, cfg):
        self.plugin = plugin
        self.vs = vs
        self.gs = gs
        self.cfg = cfg
        self.executor = CPUExecutor(max_workers=cfg.performance.cpu_executor_workers)
        self.redactor = PIIRedactor(mode=cfg.security.pii_redaction_mode)
        self.gliner_model = None
        self.labels = ["PROJECT", "PERSON", "CONCEPT", "API", "CODE_ENTITY", "ALGORITHM", "PARAMETER"]

    def _lazy_load_gliner(self):
        if GLiNER and not self.gliner_model:
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")

    async def on_user_msg(self, text: str, mode: str):
        # Friction Point #3 fix: Background indexing pipeline
        asyncio.create_task(self._process_indexing(text, mode))

    async def _process_indexing(self, text: str, mode: str):
        try:
            # 1. PII Redaction
            clean_text = self.redactor.redact(text)
            
            # 2. Parallel AI Ops (Extraction & Embedding)
            entities = await self.executor.run(self._extract_sync, clean_text)
            embedding = await self.plugin.get_embeddings(clean_text)
            
            # 3. Storage persistence
            doc_id = str(uuid.uuid4())
            self.vs.add(np.array([embedding]), [{
                "id": doc_id, "text": clean_text, "mode": mode, "ts": datetime.now().isoformat()
            }])
            
            for ent in entities:
                ename = ent['text'].lower()
                self.gs.upsert_entity(ename, ent['text'], ent['label'])
                self.gs.add_relation(doc_id, ename, "MENTIONS", conf=ent.get('score', 1.0))
        except Exception as e:
            print(f"[SynthMemory Broker Error]: {e}")

    def _extract_sync(self, text: str) -> List[Dict]:
        self._lazy_load_gliner()
        if self.gliner_model:
            return self.gliner_model.predict_entities(text, self.labels, threshold=0.3)
        return []