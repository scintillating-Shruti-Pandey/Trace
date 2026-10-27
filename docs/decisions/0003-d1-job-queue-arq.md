# Architectural Decision Record D1 — Job Queue: arq vs Celery

- **Status**: Settled (Adopted default)
- **Date**: 2026-10-04 / 2026-10-25
- **Spec Reference**: §9.1, §9.3, §19 (D1)
- **Deciders**: Platform Owner, Core Engineering

## Context

Heavy background workloads (video segmentation, frame extraction, transcription, and multi-lane embedding computation) must not block synchronous FastAPI request cycles. Spec §19 D1 evaluated `arq` versus `Celery` as the asynchronous task queue.

Celery brings a large dependency tree (Kombu, billiard, vine), complex multi-broker configurations, and historical friction with Python's modern `asyncio` event loop. Conversely, `arq` is native to `asyncio`, uses Redis directly via `redis-py` / `aioredis`, has zero external broker abstractions, and provides straightforward job timeouts and retry guarantees.

## Decision

We chose `arq` (`WorkerSettings` in `backend/app/ingest/worker.py`) backed by Redis 7 (`redis://redis:6379/0`).

1. **Asyncio-native**: Worker tasks run natively within Python's `asyncio` event loop without sub-process monkey-patching.
2. **Lightweight Operational Footprint**: Uses the existing Redis container deployed for rate-limiting and cache coordination.
3. **Opt-in Profile Isolation**: The worker is colocated under the `media` Docker Compose profile, keeping the default development tier minimal while supporting background ingestion.

## Consequences

- Ingestion manifests are validated through Pydantic schemas and enqueued via `arq.create_pool()`.
- Threadpool offloading (`asyncio.to_thread`) is utilized for synchronous SQLAlchemy database operations inside worker tasks.
- Heavy Celery broker dependencies and configuration files are avoided.
