# Architectural Decision Record D4 — Visual Lane Retention in Multi-Lane Retrieval

- **Status**: Settled (Retained based on Phase 6 ablation evidence)
- **Date**: 2026-10-25
- **Spec Reference**: §5.4, §8.3, §13.2 (Ablation A4), §19 (D4)
- **Deciders**: Retrieval Owner, Evaluation Owner

## Context

Video search often struggles when speech transcripts or auto-generated captions omit specific visual events (e.g., subtle fluid leaks, physical crack formations, machine vibration patterns, dial gauge readings). Direct visual representation creates a second retrieval lane matching visual queries against raw keyframes.

Spec §19 D4 posed the question: *Keep or cut the direct visual video lane?*
The criteria: Retain the visual lane unless Phase 6 ablation config $A_4$ (ablating the visual lane) proves that visual features provide zero lift or degrade performance.

## Decision

We chose to **KEEP** the direct visual video lane powered by `google/siglip2-so400m-patch14-384`:

1. **Empirical Evidence from Ablation Matrix ($A_4$)**:
   - In Phase 6 ablation testing (`docs/eval-reports/final.md`), removing the visual lane ($A_4$) reduced Keyframe Visual Recall@5 from 90.0% to 0.0% and degraded overall multi-modal Joint Recall@10 from 73.3% to 63.3%.
   - Queries with visual cues ("amber warning light on panel", "corroded valve stem") failed completely without visual vector matching.
2. **Hardware Co-Residence**:
   - `SigLIP 2` runs as a co-resident FP16 microservice on port 8002 consuming ~2.18 GB VRAM.
   - Combined with `BGE-M3` (~2.17 GB VRAM), total GPU utilization is ~4.35 GB, safely below the 6.0 GB VRAM limit of the RTX 4050 GPU.
3. **In-Memory Streaming**:
   - Keyframes are decoded in memory via `pyav`/`decord` without persistent image files on disk, complying with the zero-disk media caching mandate.

## Consequences

- 114 workpiece keyframes are indexed with 1152-dimensional vectors in `pgvector`.
- Reciprocal Rank Fusion (RRF $k=60$) seamlessly combines the segment-text, segment-visual, chunk, and image lanes into a unified ranked evidence pool.
