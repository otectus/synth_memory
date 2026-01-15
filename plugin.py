import asyncio
import os
import numpy as np
from pathlib import Path
import atexit
import json
import re
import sys
import threading
import queue
import time
import webbrowser
from collections import OrderedDict
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, List, Tuple, Dict, Any
from pygpt_net.plugin.base.plugin import BasePlugin
from pygpt_net.core.events import Event
from .prompts import DEFAULT_PROMPTS
from pygpt_net.item.ctx import CtxItem
from .config.loader import ConfigurationLoader
from .store.vector_store import FAISSVectorStore
from .store.graph_store import KuzuGraphStore

class SynthMemoryPlugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = "synth_memory"
        self.name = "SynthMemory (Nexus)"
        self.description = "Advanced Bi-temporal Hybrid Memory Suite optimized for Arch Linux."
        
        self.data_dir = Path.home() / ".synthmemory"
        self.loader = ConfigurationLoader(str(self.data_dir))
        self.cfg = self.loader.load()
        
        self.vs = None
        self.gs = None
        self.retriever = None
        self.broker = None

    def setup(self):
        # Deferred initialization on plugin load
        stores = self.data_dir / "stores"
        stores.mkdir(parents=True, exist_ok=True)
        
        # Components init
        self.vs = FAISSVectorStore(stores / "vector", dimension=1536)
        os.environ['KUZU_BUFFER_POOL_SIZE'] = str(int(self.cfg.performance.graph_buffer_pool_gb) * 1024 * 1024 * 1024)
        self.gs = KuzuGraphStore(stores / "graph")
        
        from .retrieval.retriever import HybridMemoryRetriever
        from .broker.event_broker import MemoryEventBroker
        self.retriever = HybridMemoryRetriever(self.vs, self.gs, self.cfg)
        self.broker = MemoryEventBroker(self, self.vs, self.gs, self.cfg)

    def handle(self, event, *args, **kwargs):
        if event.name == 'ctx.begin':
            self.on_ctx_begin(event.data['ctx'])
        elif event.name == 'post.send':
            ctx = event.data['ctx']
            # Non-blocking async dispatch
            asyncio.run_coroutine_threadsafe(
                self.broker.on_user_msg(ctx.input, ctx.mode), 
                self.window.threadpool
            )

    def on_ctx_begin(self, ctx):
        """Retrieve and inject memories into focus context window."""
        if not self.retriever or not ctx.input:
            return
            
        try:
            # In production: retrieve embeddings from core gpt provider
            query_vec = np.array(self.window.core.gpt.get_embeddings(ctx.input))
            memories = asyncio.run(self.retriever.retrieve(ctx.input, query_vec, ctx.mode))
            
            if memories:
                # Inject into system prompt according to injection ratio
                memo_strings = [m['metadata']['text'] for m in memories[:3]]
                injection = "\n\n[RECALLED SEMANTIC MEMORY]:\n" + "\n".join(memo_strings)
                ctx.system_prompt += injection
        except Exception as e:
            print(f"[SynthMemory Error] Injection failed: {e}")

    async def get_embeddings(self, text: str):
        # Bridge to Py-GPT app core
        return self.window.core.gpt.get_embeddings(text)
Plugin = SynthMemoryPlugin
