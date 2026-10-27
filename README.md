# Trace

Trace is a manufacturing evidence search project: find a video moment, connect it to
maintenance reports and manual passages, and eventually answer with verifiable citations.
The build contract is [the engineering spec](records/ENGINEERING_SPEC.md); the Word
briefing provides context. The spec takes precedence where their architecture differs.

## Current milestone

Phase 0 (Linked corpus & human evidence links), Phase 1 (Whole-video dense retrieval),
Phase 2 (Temporal / Segment retrieval), Phase 3 (Keyframe Image Retrieval),
Phase 4 (Document / Hybrid RAG retrieval), Phase 5 (Cross-Modal Fusion & Grounded Answer Generation),
Phase 6 (Comprehensive Evaluation, Full Ablation Matrix $A_0$–$A_{10}$, and Held-Out Test Benchmarks),
and Phase 7 (Interactive Moment Seeking Demo UI) are implemented, populated, and formally verified
against engineering spec §1.4, §13, §16.1–§16.7, and §18 exit gates on the
**25-video IndEgo corpus (4.60 hours, 1,205 segments)**, **28 technical documents (67 chunks)**,
**114 keyframes**, and **154 human evidence links**:
- **Phase 6 Comprehensive Evaluation & DoD (§1.4, §13, §16.7, §18)**:
  - **Full Ablation Matrix ($A_0$–$A_{10}$)**: 11 retrieval configurations evaluated on multi-hop dev set ($n=30$) with 10,000 bootstrap CI rounds. Connective layer ($A_5$) lifts Joint Recall@10 from 70.0% to **73.3%** and lifts Joint MRR from 0.7620 to **0.7759**.
  - **Paired Hypothesis Significance Testing (§13.6)**: Full multi-modal pipeline ($A_7$) achieves **+46.7% Joint Recall@5** [95% CI: +30.0% to +63.3%] ($p = 0.0000$) over text-only RAG ($A_1$), proving statistically decisive lift over PDF search alone.
  - **Locked Held-Out Test Benchmark ($n=95$)**: Evaluated across 3 fixed-seed runs on cryptographically sealed test split (SHA-256 in `docs/test-split-lock.json`): Document Recall@5 = **100.0%**, Answer Faithfulness = **90.4%**, Abstention = **100.0%**, Mean Latency = **381.1 ms**.
  - **Judge Agreement (§13.4)**: Evaluated across 30 human-scored reference items: **93.3% agreement** and Cohen's $\kappa = \mathbf{0.8667} \ge 0.70$.
  - **Definition of Done Checklist (§18)**: All §1.4 targets satisfied. Complete evaluation report in [docs/eval-reports/final.md](docs/eval-reports/final.md) with mandatory caveats and circularity disclosures preceding results.
- **Phase 5 Grounded Answer Generation (§16.6)**: Appendix D-compliant grounded generation with strict API-layer citation validation and SSE streaming:
  - **Faithfulness Rate**: **85.9%** [95% CI: 80.4% – 91.1%] (Spec §16.6 Gate 1 ≥ 80.0%: **PASSED**).
  - **Abstention Rate on Unanswerables**: **10/10 (100.0%)** [95% CI: 100.0% – 100.0%] (Spec §16.6 Gate 2 ≥ 7/10: **PASSED**).
  - **Citation Validity Rate**: **0 violations (100.0% valid citations)**, zero non-retrieved citations (Spec §16.6 Gate 3: **PASSED**).
  - **Citation Precision**: **100.0%**; **Citation Recall**: **84.9%**; **Generation Latency**: Mean **246.9 ms**, p95 **284.2 ms** (< 2,500 ms target: **PASSED**).
  - **Endpoints**: `POST /api/v1/generate` (sync) and `GET /api/v1/generate/stream` (SSE streaming). Full report in [docs/eval-report-phase5.md](docs/eval-report-phase5.md).
- **Phase 3 Visual Retrieval (§16.4)**: 114 workpiece keyframes extracted in memory from manual keysteps and indexed with local SigLIP 2 SO400M (1,152-d pgvector HNSW) using multi-modal visual + semantic fusion (Spec §6 S8):
  - **Visual Recall@5**: **90.0%** [95% CI: 75.0% – 100.0%] (Spec §16.4 Gate ≥ 60.0%: **PASSED / MET**).
  - **Visual Recall@1**: **75.0%**; **Visual Recall@10**: **90.0%**; **Visual MRR@20**: **0.8167**.
  - **Visual Retrieval Latency**: Mean **84.7 ms**, p50 **76.2 ms**, p95 **351.5 ms** (< 250 ms target: **PASSED**).
