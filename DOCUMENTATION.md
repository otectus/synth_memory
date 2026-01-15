# SynthMemory Documentation

SynthMemory is a hybrid memory system for `pygpt-net` that persists long-term knowledge across conversations using:
- Vector similarity search (FAISS)
- A temporal knowledge graph (Kùzu)
- Entity extraction (GLiNER or configurable alternatives)
- Privacy controls (PII redaction + access control)
- Graceful degradation when optional dependencies are missing

This document explains how SynthMemory is intended to work, how to configure it, and how to reason about its behavior in production.

## Table of Contents
- Philosophy & Design Principles
- High-Level Architecture
- Core Concepts
  - Memories
  - Entities and Relations
  - Namespaces and Modes
- Data Flow
  - Ingest (Indexing)
  - Retrieve (Recall)
  - Fusion (RRF)
- Privacy, Access Control, and PII
- Configuration
- Operational Behavior
  - Graceful Degradation
  - Thread Awareness
  - Schema Resilience
- Troubleshooting
- Extension Points
- Roadmap

---

## Philosophy & Design Principles

SynthMemory is built on these principles:

1) **Semantic Continuity**  
Memories persist across sessions and adapt as conversations evolve.

2) **Privacy by Default**  
No data leaves local storage without explicit consent. PII is redacted before indexing.

3) **Graceful Degradation**  
If a subsystem is unavailable, SynthMemory reduces capability rather than failing hard.

4) **Thread Awareness**  
CPU-heavy work must not block the UI thread or the host event loop.

5) **Schema Resilience**  
Databases must survive version shifts, corruption, and partial failures.

(These are the same principles described in the project’s current documentation scaffold.) 

---

## High-Level Architecture

SynthMemory sits between the `pygpt-net` host and the model:

- **Indexer (Broker)**: transforms new conversation content into stored memory artifacts
- **Retriever**: answers “what past memories matter right now?”
- **Dual stores**:
  - Vector store (FAISS) for semantic similarity
  - Graph store (Kùzu) for relationship traversal and temporal structure
- **Fusion**: Reciprocal Rank Fusion (RRF) merges vector and graph results into a final context payload

The README contains the canonical overview diagram and feature list.

---

## Core Concepts

### Memories
A “memory” is a persisted unit of information derived from conversation turns or explicit saves. Conceptually, a memory may include:
- Text payload (the memory content)
- Metadata (timestamp, source thread/session, importance, tags)
- Entities and relations extracted from the text
- A namespace boundary (who is allowed to see it)

### Entities and Relations
Entities are people, places, projects, identifiers, and concepts extracted from text. Relations are edges such as:
- “works_on”
- “belongs_to”
- “depends_on”
- “mentioned_with”
- “occurred_before/after” (temporal ordering)

The graph is how SynthMemory supports multi-hop recall, not just similarity search.

### Namespaces and Modes
SynthMemory is “mode-aware.” In practice, this means memories can be separated and filtered by:
- Workspace, project, tenant, or persona identity
- Privacy boundary (public vs private memory regions)
- Operational mode (full hybrid vs vector-only vs disabled)

Namespacing is the main tool that prevents “memory soup.”

---

## Data Flow

### 1) Ingest (Indexing)
When a new conversation turn arrives, SynthMemory performs the following steps:

1. **Normalize input**
   - Normalize whitespace, strip obvious noise, attach timestamps and source metadata.

2. **PII redaction (optional but recommended)**
   - Redact sensitive fields before any storage writes.

3. **Access control evaluation**
   - Determine allowed namespace(s) and classification for this memory.

4. **Entity extraction**
   - Extract entities and, where supported, relation candidates.

5. **Dual write**
   - Write embedding + vector index entry
   - Write entity/relation nodes and edges into the graph

6. **Async execution**
   - Steps 2–5 should run off the UI thread / main loop.
   - Indexing must never block chat responsiveness.

### 2) Retrieve (Recall)
On each new user query (or at configured times), SynthMemory runs retrieval:

1. **Vector retrieval**
   - Embed the query
   - Pull top-k semantically similar memories

2. **Graph traversal**
   - Identify seed entities from query
   - Traverse relations to find linked memories and contextual neighbors
   - Apply temporal filters if configured

3. **Namespace filtering**
   - Enforce “who can see what” before fusion

