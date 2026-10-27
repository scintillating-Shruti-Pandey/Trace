# Hosted BGE-M3 connection

> Current restriction: ZERO monetary spending. The user reports a configured key,
> but this does not authorize paid inference. The former $0.01 pilot proposal below
> is withdrawn. No inference calls have been made. Account billing inspection is
> blocked because local browser use is disabled in Work settings.

Implemented 2026-10-24. Offline adapter only; no live inference or indexing yet.
Uses existing HTTPX; its dependency moved from dev-only to runtime declarations.
No install or image build was performed.

## Set up a credential

1. Sign in or create an account at the [DeepInfra key dashboard](https://deepinfra.com/dash/api_keys).
2. Create an API key as described in the [official quickstart](https://docs.deepinfra.com/quickstart).
3. Edit `D:\Trace\.env` locally. Add `DEEPINFRA_API_KEY=your-key` (replace an existing
   blank entry rather than duplicating it). Preserve other settings. This file is
   ignored by Git; never put the real key in `.env.example`, source code or chat.
4. Tell the assistant only that the key is configured. Do not paste the secret.
   If the dashboard requires billing/top-up, report its requirement before paying;
   no account minimum or free credit has been verified.

The Hugging Face login does not configure this separate provider credential.
Setting a key does not initiate requests. Current settings read the project-root
`.env` for host commands; Docker does not yet receive this key. Do not run Compose
config dumps containing secrets. Container wiring will be part of a reviewed live step.

The earlier $0.01 live pilot is superseded by the zero-spending instruction.
Do not run this adapter against the live provider. Public model documentation lists
a usage charge; no account-specific free allowance or guaranteed zero-charge route
has been verified. Continue offline development/local feasibility checks instead.

## Adapter contract

`app.embeddings.BgeM3Client(Settings().deepinfra_api_key).embed(texts)` explicitly
calls `https://api.deepinfra.com/v1/openai/embeddings` for `BAAI/bge-m3`.
Nothing calls this automatically; it is not attached to ingestion, search or API routes.

- 1–16 nonblank texts, each at most 4096 UTF-8 bytes. This is a conservative guard,
  not a token counter. No silent input truncation; upstream chunking still required.
- Connect timeout 5 seconds, other HTTP operations 30 seconds. These are per-operation
  limits, not a guaranteed end-to-end wall-clock deadline.
- Response capped at 2 MiB. Validate exact model identifier, unique contiguous result
  indices, batch count, 1024 finite numeric dimensions, nonzero norms and integer usage.
- Reorder results to match inputs and L2-normalize vectors for cosine retrieval.
  Return vectors, token usage, attempt count, provider/model and normalization in RAM.
  Hosted weight revision remains unknown; never claim equivalence to a pinned local revision.
- Zero retries by default. Optional maximum two retries only for HTTP 429, respecting
  numeric Retry-After up to 10 seconds. Longer/date headers require rescheduling.
  Timeouts, connection failures and 5xx are not replayed because billing may be ambiguous.
- Fixed HTTPS destination, no redirects or environment proxies. Sanitized errors do
  not include provider response bodies, input text or credentials. Settings mask secrets.
- Usage is returned, not persisted; this does not implement a global spend cap.

## Verification

Offline tests use HTTPX MockTransport and fabricated vectors. They exercise response
reordering/normalization, missing credentials, invalid inputs, dimensions/nonfinite
values/usage/model errors, redirects/auth/server errors, bounded rate-limit retries,
timeouts, malformed JSON and oversized bodies. They prove adapter behavior, not real
provider access or embedding quality. Live output dimensions, truncation, provider
revision and actual token charging still require the approved pilot.

[Provider endpoint documentation](https://deepinfra.com/BAAI/bge-m3/api), checked
2026-10-24, advertises $0.010 per million tokens; pricing is not a spend authorization.
