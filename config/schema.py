from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Literal, Any
from enum import Enum
import os

class ExtractionProvider(str, Enum):
    AUTO = "Auto"
    GLINER = "GLiNER"
    SPACY = "spaCy"
    LLM = "LLM"
    HEURISTIC = "Heuristic"

class IndexingStrategy(str, Enum):
    REALTIME = "RealTime"
    DEBOUNCED = "Debounced"
    ON_CONTEXT_SWITCH = "OnContextSwitch"
    MANUAL = "Manual"

class VectorIndexType(str, Enum):
    HNSW = "HNSW"
    IVF_PQ = "IVF_PQ"
    FLAT = "Flat"

class PIIRedactionMode(str, Enum):
    STRICT = "Strict"
    PARTIAL = "Partial"
    AUDIT = "Audit"
    OFF = "Off"

class PerformanceConfig(BaseModel):
    extraction_provider: ExtractionProvider = ExtractionProvider.GLINER
    indexing_strategy: IndexingStrategy = IndexingStrategy.DEBOUNCED
    debounce_ms: int = Field(default=1000, ge=100)
    gpu_layer_offload: int = Field(default=0, ge=0, le=100)
    vector_index_type: VectorIndexType = VectorIndexType.FLAT
    graph_buffer_pool_gb: int = Field(default=4, ge=1, alias='buffer_pool_gb')
    cpu_executor_workers: int = Field(default=4, ge=1, le=32)
    embedding_batch_size: int = Field(default=64, ge=1)
    ner_extraction_timeout_ms: int = Field(default=2000, ge=100, alias='ner_timeout_ms')

class LifecycleConfig(BaseModel):
    retention_policy: str = "Forever"
    compression_policy: Literal["Summarize", "Archive", "Delete"] = "Summarize"
    reinforcement_threshold: int = Field(default=3, ge=1)

class SecurityConfig(BaseModel):
    pii_redaction_mode: PIIRedactionMode = PIIRedactionMode.STRICT
    cross_mode_inference: bool = False
    forget_policy: Literal["HardDelete", "SoftDelete", "CryptoShred"] = "CryptoShred"
    audit_log_enabled: bool = True

class RetrievalConfig(BaseModel):
    vector_k: int = Field(default=5, ge=1)
    vector_k_per_mode: Dict[str, int] = {}
    graph_depth_traversal: int = Field(default=2, ge=1, le=5)
    context_window_injection_ratio: float = Field(default=20.0, ge=0.0, le=50.0)
    rrf_k_parameter: int = Field(default=60, ge=20)

class TruthConfig(BaseModel):
    contradiction_handling: str = "HighestConfidenceWins"
    confidence_decay_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    fact_promotion_threshold: int = Field(default=3, ge=1)
    enable_temporal_invalidation: bool = True

class TaxonomyConfig(BaseModel):
    auto_tagging: bool = True
    user_defined_tags: Dict[str, Any] = {}
    tag_weighting: Dict[str, float] = {}

class VisualizationConfig(BaseModel):
    graph_visualization_engine: str = "2DForce"
    visualization_theme: str = "Dark"
    highlight_memory_hits: bool = True
    debug_overlay: bool = False

class PortabilityConfig(BaseModel):
    export_format: str = "JSON"
    encryption_key_rotation: bool = True
    backup_strategy: str = "LocalDaily"

class SynthMemoryConfig(BaseModel):
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    truth: TruthConfig = Field(default_factory=TruthConfig)
    taxonomy: TaxonomyConfig = Field(default_factory=TaxonomyConfig)
    visualization: VisualizationConfig = Field(default_factory=VisualizationConfig)
    portability: PortabilityConfig = Field(default_factory=PortabilityConfig)

    class Config:
        use_enum_values = True
        allow_population_by_field_name = True