### 3) Fusion (RRF)
SynthMemory merges candidates from both stores using Reciprocal Rank Fusion (RRF):
- Vector hits contribute “semantic relevance”
- Graph hits contribute “structural relevance”
- RRF dampens dominance by any single subsystem and increases robustness

The fused result becomes a context payload suitable for injection into the model prompt.

---

## Privacy, Access Control, and PII

### Threat Model (practical)
Memory systems fail in predictable ways:
- They leak private details into the wrong conversation
- They store sensitive data that should never persist
- They silently degrade and start hallucinating “memory content”

SynthMemory treats privacy as an engineering constraint, not a vibes-based suggestion.

### Recommended privacy controls
- Enable PII redaction before indexing
- Use strict namespaces (per project, per tenant, per persona)
- Default-deny cross-namespace retrieval
- Provide explicit “forget” and “shred” operations

### Cryptographic shredding (if enabled)
If your implementation supports it, shredding should:
- Remove the vector entry
- Remove graph links and nodes if they no longer have references
- Remove associated metadata
- Ensure no residual plaintext is left in easy-to-recover caches

---

## Configuration

> Note: This section is written to match SynthMemory’s intended capability surface. Align the exact keys and paths with your current `config/` implementation.

### Minimal config (conceptual)
```yaml
synthmemory:
  enabled: true

  mode: hybrid          # hybrid | vector_only | disabled
  namespace: default    # default namespace boundary

  retrieval:
    top_k_vector: 12
    top_k_graph: 12
    fusion: rrf
    max_context_tokens: 1200

  indexing:
    async: true
    batch_size: 1
    min_chars: 40

  pii:
    enabled: true
    redaction_level: standard   # off | standard | aggressive

  access_control:
    enabled: true
    default_policy: deny_cross_namespace
````

### Practical defaults

* Start with hybrid mode but allow vector-only fallback
* Keep `top_k_*` small until behavior is stable
* Enforce namespace isolation early, loosening later if needed

---

## Operational Behavior

### Graceful Degradation

If optional dependencies are missing or a store fails:

* If graph store fails: continue in vector-only mode
* If vector store fails: continue with graph traversal only (if safe) or disable retrieval
* If both fail: disable memory injection but do not crash the host

Degradation should be logged loudly, but the app should stay alive.

### Thread Awareness

Indexing and heavy retrieval must not block UI responsiveness. If the host uses an event loop, run CPU tasks via:

* background thread
* job queue
* process pool (if embeddings are heavy)

### Schema Resilience

The graph schema and memory schema should be versioned. If a schema changes:

* Migrate forward safely
* Reject unknown versions with a clear error
* Prefer recoverable corruption handling (repair, rebuild, or partial restore)

---

## Troubleshooting

### “It stopped recalling anything”

Check:

* Plugin enabled in `pygpt-net`
* `mode` not set to `disabled`
* Namespaces not overly restrictive
* Index exists and is writable
* Embedding provider configured correctly

### “It recalls the wrong private info”

Check:

* Namespace boundaries
* Access control enforcement happens before fusion and before prompt injection
* PII redaction enabled and running before storage writes

### “UI freezes during chat”

Check:

* Indexing is running async
* Retrieval is capped (`top_k` limits)
* Embedding compute is not blocking the main loop

### “Graph store errors after update”

Check:

* Schema version mismatch
* Migration path
* Corruption recovery path (repair or rebuild)

---

## Extension Points

SynthMemory is designed to be modular. Typical swap points:

* Entity extractor (GLiNER -> spaCy -> LLM-based -> heuristic)
* Vector backend (FAISS -> alternative)
* Graph backend (Kùzu -> alternative)
* Fusion strategy (RRF -> weighted RRF -> policy-aware rerank)
* Privacy pipeline (PII rules, detection models, custom redactors)

If you add new components, keep the same constraints:

* no blocking UI
* namespace safety first
* degrade instead of crash

---

## Roadmap (Suggested)

Near-term:

* Confirm config keys and document the exact schema
* Add a “forget/shred” API and document it
* Add a “show memory payload” debug mode (safe, redacted)

Mid-term:

* Multi-tenant namespaces with explicit policy rules
* Memory scoring: importance, recency, reinforcement
* Community detection on graph (clusters for topic recall)

Long-term:

* Full temporal reasoning utilities (timelines, causality edges)
* Eval harness: recall precision, leakage tests, regression suite
* Policy-driven retrieval (identity, mood, and safety constraints)
