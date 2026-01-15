import json
from pathlib import Path
from datetime import datetime

class PerformanceBaseline:
    """
    Establishes and tracks performance baselines for tuning decisions.
    """
    def __init__(self, baseline_file: Path):
        self.baseline_file = baseline_file
        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)

    def establish_baseline(
        self, 
        extraction_ms: float, 
        vector_ms: float, 
        graph_ms: float, 
        indexing_ms: float
    ):
        baseline = {
            "timestamp": datetime.now().isoformat(),
            "extraction_latency_ms": extraction_ms,
            "vector_search_latency_ms": vector_ms,
            "graph_traversal_latency_ms": graph_ms,
            "memory_indexing_latency_ms": indexing_ms
        }
        with open(self.baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)

    def get_baseline(self) -> dict:
        if self.baseline_file.exists():
            with open(self.baseline_file) as f:
                return json.load(f)
        return {}