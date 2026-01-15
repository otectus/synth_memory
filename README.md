# SynthMemory

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python: 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Platform: Nexus](https://img.shields.io/badge/platform-Nexus-blueviolet.svg)
![Status: Production Ready](https://img.shields.io/badge/status-production--ready-green.svg)
![Author: Otectus](https://img.shields.io/badge/author-Otectus-lightgrey.svg)

**SynthMemory** is a hybrid long-term memory plugin for
[pygpt-net](https://github.com/synaptrix/pygpt-net) that enables AI assistants
to maintain persistent, structured memory across conversations.

It combines **vector similarity**, **graph-based reasoning**, and
**entity-aware indexing** to recall relevant context, preserve relationships,
and adapt memory over time without blocking the host UI.

---

## Overview

SynthMemory injects a dedicated memory layer between the user and the model.
As conversations progress, it extracts entities and relationships, stores them
persistently, and retrieves the most relevant memories when similar topics
reappear.

The system is designed to be:
- **Privacy-conscious** by default
- **Robust under partial failure**
- **Performant across a wide range of hardware**
- **Safe to run continuously in production**

---

## Key Features

- **Hybrid Retrieval**
  Combines FAISS-based vector similarity with Kùzu graph traversal using
  Reciprocal Rank Fusion (RRF) for resilient recall.

- **Entity-Aware Indexing**
  Zero-shot named entity recognition via GLiNER (or configurable extractors)
  enables relationship-aware memory instead of flat embeddings.

- **Structured Memory**
  Memories are enriched with entities, relations, communities, and temporal
  context rather than stored as isolated text chunks.

- **Asynchronous Pipeline**
  Indexing and retrieval run off the main thread to keep the host UI responsive.

- **Graceful Degradation**
  Automatically falls back to vector-only or memory-disabled modes if optional
  dependencies are unavailable.

- **Privacy-First Design**
  Configurable PII redaction, local-only storage, access control boundaries, and
  support for cryptographic shredding.

---

## Architecture

```

┌─────────────────────────────────────────────────────┐
│                   pygpt-net Host                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Context   │  │    Event    │  │   Embedding │ │
│  │   (Ctx)     │  │   Bus       │  │   Provider  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
└─────────┼─────────────────┼─────────────────┼────────┘
│                 │                 │
▼                 ▼                 ▼
┌─────────────────────────────────────────────────────┐
│                 SynthMemory Plugin                   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │           Memory Indexer (Broker)               │  │
│  │  • Entity extraction (GLiNER / spaCy / LLM)     │  │
│  │  • PII redaction & access control               │  │
│  │  • Vector + graph dual-write                    │  │
│  └───────────────┬───────────────────────────────┘  │
│                  │                                   │
│  ┌───────────────▼───────────────────────────────┐  │
│  │           Hybrid Memory Retriever               │  │
│  │  • FAISS vector store (similarity search)       │  │
│  │  • Kùzu graph store (relation traversal)        │  │
│  │  • RRF fusion & context window management       │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘

````

---

## Installation

### Prerequisites

- [pygpt-net](https://github.com/synaptrix/pygpt-net) installed and running
- Python 3.9 or newer

### Steps

1. Clone the repository:
```bash
cd ~/.pygpt-net/plugins
git clone https://github.com/otectus/synth_memory.git
````

2. Install required dependencies:

```bash
pip install faiss-cpu kuzu gliner-spacy
```

3. Restart `pygpt-net` and enable the **“SynthMemory (Nexus)”** plugin in
   settings.

---

## Documentation

Detailed design notes, configuration options, privacy model, and operational
behavior are available in
[`DOCUMENTATION.md`](DOCUMENTATION.md).

---

## License

MIT License
Copyright (c) 2024–2026 Cipher (Otectus)
