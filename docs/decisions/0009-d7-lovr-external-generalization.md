# Architectural Decision Record D7 — LoVR External Generalization Benchmark Protocol

- **Status**: Settled (Protocol defined, local disk execution deferred)
- **Date**: 2026-10-04 / 2026-10-25
- **Spec Reference**: §13.7, §19 (D7)
- **Deciders**: Retrieval Owner, Project Sponsor

## Context

Spec §13.7 and §19 D7 proposed running the unchanged Phase 1–2 retriever on a 200-clip subset of the public LoVR benchmark (`debugger123/LoVR-benchmark`, arXiv 2505.13928) to provide an author-independent, external benchmark comparison alongside published baselines.

During dataset auditing and access verification (documented in `data/external/SETUP_REPORT.md` and `docs/decisions/0002-remote-datasets.md`), three significant constraints emerged:
1. **Zero Disk Storage Mandate**: The user mandated zero persistent disk media caching and memory-only streaming. LoVR video media is packaged in 3 multipart zip archives totaling 95.9 GB. Downloading or unpacking this archive would violate disk caching boundaries.
2. **Upstream API Instability**: While initial 5-row caption streaming succeeded, attempting offset pagination on the Hugging Face Dataset Viewer API (e.g., offset 32,312) consistently returned HTTP 500 errors.
3. **Domain Representation**: LoVR is a generic long-video benchmark. It lacks the cross-modal connective evidence layer (linking video keysteps to maintenance manuals and engineering drawings), which constitutes Trace's core technological contribution.

## Decision

1. **Defer Local Media Download**:
   - The 200-clip physical video ingestion is deferred, adhering strictly to the zero-disk media caching rule.
   - The remote dataset client (`backend/app/datasets/huggingface.py`) remains capable of streaming LoVR caption rows in RAM when upstream Hugging Face endpoints are available.
2. **Validation Protocol Standardized**:
   - A standardized benchmark script (`eval/benchmark_lovr.py`) is specified for Person 2 if local disk allocation is granted in a secondary phase.
   - Trace's core evaluation focus is preserved on the authentic 25-video, 28-document manufacturing corpus where ground-truth cross-modal links are rigorous and verified.

## Consequences

- Zero disk space consumed for multi-gigabyte external archives ($0.00 spent).
- Eliminates reliance on unstable upstream Hugging Face API pagination.
- Author-independent benchmark remains ready to execute whenever external storage permissions are enabled.
