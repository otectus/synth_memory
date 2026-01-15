import asyncio
import uuid
import numpy as np
from datetime import datetime
from typing import List, Dict, Any
from .utils.cpu_executor import CPUExecutor
from .pii_pipeline import PIIPipeline

try:
    from gliner import GLiNER
except ImportError: GLiNER = None

class MemoryEventBroker:
    def __init__(self, plugin, vs, gs, cfg):
        self.plugin = plugin
        self.vs = vs
        self.gs = gs
        self.cfg = cfg
        self.executor = CPUExecutor(max_workers=cfg.performance.cpu_executor_workers)
        self.pii = PIIPipeline(mode=cfg.security.pii_redaction_mode)
        self.gliner = None
        self.labels = ["PROJECT", "PERSON", "CONCEPT", "API", "ALGORITHM", "PARAMETER"]

    def _load_gliner(self):
        if GLiNER and not self.gliner:
            self.gliner = GLiNER.from_pretrained("urchade/gliner_small-v2.1")

    async def on_user_send(self, text: str, mode: str):
        asyncio.create_task(self._indexing_pipeline(text, mode))

    async def _indexing_pipeline(self, text: str, mode: str):
        try:
            # 1. PII Redaction
            clean_text, _ = await self.pii.redact(text)

            # 2. Extract Entities (Offload to CPU Pool)
            entities = await self.executor.run(self._extract_sync, clean_text)

            # 3. Vectorize (Bridge to Py-GPT)
            vec = await self.plugin.get_embeddings(clean_text)

            # 4. Storage ops
            doc_id = str(uuid.uuid4())
            self.vs.add(np.array([vec]), [{"id": doc_id, "text": clean_text, "ts": datetime.now().isoformat()}])
            
            for ent in (entities or []):
                ename = ent['text'].lower()
                self.gs.upsert_entity(ename, ent['text'], ent['label'])
                self.gs.add_relation(doc_id, ename, "MENTIONS", conf=ent.get('score', 1.0))
        except Exception as e: print(f"[SynthMemory Error] {e}")

    def _extract_sync(self, text: str) -> List[Dict]:
        self._load_gliner()
        return self.gliner.predict_entities(text, self.labels, threshold=0.3) if self.gliner else []
