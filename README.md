# SynthMemory

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg) 
![Python: 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Platform: Nexus](https://img.shields.io/badge/platform-Nexus-blueviolet.svg)
![Status: Production Ready](https://img.shields.io/badge/status-production--ready-green.svg)
![Author: Cipher](https://img.shields.io/badge/author-Cipher-lightgrey.svg)

A hybrid memory plugin for [pygpt-net](https://github.com/synaptrix/pygpt-net) that enables AI assistants to maintain persistent, structured memory across conversations. **SynthMemory** combines vector similarity, graph relations, and entity extraction to create a semantic memory system that recalls relevant context, understands relationships, and adapts over time.

## Overview

SynthMemory is a plugin that injects a memory layer between the user and the AI. It learns from conversations, extracts entities and relationships, and recalls relevant memories when similar topics arise. The system is designed to be privacy-conscious, performant, and robust across different hardware environments.

### Key Features

* **Hybrid Retrieval**: Combines FAISS-based vector similarity with Kùzu graph traversal using Reciprocal Rank Fusion (RRF)
* **Entity-Aware Indexing**: Uses GLiNER (or configurable extractors) for zero-shot named entity recognition
* **Graceful Degradation**: Falls back to vector-only or memory-less modes if dependencies are missing
* **Asynchronous Pipeline**: Non-blocking indexing and retrieval to keep the host UI responsive
* **Privacy-First Design**: Configurable PII redaction, local-only storage, and cryptographic shredding
* **Structured Memory**: Relationships, communities, and temporal tracking of entities

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
│  │              Memory Indexer (Broker)          │  │
│  │  • Entity extraction (GLiNER/spaCy/LLM/Heur)  │  │
│  │  • PII redaction & access control             │  │
│  │  • Vector + Graph dual-write                  │  │
│  └───────────────┬───────────────────────────────┘  │
│                  │                                   │
│  ┌───────────────▼───────────────────────────────┐  │
│  │           Hybrid Memory Retriever              │  │
│  │  • FAISS vector store (similarity search)      │  │
│  │  • Kùzu graph store (relation traversal)       │  │
│  │  • RRF fusion & context window management      │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- [pygpt-net](https://github.com/synaptrix/pygpt-net) installed and running
- Python 3.9+

### Steps

1. Clone the repository:
```bash
cd ~/.pygpt-net/plugins
git clone https://github.com/cipher/synth_memory.git
```

2. Install dependencies:
```bash
pip install faiss-cpu kuzu gliner-spacy
```

3. Restart pygpt-net and enable the **"SynthMemory (Nexus)"** plugin in settings.

## License

MIT License - Copyright (c) 2024-2026 Cipher