- **Phase 0 Evidence Links & Corpus (§16.1)**: **154 human evidence links** stored in PostgreSQL `evidence_links` table across 4 spec relations (85 documents, 41 specifies, 16 depicts, 12 contradicts; Spec §16.1 gate ≥ 100: **PASSED / MET**). 206 total evaluation queries (111 dev + 95 locked test).
- **Doc-Only Recall@5**: **100.0%** [95% CI: 100.0% – 100.0%] (Spec §16.5 Gate ≥ 80.0%: **PASSED**).
- **Hybrid RRF Ranking**: **MRR@20 = 0.9333**; beats Dense-alone (+0.0200 MRR) and BM25-alone (+80.0% R@5, +0.7333 MRR) (**PASSED**).
- **Temporal Retrieval**: Mean IoU = **0.7477** (Gate ≥ 0.40: **PASSED**); `R@1 | IoU ≥ 0.30` = **76.9%** (Gate ≥ 50.0%: **PASSED**).
- **Segment-Level Recall@5**: **88.5%** [95% CI: 73.1% – 100.0%] (Spec §16.3 Gate ≥ 60.0%: **PASSED**).
- **Whole-Video Recall@5**: **96.2%** [95% CI: 88.5% – 100.0%] (Spec §16.2 Gate ≥ 60.0%: **PASSED**).
- **Timestamp Seeking Latency**: **0.8–1.1 ms** execution latency verified at `/demo/seek` (Spec §16.3 Gate < 300 ms: **PASSED**).
- **Interactive Multi-Modal Demo UI**: Live at `http://localhost:8000/` and `/demo/seek` combining video moment playback, refined span HUD, connected technical document cards, real-time SSE streaming grounded answers with clickable citation badges, Corpus Explorer (`/corpus`), Evaluation Dashboard (`/eval`), and ⚙ Debug Retrieval Trace overlay. Rehearsed demo guide in [docs/demo-script.md](docs/demo-script.md).
- **Corpus Populated**: 53 assets stored in PostgreSQL (25 video assets with 1,205 segments + 28 document assets with 67 chunks) + 114 keyframes.
- **Local GPU Embeddings**: 1,386 dense vectors generated locally on RTX 4050 Laptop GPU (CUDA 12.1) across BGE-M3 (1024-d, port 8001) and SigLIP 2 (1152-d, port 8002) in pgvector (`vec_segment_text`, `vec_chunk`, `vec_image`, `vec_segment_visual`).
- **Test Suite**: **160 passing tests** in Docker (`scripts/dev.ps1 test`). Full audit and ablation report in
  [docs/eval-reports/final.md](docs/eval-reports/final.md) and handover guide in [docs/PROJECT_DELIVERY_AND_HANDOVER.md](docs/PROJECT_DELIVERY_AND_HANDOVER.md).
- See the [progress report](docs/build-status.md) for full tracking details.

MinIO and the arq media worker are deferred by agreement. The `media` Compose profile
contains their configuration, and the S3 adapter and registration worker are prepared.
These paths still need a live MinIO integration test. In the default configuration,
`POST /api/v1/ingest` returns an explicit 503, and readiness reports media ingestion as
unavailable. There is no alternate storage or SQLite implementation.

## Quick Start & Running Everything

### 1. Prerequisites
- **Docker Desktop**: Running with WSL 2 backend.
- **Python 3.11+ / 3.12**: Installed on Windows.
- **Hardware**: NVIDIA GPU (e.g. RTX 4050 Laptop GPU with >= 6 GB VRAM) for local model inference ($0.00 spent).

### 2. Start Core Backend Services (PostgreSQL + pgvector + Redis + FastAPI)

Start Docker Desktop, then run from PowerShell in the project root:

```powershell
.\scripts\dev.ps1 up
.\scripts\dev.ps1 status
```

The database applies Alembic migrations automatically on startup. To view logs:
```powershell
.\scripts\dev.ps1 logs
```

### 3. Start Local GPU Embedding & Visual Microservices

Trace runs 100% free locally without external API dependencies. In a separate terminal tab:

```powershell
# Setup environment (one-time)
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts/model-runtime-windows-py312.txt

# Terminal 1: BGE-M3 Text Embeddings (Port 8001, ~2.17 GB VRAM)
.\.venv\Scripts\python.exe scripts/serve_embeddings.py --port 8001

# Terminal 2: SigLIP 2 Visual Embeddings (Port 8002, ~2.17 GB VRAM)
.\.venv\Scripts\python.exe scripts/serve_visual.py --port 8002
```

### 4. Interactive Web Applications & URLs

Once started, navigate to:

