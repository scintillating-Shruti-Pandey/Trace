# Using external datasets without local copies

The user's 2026-10-04 request takes precedence over the local-sample instructions in
`records/AGENT_DATASET_SETUP.md`. Use remote reads into memory; do not save sample Parquet,
caption tables, annotation JSON, archives, or media. Save only code and verification
reports for now. Any need for local dataset files must be surfaced before proceeding.

## October 24 assessment

**Later user decision:** FORGE is removed, not pending. Do not wait for access. Define
an alternative industrial-image evaluation and state its coverage honestly. Small access
checks precede the full 20–25-video corpus, derived images and held-out query evaluation;
they are not the final dataset size. See the current [progress report](build-status.md).

Fresh evidence and candidate selection are in the
[remote-data assessment](data-readiness-2026-10-24.md). IndEgo individual video byte
ranges and matching annotations worked; full frame decoding and its reusable reader
remain pending approval. Four InspecSafe preview images decoded in memory with complete
caption fields, but other fields remain truncated. No full-row or benchmark readiness
is claimed. Existing CLI behavior is unchanged. The earlier assessment's FORGE status
has been superseded by the decision above.

## Previously verified reader paths (October 4)

| Dataset | Remote path verified | Limit |
|---|---|---|
| LoVR | Five complete caption rows via the Dataset Viewer API | Full-table traversal unverified; another offset returned HTTP 500. Video and clip caption tables are combined by the Viewer, so do not treat the default split as a clean clip-only benchmark. |
| MomentSeeker | The three small JSON annotation files, resolved at a Hub commit SHA | Actual source videos and query image/video inputs remain remote and were not fetched. Annotation access is not an end-to-end benchmark run. |
| FORGE | Public catalog metadata only | Manual access gate and HTTP 401; license text absent. |
| InspecSafe-V1 | Catalog and truncated preview metadata | Row endpoint fails; no verified bounded path to complete samples yet. |

## Reader and commands

### Register verified remote references in PostgreSQL

`app.datasets.register_remote` validates a completed verification report, then rechecks
the pinned public catalog, narration hashes and annotation counts/bounds in RAM. It
requires 20–25 unique source paths/trial groups, three frame checks per video, the original
2–15 minute duration bounds and the six-hour cap. No media is decoded again by registration;
the historical frame proof is retained with the verification report's SHA-256.

```powershell
# Uses the existing API image/dependencies and local source code; no rebuild required.
docker compose run --rm --no-deps --pull never `
  -e PYTHONPATH=/workspace/backend -v "${PWD}:/workspace:ro" -w /workspace api `
  python -m app.datasets.register_remote docs/verification/indego-final-2026-10-24.jsonl
# Add --commit to register after successful validation.
```

The additive `0002` migration creates `remote_sources`. It holds source URLs, revision,
license/attribution, duration, category, filename group and verification hashes/counts.
It stores no media, narration text, annotation labels, or frame pixels. Existing asset
storage and checksum constraints remain intact; no fake object keys/checksums are used.
Registration is transactional, serialized, capped at 25, and idempotent for identical
input. Different provenance for an existing source requires explicit review.

`GET /api/v1/remote-sources` lists this catalog. `GET /api/v1/status` exposes its count
separately from ingested `assets`. These are unreviewed sources, not classified equipment,
closed splits, VLM captions, verified ground truth, or a completed Phase 0 corpus.
The local Compose override mounts application/migration code read-only over the cached
dependency image; dependency changes still require an explicit image build.

### IndEgo video reader (implemented October 24)

`backend/app/datasets/indego.py` discovers repair and assembly candidates at revision
`c822468b5e0c9c42ebbf2939d3be936c2b203704`. It joins individual MP4s, VIA temporal
annotations and narration by filename. Empty narrations are reported/excluded. It checks
the public gate and expected CC BY 4.0 terms before reading, and refuses incomplete
directory listings instead of silently assuming a whole repository was traversed.

Selection is reproducible (SHA-256 ordering with `trace-42` prefix), excludes probable
paired views using filename groups, and targets 2–15 minute videos within the six-hour
cap. This is **not** a stratified sample or a closed evaluation split. Filename grouping
needs human trial/participant review. Metadata-only duration estimates use annotation
bounds; only decoder runs measure actual duration and check annotation bounds against it.

