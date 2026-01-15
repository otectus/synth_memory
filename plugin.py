import asyncio
import numpy as np
from pathlib import Path
import logging
from pygpt_net.plugin.base.plugin import BasePlugin
from pygpt_net.core.events import Event
from pygpt_net.item.ctx import CtxItem
from .config.loader import ConfigurationLoader
from .store.vector_store import FAISSVectorStore, NoOpVectorStore
from .store.graph_store import KuzuGraphStore, NoOpGraphStore

class SynthMemoryPlugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = "synth_memory"
        self.name = "SynthMemory (Nexus)"
        self.description = "Advanced Bi-temporal Hybrid Memory Suite optimized for Nexus."
        
        self.data_dir = Path.home() / ".synthmemory"
        self.loader = ConfigurationLoader(str(self.data_dir))
        self.cfg = self.loader.load()
        self.vs, self.gs, self.retriever, self.broker = None, None, None, None
        self.log = logging.getLogger("SynthMemory")

    def setup(self):
        stores = self.data_dir / "stores"
        stores.mkdir(parents=True, exist_ok=True)
        try:
            emb = self.window.core.gpt.get_embeddings("test")
            embedding_dim = len(emb)
        except Exception:
            embedding_dim = 1536
        
        try: self.vs = FAISSVectorStore(stores / "vector", dimension=embedding_dim)
        except ImportError: self.vs = NoOpVectorStore(stores / "vector", dimension=embedding_dim)
        
        try: self.gs = KuzuGraphStore(stores / "graph", buffer_pool_gb=self.cfg.performance.graph_buffer_pool_gb)
        except ImportError: self.gs = NoOpGraphStore(stores / "graph", buffer_pool_gb=self.cfg.performance.graph_buffer_gb)
        
        from .retrieval.retriever import HybridMemoryRetriever
        from .broker.event_broker import MemoryIndexer
        self.broker = MemoryIndexer(self.get_embeddings, self.vs, self.gs, self.cfg)
        self.retriever = HybridMemoryRetriever(self.vs, self.gs, self.cfg, extractor_fn=self.broker._extract_sync)

    def handle(self, event, *args, **kwargs):
        if event.name == 'ctx.begin': self.on_ctx_begin(event.data['ctx'])
        elif event.name == 'post.send':
            ctx = event.data['ctx']
            asyncio.run_coroutine_threadsafe(self.broker.on_user_msg(ctx.input, ctx.mode), self.window.threadpool)

    def on_ctx_begin(self, ctx):
        if not self.retriever or not ctx.input: return
        try:
            query_vec = np.array(self.window.core.gpt.get_embeddings(ctx.input))
            memories = asyncio.run(self.retriever.retrieve(ctx.input, query_vec, ctx.mode))
            if memories:
                # Use all returned memories; retriever limits output based on config
                memo_strings = [m['metadata']['text'] for m in memories]
                injection = "\n\n[RECALLED SEMANTIC MEMORY]:\n" + "\n".join(memo_strings)
                if hasattr(ctx, 'add_memory'): 
                    ctx.add_memory(injection)
                else: 
                    self.log.warning("[SynthMemory] Host context does not support memory injection; discarding recall.")
        except Exception as e: self.log.error(f"[SynthMemory: Injection] {e}")

    async def get_embeddings(self, text: str): return self.window.core.gpt.get_embeddings(text)

    def shutdown(self):
        # Close graph store first to ensure relation integrity before vector cleanup
        if self.gs: self.gs.close()
        if self.vs: self.vs.close()
Plugin = SynthMemoryPlugin
