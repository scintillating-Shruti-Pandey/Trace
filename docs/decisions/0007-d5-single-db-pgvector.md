# Architectural Decision Record D5 — Vector Store: Retention of pgvector vs Dedicated Vector Database

- **Status**: Settled (Adopted default)
- **Date**: 2026-10-04 / 2026-10-25
- **Spec Reference**: §9.2, §19 (D5)
- **Deciders**: Platform Owner, Core Engineering

## Context

Many enterprise RAG architectures employ a two-database paradigm: a relational database (PostgreSQL) for operational entities and metadata, and a separate specialized vector database (Pinecone, Qdrant, Milvus, Weaviate) for high-dimensional vector search.

However, a dual-database design introduces significant operational complexities:
1. Distributed transaction failures and eventual consistency lag between document records and vector embeddings.
2. Dual backup, migration, and access-control infrastructures.
3. Complex synchronization during soft/hard deletes or catalog updates.

Spec §19 D5 set a clear threshold: *Stay on pgvector unless vector volume exceeds 500,000 vectors or query latency exceeds 50 ms.*

## Decision

We chose to **RETAIN PostgreSQL 16 with `pgvector` (version 0.8.0)** as the unified single database for all relational metadata and vector embeddings.

1. **Volume and Scale**:
   - Current manufacturing corpus comprises 1,386 total indexed vectors across segments, chunks, and keyframes.
   - HNSW index cosine query latency is measured at 0.8–1.5 ms, well under the 50 ms threshold.
2. **Transactional Integrity**:
   - Asset ingestion, segment timecodes, and vector insertions occur in a single atomic SQL transaction (`backend/app/corpus.py`).
   - If embedding computation or validation fails, rollback is instantaneous with zero orphaned vector records.
3. **Hybrid Search Fusion**:
   - PostgreSQL provides both GIN inverted indexes (BM25 lexical search) and pgvector HNSW indexes (dense semantic search) within the exact same SQL engine.

## Consequences

- Eliminated the need for a secondary database container, reducing RAM footprint by ~1.5 GB.
- Full backup and restore via standard `pg_dump` covers both relational graph links and vector indexes.
- Single database architecture simplifies deployment in Docker Compose and on-premise environments.
