# Architectural Decision Record D8 — Observability: Structured JSON Logging & Tracing vs OpenTelemetry/Jaeger

- **Status**: Settled (Adopted structured logging + correlation IDs)
- **Date**: 2026-10-25
- **Spec Reference**: §10.1, §10.2, §19 (D8)
- **Deciders**: Platform Owner, Core Engineering

## Context

Observability in a multi-stage retrieval pipeline is critical. A single question passes through:
1. Query analysis & expansion
2. Dense & lexical document retrieval (GIN BM25 + BGE-M3)
3. Whole-video & temporal segment retrieval
4. Keyframe visual similarity (SigLIP 2)
5. Reciprocal Rank Fusion (RRF)
6. Cross-modal evidence link traversal
7. Temporal window refinement
8. Appendix D grounded generation with SSE streaming

Spec §19 D8 evaluated two observability architectures:
- Full OpenTelemetry (OTel) Collector with external Jaeger/Zipkin distributed tracing containers.
- High-performance structured JSON logging with request correlation IDs and an in-memory latency breakdown displayed in the UI.

Running an OTel daemon and Jaeger collector adds 2 additional containers and ~500 MB of continuous RAM overhead, adding operational friction to local developer environments and single-node edge deployments.

## Decision

We chose **Structured JSON Logging with Request Correlation IDs and the Interactive ⚙ Debug Trace Drawer**:

1. **Correlation IDs & Structured Logs**:
   - Every inbound request receives an `X-Request-ID` UUID propagation header.
   - All log records output structured JSON containing `event`, `trace_id`, `lane`, `latency_ms`, and candidate counts.
2. **Real-time Latency Waterfall (⚙ Debug Drawer)**:
   - For every search or streaming query, the backend captures nanosecond-precision micro-timestamps across all 6 pipeline stages and returns them via SSE events and debug headers.
   - The frontend's sliding ⚙ Debug Trace drawer renders a live visual waterfall (e.g., *BGE-M3 text embed: 14.2ms, SigLIP 2 visual encode: 28.1ms, pgvector HNSW search: 1.1ms, RRF fusion: 0.4ms*).
3. **No Heavy External Tracing Daemon**:
   - Zero additional Docker services required for tracing. Log outputs conform to standard 12-factor application design, readable by Datadog, CloudWatch, or Grafana Loki in enterprise production.

## Consequences

- Minimal runtime overhead (< 0.2 ms per query).
- Instant visibility into latency bottlenecks directly in the web UI for both developers and business stakeholders.
- Avoided extra container resource consumption on the local development workstation.
