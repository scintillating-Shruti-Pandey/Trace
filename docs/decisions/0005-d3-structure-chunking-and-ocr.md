# Architectural Decision Record D3 — Structure-Aware Chunking and OCR Strategy

- **Status**: Settled
- **Date**: 2026-10-25
- **Spec Reference**: §6.2, §6.3, §19 (D3)
- **Deciders**: Corpus Owner, Retrieval Owner

## Context

Industrial technical documentation consists of multi-level headings (H1–H4), structured tables (torque specifications, sensor pinouts), numbered sequential procedures, and safety callout boxes. Naive fixed-token sliding-window chunking destroys hierarchical context, separating procedure steps from their parent equipment headers and hazard warnings.

Spec §19 D3 also evaluated OCR extraction strategy: Tesseract OCR with VLM fallback versus direct VLM extraction.

Direct VLM extraction introduces latency, non-deterministic token generation, and potential billable API costs ($0.00 spend rule). Tesseract provides reliable, fast deterministic extraction for scanned tabular inspection logs.

## Decision

1. **Structure-Aware Chunking**:
   - Implemented hierarchical Markdown/HTML structure-aware splitting preserving document section paths (`manual.pdf > Section 4.2 Hydraulic Assembly > Step 3 Check Valves`).
   - Breadcrumb metadata is prefixed to chunk text before embedding, ensuring dense search matches both macro-topic and micro-step queries.
   - Preserves table markdown grids and warning callouts intact within chunk boundaries (200–500 tokens).

2. **Deterministic Extraction**:
   - Prioritized structured text parsing and local deterministic OCR without billable cloud APIs.
   - Text extracted from technical drawings and diagrams is stored with spatial bounding metadata when available.

## Consequences

- 28 technical documents across 3 industrial equipment families were structured into 67 high-fidelity chunks.
- Phase 4 document retrieval achieved 100% Recall@5 with zero orphaned procedure steps.
- Zero monetary spending requirement maintained.
