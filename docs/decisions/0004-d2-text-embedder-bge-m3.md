# Architectural Decision Record D2 — Text Embedder: BGE-M3 vs E5-Large

- **Status**: Settled (Adopted default)
- **Date**: 2026-10-24 / 2026-10-25
- **Spec Reference**: §5.3, §8.1, §19 (D2)
- **Deciders**: Retrieval Owner, Platform Owner

## Context

Text retrieval spans whole videos (titles and summaries), temporal segments (dense visual captions and transcripts), and technical documents (manuals, SOPs, and inspection reports). The embedder must support technical terminology, multilingual nomenclature (German/English manufacturing machinery), and long sequences up to 8,192 tokens without truncation.

Spec §19 D2 evaluated `BAAI/bge-m3` versus `intfloat/multilingual-e5-large`.

While `e5-large` is a solid dense model, it is restricted to 512 tokens and dense-only similarity. In contrast, `bge-m3` offers:
1. Native 8,192 input context length (eliminating premature chunk truncation).
2. Dense representations (1024-dimensional vectors).
3. Sparse lexical representations (multi-lingual term weights).
4. Multi-vector cross-attention capabilities.
5. High benchmark performance on technical and structured documentation.

## Decision

We chose `BAAI/bge-m3` as the primary unified text embedding model across all text lanes:
- Deployed as a dedicated local FastAPI microservice on `127.0.0.1:8001` running under CUDA 12.1 in FP16 precision.
- Consumes ~2.17 GB VRAM, fitting comfortably within the fixed RTX 4050 6 GB GPU hardware budget alongside the visual encoder.
- Fallback adapter (`backend/app/embeddings.py`) maintains zero-cost local execution with graceful fallback handling.

## Consequences

- 1024-dimensional HNSW cosine index (`vector_cosine_ops`) is standardized in PostgreSQL via `pgvector`.
- Whole-video retrieval achieved Recall@5 of 96.2% and MRR of 0.8910 in Phase 1 evaluation.
- Document hybrid RAG achieved Recall@5 of 100.0% and MRR of 0.9333 in Phase 4 evaluation.
