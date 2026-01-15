import os
from typing import List, Tuple
from .schema import SynthMemoryConfig

class ConfigurationValidator:
    """
    Safety layer to prevent configuration that stalls the host system.
    """
    @staticmethod
    def validate(config: SynthMemoryConfig) -> Tuple[bool, List[str]]:
        warnings = []
        
        # CPU Check
        cpu_count = os.cpu_count() or 4
        if config.performance.cpu_executor_workers > cpu_count * 2:
            warnings.append(f"Warning: {config.performance.cpu_executor_workers} workers may cause contention on {cpu_count}-core CPU.")

        # Memory Check
        if config.performance.graph_buffer_pool_gb > 32:
            warnings.append("Warning: High graph buffer pool (>32GB) may cause system OOM.")

        # Search Check
        if config.retrieval.vector_k > 50:
            warnings.append("Warning: High vector_k values significantly increase retrieval latency.")
            
        return len(warnings) == 0, warnings