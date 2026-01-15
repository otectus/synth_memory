import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

class CPUExecutor:
    """
    Dedicated thread pool for offloading CPU-heavy tasks (GLiNER extraction, FAISS search).
    Ensures the Py-GPT main thread (GUI) remains responsive.
    """
    def __init__(self, max_workers: int = 4):
        self.pool = ThreadPoolExecutor(max_workers=max_workers)

    async def run(self, func: Callable, *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.pool, lambda: func(*args, **kwargs))