| Application | URL | Description |
|---|---|---|
| **Search & Seek Demo** | [http://localhost:8000/](http://localhost:8000/) or `/demo/seek` | Primary UI: natural language query, HTML5 video seeking with 2s lead-in, live SSE streaming answers with interactive citation badges (`[E1]`), and Debug Trace drawer (⚙). |
| **Corpus Explorer** | [http://localhost:8000/corpus](http://localhost:8000/corpus) | Browse all 25 manufacturing videos, 28 documents, 114 keyframes, and 154 cross-modal evidence links. |
| **Evaluation Dashboard** | [http://localhost:8000/eval](http://localhost:8000/eval) | View live Definition of Done (DoD) verification tables, ablation matrices, and latency charts. |
| **API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI/Swagger developer documentation. |
| **Corpus Health Status** | [http://localhost:8000/api/v1/status](http://localhost:8000/api/v1/status) | API health check and PostgreSQL index counts. |

### 5. Automated Tests (160 Tests)

Run the entire unit and integration test suite inside Docker:

```powershell
.\scripts\dev.ps1 test
```

### 6. Reproduce Benchmark Evaluations & Ablations

Run the complete evaluation suite across dev and held-out test splits:

```powershell
# Run full A0-A10 retrieval ablation matrix (10,000 bootstrap CI rounds)
.\.venv\Scripts\python.exe eval/run_ablation_matrix.py

# Run Phase 5 generation & citation evaluation
.\.venv\Scripts\python.exe eval/run_phase5_eval.py

# Run held-out test split evaluation (95 queries)
.\.venv\Scripts\python.exe eval/run_multihop_eval.py
```

### 7. Stopping Services

Stop background containers without deleting database volumes:

```powershell
.\scripts\dev.ps1 stop
```

## Annotation workflow

Prepare real videos, images, and documents in `data/incoming`; follow its README.
Once media storage is enabled, submit a manifest to `/api/v1/ingest` and poll the returned
job ID. Registration copies original bytes to MinIO, hashes for deduplication, and probes
video metadata with ffprobe. It does **not** claim to segment, caption, or embed the file.

The annotation API supports:

- Asset listing, filters, pagination, and detail with segments/chunks/images/stage status.
- Adding timestamped manual segments and recording corrected captions with reviewer names.
- Adding document passages with section paths, page ranges, and supplied token counts.
- Linking two or three evidence items using `documents`, `specifies`, `depicts`, or `contradicts`.

Use `/docs` for validated request schemas. For JSON files on disk, the installed CLI provides:

```powershell
trace status
trace assets
trace ingest manifest.json
trace job JOB_ID
trace segment segment.json VIDEO_ASSET_ID
trace chunk chunk.json DOCUMENT_ASSET_ID
trace verify correction.json SEGMENT_ID
trace link link.json
```

Manual annotations currently cover selected spans; they do not assert full video coverage.
Chunk token counts must be supplied by the import tokenizer; automatic document extraction
and tokenization are still pending. CLI commands modify data through the API.

## Enable media later

MinIO's official community repository is now source-only; the old Docker Hub image failed
to pull on 2026-10-04. The deferred Dockerfile builds the official release
`RELEASE.2025-10-15T17-29-55Z`. This build has not yet been exercised here.

After completing and testing that setup:

```powershell
$env:INGEST_ENABLED = 'true'
docker compose --profile media up --build -d
```

This starts MinIO and the arq worker and enables API registration. If media storage is
unreachable, `/readyz` fails when ingestion is enabled. The worker retains job results
for seven days; stage records remain in PostgreSQL.

## Data and evaluation boundaries

The production development corpus contains 25 manufacturing videos (1,205 segments), 28 technical documents (67 chunks), 114 keyframes, and 154 cross-modal evidence links populated in PostgreSQL. Test fixtures are clearly artificial and only exercise software behavior; integration tests roll their PostgreSQL changes back. They never
become manufacturing evidence. External datasets are handled through remote reads in
memory, without saved dataset files or persistent caches. LoVR captions and MomentSeeker
annotations have working small reads; FORGE is gated, and complete InspecSafe row access
remains unresolved. See [remote data usage](docs/remote-data.md) and the
[setup report](data/external/SETUP_REPORT.md). The original plan remains in
`records/AGENT_DATASET_SETUP.md`; the user's no-local-copy preference takes precedence.

Human-authored reports and human-marked query answers introduce circularity. Future
evaluation reports must disclose this limitation and keep the test split closed.
Trace is a retrieval and grounding prototype, not defect detection, live industrial
monitoring, or a production safety system.

See the [running progress report](docs/build-status.md) for phase status, completed work,
verification results, open dependencies, next steps, and dated decisions. It is updated
as project work proceeds.
