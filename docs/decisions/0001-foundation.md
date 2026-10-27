# Foundation decisions — 2026-10-04

Trace follows the engineering spec over earlier briefing alternatives. PostgreSQL 16
with pgvector remains the only metadata/vector database; Redis and arq remain the queue
choice (D1). The initial API uses synchronous SQLAlchemy sessions in FastAPI threadpool
routes, while Redis/arq operations are asynchronous. Heavy processing belongs in the worker.

Docker Desktop was installed by the user. An initial SQLite fallback was withdrawn after
the user required missing dependencies to be surfaced rather than silently substituted.

MinIO Docker Hub access failed. Its official repository now documents source-only
distribution. The user authorized deferring components that can be completed later;
MinIO and the worker are therefore in an opt-in media profile. Registration responds
with an explicit unavailable error while disabled. No replacement storage was selected.

The initial schema retains spec vector dimensions without loading any model. Runtime
model/dimension identity checks must be added before retrieval is enabled.

The spec's RRF test example in 14.2 has its ordering reversed: 1/61 is less than 2/65.
When fusion is implemented, tests must follow the formula in 8.4. No retrieval algorithm
or evaluation target is changed by this clarification.