`backend/app/datasets/remote_video.py` supplies a loopback seekable HTTP source to the
existing container's FFmpeg. Upstream requests must return exact HTTP 206 ranges.
Each active object uses 256 KiB blocks, a 4 MiB RAM cache, and a 32 MiB transfer budget.
Budget exhaustion, malformed annotations and decoder failures are explicit failures.
No fallback downloads occur. At most three readers may run concurrently; these checks
use CPU decoding, not GPU models. Container and workspace are mounted read-only.

From PowerShell, with Docker running and the existing `trace-api:latest` image available:

```powershell
$traceDocker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
& $traceDocker run --rm --pull never --read-only `
  -e PYTHONPATH=/workspace/backend `
  --mount "type=bind,source=$PWD,target=/workspace,readonly" `
  --workdir /workspace trace-api:latest `
  python -m app.datasets.indego --category all --limit 25 --workers 3 --decode
```

`--decode` probes each selected video and decodes 96×96 RGB validation frames at
5%, 50% and 95% of its duration. The small frame size is for a decoding check, not the
future embedding input resolution. Omitting `--decode` verifies MP4 prefixes and
annotations only. Use `--category repair` or `assembly` to inspect one category.
The CLI prints source paths, hashes, counts, measured durations and failures, never
narration content or raw media. This output may be saved as a verification report.
Exit status 1 means the requested count was not reached or discovery failed; rejected
candidates remain visible even if other candidates bring the successful count to target.

This is an external reader, not corpus ingestion: it writes no assets, segments,
embeddings or evidence links to PostgreSQL. The deferred MinIO architecture is unchanged.
Raw frames and narrations remain in memory. The current [progress report](build-status.md)
links the actual run evidence and distinguishes accessible videos from indexed assets.

### Existing annotation and caption reader

The reader in `backend/app/datasets/huggingface.py` uses Python's standard library.
No `datasets`, Hugging Face Hub cache, DuckDB extension, or new package installation is
needed for these verified paths. It makes HTTPS requests, keeps responses in RAM, and
never follows image/video references automatically. Each response is capped at 4 MiB.
It rejects gated repositories and truncated rows rather than returning partial evidence.

Run from the project root in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m app.datasets.huggingface inspect all
.\.venv\Scripts\python.exe -m app.datasets.huggingface sample lovr --config default --split train --limit 5
.\.venv\Scripts\python.exe -m app.datasets.huggingface annotations --task text
.\.venv\Scripts\python.exe -m app.datasets.huggingface annotations --task text-image
.\.venv\Scripts\python.exe -m app.datasets.huggingface annotations --task text-video
```

The CLI prints metadata/schema/count summaries, not dataset rows. A later consumer can
use `iter_rows(...)` or `read_moment_annotations(...)` directly and process their returned
objects in memory. Row iteration requires an explicit split and has a 500-row call cap.
The five-row smoke check uses the start of the train split: it is not a random/stratified
sample, a retrieval evaluation, or a replacement for a held-out test set.

MomentSeeker JSON reads fetch one whole small annotation file into memory. Its three
files were 384,920, 164,309, and 165,944 bytes in the checked revision. Their paths remain
references to media, not playable individual URLs. Viewer reads use the server's current
conversion and are not revision-pinned; only direct annotation JSON reads are pinned.

## What streaming does and does not mean

Remote data still crosses the network and uses RAM. “No local copies” here means no
persistent dataset payload or cache files written by this reader; it does not mean
zero network transfer, zero RAM, or remote model execution. A Hugging Face dataset
repository stores data; processing still needs our own compute or a separate hosted service.

LoVR video data is in three compressed archive parts totaling roughly 95.9 GB. InspecSafe
has compressed train/test archives of about 17.9/5.75 GB. Sequential archive streaming could
avoid retaining an archive on disk but still transfer substantial unwanted data before
reaching a desired item. That path was deliberately not attempted. Do not convert internal
archive paths to invented `resolve/...mp4` URLs or silently download the archives.

No external dataset supplies Trace's linked manufacturing video/report/manual corpus.
Remote benchmarks can support evaluation and early experiments, but the human-authored
links and matching real source material in Phase 0 are still required.

## Follow-ups

FORGE is removed from Phase 3 delivery. For any future approved gated source, configure
an approved read token locally
when authentication support is added; never paste credentials into chat or reports.
LoVR video access and complete InspecSafe samples can remain deferred while the verified
annotation paths are used. No large download is authorized by these follow-ups.
