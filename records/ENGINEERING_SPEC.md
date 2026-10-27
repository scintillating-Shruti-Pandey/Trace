# Multimodal Manufacturing Intelligence & Video Search (RAG)
## Engineering Specification v1.0

> **User-approved amendment — 2026-10-24 (Asia/Calcutta):** FORGE is removed from
> the delivery plan. References below to a mandatory FORGE run are superseded, not
> satisfied. Define and document an alternative industrial-image retrieval evaluation;
> its exact source/protocol still require verification and step approval. Do not label
> its results as FORGE scores or claim equivalent workpiece coverage. The existing
> RTX 4050 Laptop GPU with 6 GB VRAM is the fixed compute budget, superseding the
> 16–24 GB hardware assumption. Runtime feasibility remains to be tested. Corpus size,
> human evidence requirements, held-out evaluation and other quality gates remain in force.

| | |
|---|---|
| **Codename** | `mmi` (Multimodal Manufacturing Intelligence) |
| **Status** | Approved to build — spec frozen for Phase 0–2, living doc for Phase 3+ |
| **Date** | 14 September 2026 |
| **Source** | Derived from *Project Briefing: Multimodal Manufacturing Intelligence & Video Search with RAG* |
| **Owner roles** | Corpus Owner (Phase 0), Retrieval Owner (Phases 1–3), Platform Owner (Phases 4–7) |
| **Target** | Demoable end-to-end system in 10–13 focused weeks |

---

## How to read this document

This is a build spec, not a proposal. The briefing established *whether* to build; this establishes *what exactly gets built*. Sections 1–3 are the contract (what the system is, what it is not). Sections 4–8 are the data and ML layer. Sections 9–12 are the software layer. Sections 13–15 are how we prove it works. Section 16 is the schedule with binary acceptance gates.

Anything marked **[DECIDE]** is an open choice with a stated default — the default applies unless someone actively overrides it before that phase starts. Anything marked **[HARD CAP]** is a scope limit that is not negotiable mid-project; changing it requires an explicit decision recorded in Section 19.

---

# PART I — DEFINITION

## 1. What we are building

### 1.1 One-sentence definition

A retrieval-augmented question answering system over a linked corpus of manufacturing videos, images, and technical documents, which answers natural-language questions with a generated answer grounded in cited evidence — including the exact video timestamp.

### 1.2 The canonical query

Every design decision in this document traces back to one query shape:

> "Find the video where the hydraulic pump was inspected and tell me what problem was identified."

Correctly answering this requires the system to:

1. Locate the **video** about hydraulic pump inspection (whole-video retrieval)
2. Locate the **moment inside that video** where the inspection happens (temporal grounding)
3. Locate the **maintenance report** describing the finding (document retrieval)
4. Optionally locate the **manual section** giving the spec or procedure (document retrieval)
5. Optionally locate a **still image** of the component (image retrieval)
6. **Fuse** these into a single answer that is faithful to the evidence and cites each piece
7. Return a **jump-to-timestamp** affordance so a human can verify in two clicks

A system that does 1, 3 and 6 is a chatbot over PDFs. The project's value is in 2, 5 and 7 — and in evaluating each independently.

### 1.3 Explicit non-goals

These are out of scope and should be actively refused if proposed mid-project:

| Non-goal | Why |
|---|---|
| Training or fine-tuning any foundation model | We have neither the data volume nor the compute. Every model is used off-the-shelf. Fine-tuning a reranker is the *only* possible exception and only in Phase 6 stretch. |
| Real-time video stream ingestion | Corpus is batch-ingested and static. No live camera feeds. |
| Defect detection / anomaly classification as a product feature | We retrieve and ground; we do not claim to detect defects. FORGE is used as a generalization *check*, not as a classifier we ship. |
| Multi-tenant auth, RBAC, SSO | Single-user demo. One optional shared API key. |
| Production-grade uptime, HA, autoscaling | Single-node Docker Compose. |
| Sensor/ERP/PLC/digital-twin integration | Explicitly disclaimed in the briefing (§7). Not this project. |
| Publication-grade statistical claims | Eval set is self-built and partly circular. We report honestly with caveats. |

### 1.4 Definition of done

The project is **successful** when, on a held-out set of queries against our own corpus:

- The correct video segment is in the top-5 retrieved segments for ≥ 70% of video-grounded queries (Recall@5)
- Temporal localisation of the top-1 correct segment has mean IoU ≥ 0.4 against human-marked ground truth
- The correct document chunk is in top-5 for ≥ 80% of document-grounded queries
- An LLM judge, spot-validated by a human on ≥ 30% of items, rates ≥ 85% of generated answers as **faithful** (no claim unsupported by retrieved evidence)
- The full-system ablation shows a measurable, reported improvement over a text-only baseline on multi-hop queries
- The UI performs the full loop — type query, see answer, click citation, land on the right video second — in under 5 seconds p95 on warm cache

These numbers are targets, not guarantees. They are chosen to be honest: they are achievable with good engineering on a 25-video corpus and are *not* the kind of numbers that would justify a paper.

---

## 2. The two ML problems, kept separate

The briefing's §3.2 insistence on separating retrieval from grounded reasoning is load-bearing for the whole architecture. Concretely this means:

**Retrieval subsystem** — input: a natural-language query. Output: a ranked list of `Evidence` objects with scores. Measured by Recall@k, MRR, nDCG, and (for video) temporal IoU. Has **no** LLM in its scoring path except the reranker, which is separately ablatable. Can be evaluated offline with zero generation cost.

**Generation subsystem** — input: a query plus a fixed list of `Evidence` objects. Output: an answer string with inline citations. Measured by faithfulness, correctness, citation precision/recall. Can be evaluated with *oracle* evidence (ground-truth evidence injected directly), which isolates generation quality from retrieval quality.

This split gives four evaluation configurations, and we run all four:

| Config | Retrieval | Evidence given to generator | What it isolates | Config ids (§13.5) |
|---|---|---|---|---|
| R-only | real | — | Pure retrieval quality | A0–A8 |
| G-oracle | bypassed | ground-truth evidence | Pure generation quality | A9 |
| End-to-end | real | retrieved | The product | A7 |
| Adversarial | real | retrieved + 2 injected distractors | Robustness to bad retrieval | A10 |

The `Adversarial` config is the one that catches the most dangerous failure mode: a generator that confidently answers from a wrong-but-plausible document. If faithfulness collapses there, the generation prompt needs abstention logic before anything else gets tuned.

---

## 3. System architecture

### 3.1 Runtime topology

```
                          ┌──────────────────────────────────┐
                          │  React SPA (Vite + TS)           │
                          │  search · evidence panel · player│
                          └───────────────┬──────────────────┘
                                          │ HTTPS / JSON + SSE
                          ┌───────────────▼──────────────────┐
                          │  FastAPI  (api)                  │
                          │  /query /ingest /assets /eval    │
                          └──┬──────────┬──────────┬─────────┘
                             │          │          │
         ┌───────────────────▼──┐  ┌────▼──────┐  ┌▼──────────────────┐
         │ Retrieval Orchestr.  │  │ Postgres  │  │ Object store      │
         │  (in-process module) │  │ + pgvector│  │  (MinIO / disk)   │
         └──┬────┬────┬────┬────┘  └───────────┘  └───────────────────┘
            │    │    │    │
    ┌───────▼┐ ┌─▼───┐ ┌▼────┐ ┌▼─────────┐
    │ video  │ │image│ │ doc │ │ BM25     │       all four are pgvector
    │ seg idx│ │ idx │ │ idx │ │ (tsvector│       tables + one GIN index
    └────────┘ └─────┘ └─────┘ └──────────┘
            │
            ▼
    ┌───────────────────────┐        ┌─────────────────────────┐
    │ Reranker (LLM, async) │───────▶│ Generator (multimodal   │
    └───────────────────────┘        │ LLM, streaming)         │
                                     └─────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │ Worker (Celery/arq) — ingestion DAG, GPU-bound stages   │
    │  shot detect · caption · embed · OCR · chunk · index    │
    └─────────────────────────────────────────────────────────┘
```

### 3.2 Component inventory

| Component | Responsibility | Tech | Runs where |
|---|---|---|---|
| `web` | Search UI, evidence panel, video player with timestamp sync | React 19 + TS + Vite + Tailwind + shadcn/ui | Browser |
| `api` | HTTP contract, request validation, orchestration, SSE streaming | FastAPI + Pydantic v2 + uvicorn | CPU container |
| `worker` | Ingestion DAG: all heavy/GPU stages, idempotent and resumable | arq (async Redis queue) **[DECIDE: default arq, Celery if team prefers]** | GPU container |
| `db` | Metadata, all four vector indices, BM25 index, eval records | Postgres 16 + pgvector 0.8 + `pg_trgm` | CPU container |
| `blob` | Video files, extracted frames, thumbnails, HLS renditions | MinIO (S3 API) in dev, plain disk acceptable | CPU container |
| `cache` | Query cache, job queue, rate limits | Redis 7 | CPU container |
| `eval` | Offline eval harness, ablation runner, report generator | Python CLI + pytest | Anywhere |

**Why one Postgres and not a dedicated vector DB.** Four separate modalities need four indices, but they all need to be *joined back to the same document/segment metadata* for the evidence panel. pgvector keeps the join inside one query. The corpus is 25 videos → roughly 2–5k segments, 3–8k images, 5–15k text chunks. That is three orders of magnitude below where a dedicated vector store earns its operational cost. HNSW in pgvector handles this with sub-10ms latency.

> **[DECIDE]** If the corpus ever exceeds ~500k vectors, migrate the vector tables to Qdrant and keep Postgres for metadata. Write the retrieval layer behind a `VectorStore` protocol from day one so this is a one-file change. See §10.4.

### 3.3 The one architectural decision that isn't obvious

**Video retrieval runs on captions, not primarily on video embeddings.**

Current independent benchmarking of text-to-video embedding models shows the self-hostable open models performing poorly at zero-shot retrieval — in a 2026 head-to-head over 20 videos / 60 queries, InternVideo2-6B scored nDCG@5 of 0.186 and SigLIP 2 SO400M 0.202, versus 0.697–0.721 for hosted API models, with X-CLIP Base (a 150M-param model) beating InternVideo2-6B outright. That benchmark is small, vendor-published, and handicaps local models by feeding them 4–8 sampled frames against full-video API processing — so it is directional, not decisive. But the direction is consistent with what the same literature says about long-video grounding being fundamentally a *search* problem rather than an embedding-similarity problem.

Our domain makes this worse, not better: "hydraulic pump inspection" is a domain phrase whose visual signature (a person with a torch near a grey cylinder) is nearly identical to a dozen other maintenance actions. Raw visual embedding similarity will not separate them.

**Therefore the primary video retrieval path is:**

```
video → shot/segment detection → VLM caption per segment (rich, domain-prompted)
      → text embedding of caption → text-to-text vector search
```

and the **secondary path** is a direct visual embedding (SigLIP 2 over sampled frames), fused in via reciprocal rank fusion. The visual path catches queries that are genuinely visual ("show me the video with the yellow safety cage") where a caption may have omitted the detail; the caption path carries the semantic load.

This is also why Phase 0 exists and why the caption prompt (Appendix C) is a first-class engineering artifact, not a throwaway. **Caption quality is the single highest-leverage variable in the entire system.** A day spent on the captioning prompt is worth a week spent on reranker tuning.

---

# PART II — DATA

## 4. The corpus (Phase 0)

### 4.1 Why this phase is unavoidable

The briefing's critical finding stands: no public dataset links manufacturing video segments to maintenance reports and manuals. LoVR, GEM, FORGE and InspecSafe each cover one slice; none provides the connective layer. That layer is the project.

### 4.2 [HARD CAP] Corpus scope

| Asset | Target | Hard cap | Notes |
|---|---|---|---|
| Videos | 20–25 | **25 videos** | 2–15 min each; longer is better for the temporal-grounding story |
| Total video duration | 3–5 hours | 6 hours | |
| Video segments (derived) | 1,500–3,000 | — | auto-generated, not hand-made |
| Human-verified segments | 150–250 | — | ~10 per video; the ones referenced by ground truth |
| Still images | 200–400 | 500 | frames extracted + any separate photos |
| Maintenance reports | 25–40 | 50 | one or two per video, 200–600 words |
| Manual / SOP excerpts | 15–30 | 40 | 1–5 pages each |
| Eval queries | 120–180 | — | see §13.2 for the composition |

**Time cap: 2 weeks wall-clock. On day 14 Phase 0 ends regardless of completeness, and Phase 1 starts with whatever exists.** This is the single biggest controllable risk in the project.

### 4.3 Sourcing strategy

Ranked by preference:

1. **Self-filmed** — a university machine shop, lab equipment, a 3D printer farm, an HVAC plant room. Phone video is fine. This has zero licensing risk and gives full control over what's depicted. Budget one afternoon for a shoot that yields 8–12 videos.
2. **Explicitly open-licensed industrial footage** — CC0/CC-BY from Pexels, Pixabay, Wikimedia Commons, and manufacturer channels that publish under permissive terms. Record the license per asset in `assets.license`.
3. **Publicly available maintenance/inspection footage used privately** — permitted for a private, non-distributed corpus, but every such asset is flagged `redistributable = false` and the corpus can then never be published. Keep these under 40% of the corpus so a redistributable subset always exists.

For **manuals and reports**: real equipment manuals are widely available as PDFs from manufacturers. Reports must be **written by us** (no public source exists that matches our footage) — this is the "self-authored ground truth" limitation named in the briefing's risk table, and it is disclosed in every write-up rather than hidden.

### 4.4 Domain scoping

Pick **three equipment families** and stay inside them. Suggested: *hydraulic/pneumatic systems*, *rotating machinery (pumps, motors, bearings)*, *CNC / machining*. Three families is enough to make cross-document retrieval non-trivial and few enough that terminology stays consistent — which matters because BM25 and embedding retrieval both degrade when the corpus is a semantic grab-bag.

### 4.5 Data model

```sql
-- ============ core assets ============
CREATE TABLE assets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind            TEXT NOT NULL CHECK (kind IN ('video','image','document')),
  title           TEXT NOT NULL,
  source_uri      TEXT,                 -- original URL or 'self-filmed'
  storage_key     TEXT NOT NULL,        -- object-store key
  license         TEXT NOT NULL,        -- 'CC0','CC-BY-4.0','self','private-use'
  redistributable BOOLEAN NOT NULL DEFAULT false,
  equipment_family TEXT,                -- 'hydraulic','rotating','cnc'
  duration_s      REAL,                 -- video only
  width           INT, height INT, fps  REAL,
  page_count      INT,                  -- document only
  checksum_sha256 TEXT NOT NULL,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta            JSONB NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX ON assets (checksum_sha256);

-- ============ video segments ============
CREATE TABLE segments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  idx             INT NOT NULL,          -- ordinal within the video
  start_s         REAL NOT NULL,
  end_s           REAL NOT NULL,
  method          TEXT NOT NULL,         -- 'shot','fixed-30s','merged','manual'
  keyframe_key    TEXT,                  -- object-store key of representative frame
  caption         TEXT,                  -- VLM-generated, the retrieval payload
  caption_model   TEXT,
  caption_prompt_v TEXT,                 -- prompt version, e.g. 'cap-v3'
  transcript      TEXT,                  -- ASR for this span, may be null/empty
  human_verified  BOOLEAN NOT NULL DEFAULT false,
  human_caption   TEXT,                  -- overrides caption when present
  CONSTRAINT span_valid CHECK (end_s > start_s)
);
CREATE INDEX ON segments (asset_id, start_s);

-- ============ document chunks ============
CREATE TABLE chunks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  idx             INT NOT NULL,
  doc_type        TEXT NOT NULL CHECK (doc_type IN ('manual','sop','report')),
  section_path    TEXT,                  -- '4.2 > Hydraulic Pump > Inspection'
  page_from       INT, page_to INT,
  text            TEXT NOT NULL,
  token_count     INT NOT NULL,
  tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX ON chunks USING GIN (tsv);
CREATE INDEX ON chunks (asset_id, idx);

-- ============ images ============
CREATE TABLE images (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        UUID REFERENCES assets(id) ON DELETE CASCADE,
  segment_id      UUID REFERENCES segments(id) ON DELETE SET NULL, -- if frame-derived
  storage_key     TEXT NOT NULL,
  caption         TEXT,
  ocr_text        TEXT,
  source          TEXT NOT NULL CHECK (source IN ('frame','standalone'))
);

-- ============ THE CONNECTIVE LAYER — the actual contribution ============
CREATE TABLE evidence_links (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  segment_id      UUID REFERENCES segments(id) ON DELETE CASCADE,
  chunk_id        UUID REFERENCES chunks(id) ON DELETE CASCADE,
  image_id        UUID REFERENCES images(id) ON DELETE CASCADE,
  relation        TEXT NOT NULL,   -- 'documents','specifies','depicts','contradicts'
  confidence      REAL NOT NULL DEFAULT 1.0,
  author          TEXT NOT NULL,   -- 'human' | 'llm-proposed'
  note            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(segment_id, chunk_id, image_id) >= 2)
);

-- ============ vectors (one table per space, all pgvector) ============
CREATE TABLE vec_segment_text  (segment_id UUID PRIMARY KEY REFERENCES segments(id) ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1024) NOT NULL);
CREATE TABLE vec_segment_visual(segment_id UUID PRIMARY KEY REFERENCES segments(id) ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1152) NOT NULL);
CREATE TABLE vec_chunk         (chunk_id   UUID PRIMARY KEY REFERENCES chunks(id)   ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1024) NOT NULL);
CREATE TABLE vec_image         (image_id   UUID PRIMARY KEY REFERENCES images(id)   ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1152) NOT NULL);

CREATE INDEX ON vec_segment_text   USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX ON vec_segment_visual USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX ON vec_chunk          USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX ON vec_image          USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

-- ============ evaluation ============
CREATE TABLE eval_queries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  text          TEXT NOT NULL,
  query_type    TEXT NOT NULL,  -- 'video-only','doc-only','multi-hop','visual','unanswerable'
  difficulty    TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
  split         TEXT NOT NULL CHECK (split IN ('dev','test')),
  author        TEXT NOT NULL,
  reference_answer TEXT
);

CREATE TABLE eval_gold (            -- ground-truth evidence for a query
  query_id      UUID NOT NULL REFERENCES eval_queries(id) ON DELETE CASCADE,
  segment_id    UUID REFERENCES segments(id),
  chunk_id      UUID REFERENCES chunks(id),
  image_id      UUID REFERENCES images(id),
  gold_start_s  REAL, gold_end_s REAL,   -- human-marked true span, for IoU
  grade         SMALLINT NOT NULL DEFAULT 2 CHECK (grade IN (1,2)) -- 2=essential,1=helpful
);

CREATE TABLE eval_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_name   TEXT NOT NULL,     -- one of the ablation config ids in §13.5: 'A0'…'A10'
  git_sha       TEXT NOT NULL,
  params        JSONB NOT NULL,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  metrics       JSONB
);

CREATE TABLE eval_results (
  run_id        UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  query_id      UUID NOT NULL REFERENCES eval_queries(id),
  retrieved     JSONB NOT NULL,    -- ranked evidence ids + scores
  answer        TEXT,
  judge         JSONB,             -- faithfulness, correctness, citation scores + rationale
  latency_ms    INT
);
```

### 4.6 Annotation protocol

Annotation is the expensive part; the protocol exists to stop it sprawling.

**Step 1 — auto-first.** Never annotate from scratch. The pipeline generates segments and captions; a human only *corrects*. Correcting a caption takes ~20 seconds; writing one takes ~2 minutes.

**Step 2 — annotate only what ground truth touches.** Of ~2,000 segments, only the ~200 that appear in `eval_gold` need `human_verified = true`. The rest stay machine-captioned. This is honest as long as it's stated: retrieval operates over machine captions, which is exactly how the system would work in production.

**Step 3 — the linking pass is the real work.** For each video, a human writes one maintenance report (200–600 words) that describes what actually happens at specific timestamps, then links report paragraphs to segments via `evidence_links`. A manual excerpt is then attached that *specifies* what the report *observes* — e.g. report says "pressure reading 180 bar", manual section says "operating range 150–200 bar". That gap between observed and specified is what makes multi-hop queries meaningful.

**Step 4 — adversarial padding.** Deliberately include near-duplicate content: two different hydraulic pumps, two inspections of the same machine on different dates, a manual section for a *similar but different* model number. Without distractors, Recall@5 on a 25-video corpus is trivially ~100% and the metrics mean nothing.

**Step 5 — inter-annotator check.** If two people work on this, have both independently mark gold spans for 20 queries. Report span-level IoU agreement. If human-to-human IoU is 0.6, the system's 0.4 target reads very differently — and that context belongs in the write-up.

### 4.7 Ground-truth circularity — stated plainly

The person who writes the reports also writes the queries and marks the gold spans. That is circular, and it inflates every number. Mitigations, all of which are cheap:

- **Author separation** where headcount allows: person A builds the corpus, person B writes eval queries without having seen the reports.
- **Time separation** where it doesn't: write queries at least 3 days after the corpus, from the video list alone, before re-reading the reports.
- **Query paraphrase test**: every test-split query gets one paraphrase written by a different person (or a different LLM with a "rewrite as a shop-floor technician would ask it" prompt). Report metrics on both. A large gap = the system is fitting the author's phrasing, not the semantics.
- **Disclose it in every artifact.** README, report, demo script, slide deck. The briefing already commits to this.

---

## 5. External datasets — role and handling

Each public dataset has exactly one job. None is a source of the linked corpus.

| Dataset | Verified | Job in this project | Concretely, we do |
|---|---|---|---|
| **LoVR** (arXiv 2505.13928) | Yes — 467 long videos, 40,804 captioned clips | Methodology reference for long-video and clip-level retrieval; optional external sanity benchmark | Read the paper, mirror its segmentation granularity and caption style. **Optionally** run our Phase 1–2 retriever on a 200-clip LoVR subset to get one externally-comparable number. |
| **GEM (GEM-V / GEM-I)** (2021, Microsoft/ACL) | Yes — 1.2M query-image-title, 99K query-video-title | Generic retrieval baseline only | Use *only* if we want a "does our retriever behave sanely on generic web content" smoke test. Low priority. Explicitly **not** manufacturing data. |
| **FORGE** (arXiv 2604.07413) | Yes — ~12k samples, 2D images + 3D point clouds, fine-grained part labels | Domain-generalisation check for the **image** encoder | Run our image encoder zero-shot on a FORGE subset, report retrieval accuracy on workpiece/part queries. Answers "does our image path understand industrial parts, or only generic objects?" **Not** a source of video/reports/manuals. |
| **InspecSafe-V1** (arXiv 2601.21173) | Yes — 41 robots, 2,239 sites, 5,013 instances, incl. infrared/audio/depth | Domain-generalisation + safety reference | Optional Phase 3 stretch: check whether our segment retriever transfers to genuinely industrial inspection footage. Its extra modalities (IR, radar, audio) are **out of scope**. |
| **MELON** | **No — unverifiable, treated as a fabricated citation** | None | Dropped entirely. Do not re-introduce. If anyone cites it, ask for the arXiv ID. |
| **MomentSeeker** | Yes | Literature anchor for temporal/moment retrieval | Adopt its task formulation and metric definitions (IoU thresholds, R@1/IoU=0.5 style reporting) so our numbers are at least *comparable in form* to published work. |

**A standing rule:** before any dataset, model, or paper enters the build, someone opens the arXiv/HuggingFace page and confirms it exists with the claimed contents. The MELON finding is why. Add a one-line entry to `docs/verified-sources.md` with the URL and date checked.

**Licensing:** check each dataset's terms before download. Several benchmark datasets are research-use-only. Since we neither train nor redistribute, research use is almost certainly fine — but record the terms in `docs/licenses.md`.

---

# PART III — THE PIPELINE

## 6. Ingestion pipeline

The ingestion DAG is idempotent and resumable at every stage. Every stage writes its output to the DB and marks a `stage_status` row; re-running skips completed stages unless `--force`. This matters more than it sounds: you will re-run captioning five times while tuning the prompt, and re-running shot detection each time wastes hours of GPU.

```
ingest(asset)
  │
  ├─ S0  probe          ffprobe → duration, fps, resolution, codec; checksum; dedupe
  ├─ S1  normalize      ffmpeg → H.264 720p 30fps MP4 + HLS renditions for the player
  ├─ S2  segment        PySceneDetect adaptive + min/max duration guards
  ├─ S3  keyframe       middle frame per segment + 3 sampled frames → object store
  ├─ S4  asr            faster-whisper (large-v3) → word-level timestamps → per-segment transcript
  ├─ S5  caption        VLM over 4–8 frames + ASR span → structured caption   ◀── highest leverage
  ├─ S6  embed-text     caption(+transcript) → text embedding → vec_segment_text
  ├─ S7  embed-visual   sampled frames → SigLIP 2 → mean-pool → vec_segment_visual
  ├─ S8  image-index    frames + standalone images → SigLIP 2 + caption + OCR → vec_image
  └─ S9  verify         invariants: no gaps, no overlaps, every segment has a vector
```

```
ingest(document)
  ├─ D0  probe          checksum, page count, born-digital vs scanned
  ├─ D1  extract        PyMuPDF text + layout; if scanned → OCR (§6.4)
  ├─ D2  structure      detect headings → build section_path tree
  ├─ D3  chunk          structure-aware, 300–500 tokens, 15% overlap, never split a table
  ├─ D4  embed          → vec_chunk;  tsvector generated automatically for BM25
  └─ D5  verify         every chunk has section_path, token_count in range, vector present
```

### 6.1 S2 — segmentation

Fixed-length windows are the wrong default for inspection footage, where a single camera holds on one component for 90 seconds and then cuts. Use **adaptive shot detection with duration guards**:

- `PySceneDetect` `AdaptiveDetector`, threshold 3.0 (tune on 3 videos)
- **Merge** adjacent shots shorter than `MIN_SEG = 8s`
- **Split** shots longer than `MAX_SEG = 45s` at ASR sentence boundaries; if no speech, split evenly
- Emit a **second, overlapping index** of fixed 30s windows with 50% stride (`method='fixed-30s'`)

Two indices sounds redundant; it isn't. Shot-based segments align with visual events; fixed windows align with *narration*, and the query "what problem was identified" is usually answered by speech that spans a shot boundary. Retrieval queries both and fuses. Cost is ~2x storage on vectors, which is negligible at this scale.

**Guard:** assert coverage — the union of shot segments must cover 100% of the video with no gaps, and overlaps only where intentional.

### 6.2 S5 — captioning (the critical stage)

Input: 4–8 uniformly-sampled frames from the segment (plus first and last frame always), the ASR transcript for that span, the video title, and the equipment family.

Output: **structured JSON**, not free prose:

```json
{
  "summary": "A technician removes the inspection cover from a hydraulic pump and checks the pressure gauge with a torch.",
  "equipment": ["hydraulic pump", "pressure gauge", "inspection cover"],
  "actions": ["removing cover", "visual inspection", "reading gauge"],
  "observations": ["gauge reads approximately 180 bar", "visible fluid residue near the housing seam"],
  "visual_details": ["yellow safety cage", "handheld torch", "blue overalls"],
  "text_in_frame": ["MAX 200 BAR"],
  "confidence": "high"
}
```

Then the embedded string is a **rendered** version of that JSON, not the JSON itself — a templated sentence that concatenates the fields in natural order. Structure earns its keep three ways: `equipment` and `text_in_frame` feed BM25 as exact-match handles; `observations` is what multi-hop queries actually target; and `confidence: low` segments can be down-weighted or flagged for human review.

The full prompt is Appendix C. It is versioned (`caption_prompt_v`), and **changing it invalidates every segment embedding** — the pipeline must detect a version mismatch and force re-embedding.

**Model choice.** Start with an API multimodal LLM for caption quality (this is the "hybrid" decision from §7). If cost becomes a problem: captioning 2,500 segments at ~6 frames each is a one-time batch, run overnight, with a re-run every time the prompt changes. Budget for 5–8 full re-runs. Cache aggressively on `(segment_checksum, prompt_version, model)`.

### 6.3 S4 — ASR

`faster-whisper` `large-v3`, `word_timestamps=True`, VAD filter on. Industrial footage is noisy; expect WER to be poor on shop-floor audio and *do not* rely on ASR alone. Store the transcript with per-word timings so segment boundaries can snap to sentence ends. Empty transcript is a normal, expected case — the caption path must work without speech.

### 6.4 D1 — document extraction

Manuals are the messiest input. Order of attempts:

1. **Born-digital PDF** → PyMuPDF `get_text("dict")` preserving layout, reading order from block coordinates
2. **Scanned PDF** → check text-layer coverage; if < 100 chars/page, run OCR
3. **OCR** → `ocrmypdf` (Tesseract) as baseline; for dense multi-column engineering documents, a VLM page-to-markdown pass gives markedly better structure at higher cost. **[DECIDE]** Default: Tesseract first, VLM fallback for pages where Tesseract output fails a heuristic quality check (< 40% dictionary words).
4. **Tables** → `camelot` / `pdfplumber` for ruled tables; render as markdown inside the chunk, never split across chunks. Spec tables are exactly what multi-hop queries need.

### 6.5 D3 — chunking

Structure-aware, not naive fixed-size:

- Split on detected headings first; a section shorter than 500 tokens becomes one chunk
- Longer sections split at paragraph boundaries into 300–500 token chunks with 15% overlap
- **Every chunk is prefixed at embed time** (not in stored `text`) with its breadcrumb: `"[Hydraulic Systems > 4.2 Pump Inspection] <chunk text>"`. This single trick reliably improves retrieval on technical documents because chunks from the middle of a section otherwise lose all topical anchoring.
- Tables and figure captions stay intact; a table gets its section header plus the table
- Reports (short) are chunked by paragraph, since each paragraph typically maps to one timestamp

### 6.6 Idempotency and resumability

```sql
CREATE TABLE stage_status (
  asset_id   UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  stage      TEXT NOT NULL,
  status     TEXT NOT NULL CHECK (status IN ('pending','running','done','failed')),
  input_hash TEXT NOT NULL,   -- hash of (upstream outputs + stage config + model + prompt version)
  error      TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (asset_id, stage)
);
```

A stage re-runs iff `input_hash` changed or status ≠ `done`. `input_hash` includes the prompt version and model name — so bumping the caption prompt automatically invalidates S5→S6 for every asset, and nothing else. This is the mechanism that makes prompt iteration affordable.

---

## 7. Model stack

### 7.1 Decisions

| Role | Choice | Where it runs | Why |
|---|---|---|---|
| **Segment captioning** | API multimodal LLM (Claude / GPT-class) | API | Caption quality dominates end-to-end retrieval quality (§3.3). One-time batch cost. Structured-output reliability matters here and API models are ahead. |
| **Text embedding** (captions, chunks, queries) | Open model, self-hosted, 1024-dim — BGE-M3 or E5-family multilingual-large **[DECIDE: default BGE-M3]** | Local GPU | Free, fast, no per-query cost, well-understood on technical text. BGE-M3 additionally gives sparse + ColBERT vectors from one model if we want them later. |
| **Image / frame embedding** | SigLIP 2 SO400M (1152-dim) | Local GPU | Best open image-text model at this scale; strong on fine-grained visual detail. |
| **Direct video embedding** (secondary path) | SigLIP 2 over sampled frames, mean-pooled | Local GPU | Deliberately *not* InternVideo2 — see §3.3. A 6B model that underperforms a 150M one zero-shot is not worth 25s/video of GPU time. Revisit only if the caption path plateaus. |
| **ASR** | faster-whisper large-v3 | Local GPU | Standard, fast, word timestamps. |
| **Reranker** | LLM-based cross-modal reranker (API) + optional local cross-encoder baseline (BGE-reranker-v2-m3) | API + local | The briefing specifies LLM-based, not custom-trained. Keep a local cross-encoder as the cheap baseline so the ablation can show what the LLM reranker actually buys. |
| **Answer generation** | API multimodal LLM, streaming | API | Needs to reason over text + keyframes + timestamps and emit citations reliably. |
| **LLM-as-judge** | API LLM, **different family from the generator** | API | Using the same model to generate and judge inflates scores. Non-negotiable. |

### 7.2 The abstraction that keeps this changeable

Every model sits behind a Protocol. Model choice becomes config, not code:

```python
class TextEmbedder(Protocol):
    dim: int
    name: str
    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...

class ImageEmbedder(Protocol):
    dim: int
    name: str
    def embed_images(self, images: list[Image]) -> np.ndarray: ...
    def embed_text(self, texts: list[str]) -> np.ndarray: ...   # shared space

class Captioner(Protocol):
    def caption(self, frames: list[Image], transcript: str, ctx: SegmentContext) -> Caption: ...

class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Evidence], k: int) -> list[Evidence]: ...

class Generator(Protocol):
    def generate(self, query: str, evidence: list[Evidence]) -> AsyncIterator[GenerationChunk]: ...
```

The embedding **model name is stored on every vector row**. A mismatch between the configured model and the stored model is a startup error, not a silent wrong-answer bug. This is the most common way multimodal RAG systems break quietly.

### 7.3 Hardware

Minimum viable: one 16GB GPU (RTX 4080 / A4000 / a Colab or Lambda instance). SigLIP 2 SO400M and BGE-M3 co-resident fit comfortably; Whisper large-v3 needs ~5GB and can run sequentially. 24GB (3090/4090/A5000) removes all sequencing constraints. No GPU at all is workable but slow: SigLIP on CPU is ~20x slower, which turns a 2-hour ingest into two days.

**Cost envelope, one-time:** captioning ~2,500 segments and judging ~180 queries × 6 ablation configs is the bulk. Budget in the low hundreds of dollars for the whole project including 5–8 caption re-runs. Set a hard spend alarm and cache every LLM call keyed on input hash.

---

## 8. Retrieval architecture

### 8.1 Stages

```
query
  │
  ├─ 8.2 analysis        → intent, modality hints, expanded terms, filters
  │
  ├─ 8.3 candidate generation (parallel, 4 lanes)
  │     ├─ segment-text   : vector(caption) ∪ BM25(caption fields)   → top 50
  │     ├─ segment-visual : vector(frames)                            → top 30
  │     ├─ chunk          : vector(chunk) ∪ BM25(chunk)               → top 50
  │     └─ image          : vector(image) ∪ BM25(ocr+caption)         → top 30
  │
  ├─ 8.4 fusion          → reciprocal rank fusion across lanes         → top 30
  ├─ 8.5 link expansion  → pull evidence_links neighbours              → +N
  ├─ 8.6 rerank          → LLM cross-modal rerank                      → top 8
  ├─ 8.7 temporal refine → tighten the winning span                    → precise (start,end)
  └─ 8.8 generate        → grounded answer + citations (streaming)
```

### 8.2 Query analysis

One cheap LLM call (or a rule-based fallback for the ablation baseline) produces:

```json
{
  "intent": "find_and_explain",
  "modality_hints": ["video", "report"],
  "equipment": ["hydraulic pump"],
  "expanded_terms": ["hydraulic pump", "hydraulic system", "pump inspection", "fluid pressure"],
  "filters": {"equipment_family": "hydraulic"},
  "needs_temporal": true,
  "sub_queries": ["hydraulic pump inspection video", "hydraulic pump problem identified report"]
}
```

`sub_queries` matters: the canonical query is genuinely two retrievals, and issuing them separately materially beats issuing one blended query. `needs_temporal` gates stage 8.7.

**Ablation hook:** query analysis must be disableable (`--no-query-analysis`) so we can report what it contributes.

### 8.3 Hybrid lexical + dense

Every text lane runs both. Dense retrieval alone fails on exactly the queries manufacturing produces: model numbers (`P/N 4471-B`), spec values (`180 bar`), and acronyms. BM25 catches those; dense catches paraphrase. Neither is optional.

Postgres does both natively:

```sql
-- dense
SELECT s.id, 1 - (v.embedding <=> :qvec) AS score
FROM vec_segment_text v JOIN segments s ON s.id = v.segment_id
ORDER BY v.embedding <=> :qvec LIMIT 50;

-- lexical
SELECT c.id, ts_rank_cd(c.tsv, websearch_to_tsquery('english', :q)) AS score
FROM chunks c WHERE c.tsv @@ websearch_to_tsquery('english', :q)
ORDER BY score DESC LIMIT 50;
```

### 8.4 Fusion — RRF, not score blending

Scores from cosine similarity, BM25 and a rerank model live on incompatible scales; weighted score blending needs per-corpus tuning that a 25-video corpus cannot support without overfitting. **Reciprocal Rank Fusion** uses only ranks:

```
RRF(d) = Σ_lanes  w_lane / (k + rank_lane(d)),    k = 60
```

Default weights `w = 1.0` for every lane. Lane weights are config, exposed in the ablation grid, and **must not be tuned on the test split** (§13.6).

### 8.5 Link expansion — using the connective layer at query time

This is where the hand-built `evidence_links` earn their cost. After fusion, for each surviving segment, pull linked chunks and images and inject them at a discounted score (×0.7). A query that retrieves the right *video segment* then gets the right *report paragraph* for free, even if the report paragraph's own retrieval score was mediocre.

Guard against runaway expansion: max 2 neighbours per item, one hop only, capped at +10 items total.

**Ablation hook:** `--no-link-expansion`. This one is interesting to report — it quantifies the value of the connective layer, which is the project's actual contribution.

### 8.6 Reranking

Send the top ~30 candidates to an LLM in **one** call — batched, not one call per candidate. Each candidate is rendered compactly (segment: caption JSON + timestamp + video title; chunk: breadcrumb + text; image: caption + OCR). Keyframes are attached as images only for the top 10 candidates, to control token cost.

The reranker returns a relevance grade 0–3 per candidate plus a one-line rationale. Grades, not a ranking — grades are more stable across runs and give us a natural cutoff (drop everything below 2). The rationale is logged and shown in a debug panel; it is the single most useful artifact when diagnosing a bad answer.

**Fallback:** if the reranker call fails or times out (>8s), degrade to RRF order and flag the response `degraded: true`. Never fail the whole query on reranker failure.

### 8.7 Temporal refinement

Retrieval returns a segment (say 30s). The user wants the moment (say 6s). Coarse-to-fine:

1. Take the winning segment plus one neighbour on each side
2. Slide a 5s window with 1s stride across that span
3. Score each window by: caption-term overlap + ASR word-timestamp match for query terms + (optional) frame-level SigLIP similarity to the query
4. Return the argmax window, expanded to the nearest ASR sentence boundary, clamped to the segment ±5s

For queries where ASR contains the answer terms, word-timestamp matching alone is both accurate and free. Only fall back to frame scoring when the transcript is empty.

The UI seeks to `max(0, start - 2)` — two seconds of lead-in makes the jump feel correct to a human even when the boundary is exact.

### 8.8 Generation

The generator receives the query, up to 8 evidence items (each with a stable citation id), and the keyframes of any cited segments. Contract:

- Every factual claim carries a citation `[E3]`
- If evidence is insufficient, say so explicitly and name what's missing — **abstention is a success, not a failure**
- Never introduce equipment, values, or part numbers absent from the evidence
- When evidence conflicts, surface the conflict rather than picking one
- Timestamps are quoted from evidence metadata, never inferred

Full prompt in Appendix D. Response streams over SSE so first token lands fast; evidence panel renders immediately from the retrieval response, before generation completes.

### 8.9 Latency budget (p95, warm)

| Stage | Budget |
|---|---|
| Query analysis | 400 ms |
| Candidate generation (4 lanes, parallel) | 150 ms |
| Fusion + link expansion | 20 ms |
| Rerank (LLM) | 1,800 ms |
| Temporal refine | 200 ms |
| **Time to evidence panel** | **~2.5 s** |
| First generated token | +800 ms |
| Full answer | +3 s |
| **Time to complete answer** | **~6 s** |

Evidence renders at 2.5s, which is what makes the product feel responsive — the user starts reading citations while the answer streams.

---

# PART IV — SOFTWARE

## 9. Repository layout

Monorepo, two deployable apps, one shared eval harness.

```
mmi/
├── README.md
├── docker-compose.yml
├── docker-compose.gpu.yml
├── Makefile                          # make dev / ingest / eval / test
├── .env.example
├── docs/
│   ├── ENGINEERING_SPEC.md           # this file
│   ├── verified-sources.md           # every dataset/model/paper + date verified
│   ├── licenses.md
│   ├── decisions/                    # ADRs, one file per [DECIDE] resolved
│   └── eval-reports/                 # generated, committed
│
├── backend/
│   ├── pyproject.toml                # uv / poetry
│   ├── alembic/                      # migrations
│   ├── app/
│   │   ├── main.py                   # FastAPI app factory
│   │   ├── config.py                 # pydantic-settings, all env vars
│   │   ├── deps.py                   # DI: db session, model registry, stores
│   │   ├── api/
│   │   │   ├── routes_query.py
│   │   │   ├── routes_assets.py
│   │   │   ├── routes_ingest.py
│   │   │   ├── routes_eval.py
│   │   │   └── routes_health.py
│   │   ├── schemas/                  # Pydantic request/response models
│   │   │   ├── query.py  evidence.py  asset.py  ingest.py  eval.py
│   │   ├── models/                   # SQLAlchemy ORM
│   │   ├── retrieval/
│   │   │   ├── orchestrator.py       # the 8.1 pipeline
│   │   │   ├── analyzer.py           # 8.2
│   │   │   ├── lanes/                # segment_text, segment_visual, chunk, image
│   │   │   ├── fusion.py             # RRF
│   │   │   ├── expansion.py          # evidence_links hop
│   │   │   ├── rerank.py             # 8.6
│   │   │   └── temporal.py           # 8.7
│   │   ├── generation/
│   │   │   ├── generator.py
│   │   │   ├── prompts/              # versioned .md prompt files
│   │   │   └── citations.py          # parse + validate [E3] refs
│   │   ├── ingest/
│   │   │   ├── dag.py                # stage runner + stage_status
│   │   │   ├── stages/               # s0_probe.py … s9_verify.py, d0…d5
│   │   │   └── segmentation.py
│   │   ├── ml/
│   │   │   ├── registry.py           # model name → instance, dim checks
│   │   │   ├── text_embedder.py  image_embedder.py
│   │   │   ├── captioner.py  asr.py  llm.py
│   │   │   └── protocols.py          # §7.2
│   │   ├── stores/
│   │   │   ├── vector_store.py       # VectorStore protocol + pgvector impl
│   │   │   ├── blob.py               # S3/MinIO/disk
│   │   │   └── cache.py
│   │   └── core/                     # logging, errors, tracing, rate limit
│   └── tests/
│       ├── unit/  integration/  e2e/  fixtures/
│
├── eval/
│   ├── harness.py                    # run a config end-to-end
│   ├── metrics.py                    # recall@k, mrr, ndcg, iou — pure functions
│   ├── judge.py                      # LLM-as-judge + rubric
│   ├── ablation.py                   # the grid runner
│   ├── report.py                     # → markdown + charts
│   └── configs/*.yaml                # one per ablation cell
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx  App.tsx  router.tsx
│       ├── api/                      # generated client from OpenAPI
│       ├── features/
│       │   ├── search/               # SearchBar, ResultsList, AnswerStream
│       │   ├── evidence/             # EvidencePanel, EvidenceCard, CitationChip
│       │   ├── player/               # VideoPlayer, Timeline, SegmentMarkers
│       │   ├── corpus/               # AssetBrowser, SegmentInspector
│       │   └── debug/                # RetrievalTrace, ScoreBreakdown
│       ├── components/ui/            # shadcn
│       ├── hooks/                    # useQuery(TanStack), useSSE, usePlayerSync
│       └── lib/
└── scripts/
    ├── seed_corpus.py  annotate_cli.py  backfill_embeddings.py
```

---

## 10. Backend — FastAPI

### 10.1 Core schemas

```python
# schemas/evidence.py
from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID

class EvidenceBase(BaseModel):
    id: str                        # citation id: "E1", "E2" — stable within a response
    kind: Literal["segment", "chunk", "image"]
    asset_id: UUID
    asset_title: str
    score: float                   # post-fusion, pre-rerank
    rerank_grade: int | None = None    # 0-3
    rerank_rationale: str | None = None
    lanes: list[str]               # which lanes surfaced it — for the debug panel
    via_link: bool = False         # arrived through evidence_links expansion

class SegmentEvidence(EvidenceBase):
    kind: Literal["segment"] = "segment"
    segment_id: UUID
    start_s: float
    end_s: float
    refined_start_s: float | None = None   # after temporal refinement
    refined_end_s: float | None = None
    caption: str
    transcript: str | None
    keyframe_url: str
    playback_url: str              # HLS or MP4 with #t= fragment
    iou_hint: float | None = None  # populated only in eval mode

class ChunkEvidence(EvidenceBase):
    kind: Literal["chunk"] = "chunk"
    chunk_id: UUID
    doc_type: Literal["manual", "sop", "report"]
    section_path: str | None
    page_from: int | None
    page_to: int | None
    text: str
    highlight_spans: list[tuple[int, int]] = []

class ImageEvidence(EvidenceBase):
    kind: Literal["image"] = "image"
    image_id: UUID
    image_url: str
    caption: str | None
    ocr_text: str | None

Evidence = SegmentEvidence | ChunkEvidence | ImageEvidence
```

```python
# schemas/query.py
class QueryRequest(BaseModel):
    q: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(8, ge=1, le=20)
    modalities: list[Literal["video","image","document"]] | None = None
    filters: dict[str, str] | None = None        # e.g. {"equipment_family": "hydraulic"}
    config: str = "full"                         # ablation config name
    stream: bool = True
    include_trace: bool = False                  # debug panel payload

class Citation(BaseModel):
    evidence_id: str        # "E3"
    quote: str | None       # the exact supporting span, when extractable
    char_start: int         # position in the answer text
    char_end: int

class QueryResponse(BaseModel):
    query_id: UUID
    answer: str
    citations: list[Citation]
    evidence: list[Evidence]
    abstained: bool = False
    degraded: bool = False          # a stage failed and was bypassed
    latency_ms: dict[str, int]      # per-stage
    trace: RetrievalTrace | None = None
```

### 10.2 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/query` | The main endpoint. `stream=false` → `QueryResponse`. |
| `POST` | `/api/v1/query/stream` | SSE. Events: `evidence` (full evidence list, ~2.5s), `token` (answer deltas), `citation`, `done`, `error`. Evidence-first ordering is required. |
| `GET` | `/api/v1/assets` | Paginated corpus listing; filter by `kind`, `equipment_family`. |
| `GET` | `/api/v1/assets/{id}` | Asset detail + its segments/chunks. |
| `GET` | `/api/v1/assets/{id}/stream.m3u8` | HLS manifest (or signed MP4 URL). |
| `GET` | `/api/v1/segments/{id}` | Segment detail incl. caption JSON, transcript, neighbours. |
| `PATCH` | `/api/v1/segments/{id}` | Annotation: set `human_caption`, `human_verified`. |
| `GET` | `/api/v1/chunks/{id}` | Chunk detail + source page render URL. |
| `POST` | `/api/v1/links` | Create an `evidence_link` (annotation UI). |
| `POST` | `/api/v1/ingest` | Enqueue an asset. Returns `job_id`. |
| `GET` | `/api/v1/ingest/{job_id}` | Per-stage status, progress, errors. |
| `POST` | `/api/v1/ingest/{asset_id}/rerun` | `?stages=S5,S6&force=true` |
| `GET` | `/api/v1/eval/runs` · `/runs/{id}` | Eval run listing and detail. |
| `POST` | `/api/v1/eval/runs` | Trigger an ablation config. |
| `GET` | `/healthz` · `/readyz` | Liveness / readiness (readiness checks model dims vs DB). |

### 10.3 SSE contract

```
event: evidence
data: {"evidence": [...], "latency_ms": {"analysis": 380, "lanes": 140, "rerank": 1750}}

event: token
data: {"delta": "The hydraulic pump was inspected"}

event: citation
data: {"evidence_id": "E3", "char_start": 0, "char_end": 34}

event: done
data: {"query_id": "...", "abstained": false, "degraded": false}
```

Client renders the evidence panel on the first event. Citation events arrive as the generator emits `[E3]` markers, which the server strips from the token stream and converts into offsets — so the frontend never has to parse citation syntax out of streaming text.

### 10.4 Vector store abstraction

```python
class VectorStore(Protocol):
    async def upsert(self, space: str, ids: list[UUID], vecs: np.ndarray, model: str) -> None: ...
    async def search(self, space: str, vec: np.ndarray, k: int,
                     filters: dict | None = None) -> list[tuple[UUID, float]]: ...
    async def delete(self, space: str, ids: list[UUID]) -> None: ...
    async def assert_model(self, space: str, model: str, dim: int) -> None: ...
```

`assert_model` runs at startup for all four spaces and refuses to boot on mismatch. Swapping pgvector for Qdrant later means one new implementation, no call-site changes.

### 10.5 Error handling

- Every external call (LLM, embedder, blob store) wrapped with timeout + bounded retry (3 attempts, exponential backoff with jitter) + circuit breaker
- **Graceful degradation ladder:** reranker fails → RRF order, `degraded=true`. Query analyzer fails → raw query, `degraded=true`. Generator fails → return evidence with `answer=null` and a client-visible notice. A query returns *something* useful unless the DB is down.
- Structured JSON logs with `query_id` on every line; per-stage timings always logged even on success
- OpenTelemetry spans per stage. **[DECIDE]** Default: OTel to console in dev, Jaeger optional. Not required for the demo but makes latency work tractable.

### 10.6 Configuration

All config via `pydantic-settings`, no hardcoded values, `.env.example` complete and committed. Key groups: database, blob, redis, model names + dims + endpoints, API keys, retrieval params (`RRF_K`, lane weights, `TOP_K_*`), generation (model, temperature=0, max tokens), limits (rate limits, max query length, spend cap), feature flags (the ablation toggles).

---

## 11. Frontend — React

### 11.1 Stack

React 19 + TypeScript + Vite + TanStack Query + Tailwind + shadcn/ui + `hls.js` (or `video.js`) + `zustand` for player/selection state. Client generated from the FastAPI OpenAPI schema (`openapi-typescript` + `openapi-fetch`) so the API contract is enforced at compile time — if the backend changes a field, the frontend fails to build rather than failing at runtime in the demo.

### 11.2 Screens

**`/` — Search (the demo screen).** Three-pane:

```
┌────────────────────────────────────────────────────────────────────┐
│  [ Find the video where the hydraulic pump was inspected…    ] 🔍   │
│  modality: [video][image][doc]   family: [hydraulic ▾]   [debug ⚙] │
├──────────────────────────┬─────────────────────────────────────────┤
│  ANSWER (streaming)      │  EVIDENCE                               │
│                          │  ┌───────────────────────────────────┐  │
│  The hydraulic pump on   │  │ ▶ E1  VIDEO  pump-inspect-03.mp4  │  │
│  line 2 was inspected    │  │   02:14 – 02:41    grade 3        │  │
│  at 02:14 [E1]. The      │  │   [keyframe thumb] technician re… │  │
│  technician identified   │  └───────────────────────────────────┘  │
│  fluid seepage at the    │  ┌───────────────────────────────────┐  │
│  housing seam [E2],      │  │ 📄 E2  REPORT  MR-2026-014        │  │
│  which the manual        │  │   §Findings   grade 3             │  │
│  flags as a seal-        │  │   "…evidence of fluid seepage…"   │  │
│  replacement trigger     │  └───────────────────────────────────┘  │
│  [E3].                   │  ┌───────────────────────────────────┐  │
│                          │  │ 📘 E3  MANUAL  HP-400 §4.2        │  │
│  ⓘ 3 sources · 2.4s      │  │   "Any seepage at the housing…"   │  │
├──────────────────────────┴───┴───────────────────────────────────┴─┤
│  ▶ ━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━  02:16 / 08:32               │
│    ▓▓  segment markers · highlighted span 02:14–02:41              │
└────────────────────────────────────────────────────────────────────┘
```

Behaviours that matter for the demo:

- **Citation chips are the interaction.** Clicking `[E1]` in the answer scrolls the evidence panel to E1 *and*, if it's a segment, seeks the player. Hovering highlights both.
- **Player seeks to `start - 2s`** and shows a highlighted band on the timeline for the refined span. Seek must be < 300ms — that requires HLS with short segments, or MP4 with proper `moov` atom at the front (`ffmpeg -movflags +faststart`).
- **Evidence appears before the answer.** Non-negotiable — it's what makes the system feel like retrieval rather than a chatbot.
- **Abstention renders differently**: an amber panel saying what evidence was missing, not a normal answer. Demoing an honest abstention is more persuasive than demoing a confident answer.

**`/corpus` — Asset browser.** Grid of videos/docs/images, per-asset drill-in with the segment timeline, captions, transcript, and linked evidence. This is also the annotation surface: edit a caption, mark verified, draw a link.

**`/debug` (or the ⚙ overlay) — Retrieval trace.** Per-lane candidates with scores, RRF contributions, rerank grades and rationales, which items came via link expansion, per-stage latency. This is a development tool but it is also the *best* thing to show a technical reviewer, because it demonstrates the system is not a black box.

**`/eval` — Eval dashboard.** Run history, metric tables, the ablation matrix, per-query drill-in showing retrieved vs gold. Reads `eval_runs` / `eval_results`. Low priority; build it if Phase 6 has slack, otherwise the markdown report from `eval/report.py` suffices.

### 11.3 Player synchronisation

The one genuinely fiddly piece. State lives in a `zustand` store:

```ts
interface PlayerState {
  assetId: string | null
  currentTime: number
  activeEvidenceId: string | null
  highlightSpan: { start: number; end: number } | null
  seekTo: (t: number, evidenceId?: string) => void
}
```

`seekTo` is debounced (120ms) so rapid citation clicks don't thrash the media element. The player emits `timeupdate` at ~4Hz; when `currentTime` leaves `highlightSpan`, the active citation chip de-highlights. If the asset changes, the player unmounts and remounts keyed on `assetId` — trying to swap `src` on a live HLS instance is a reliable source of bugs.

### 11.4 Accessibility and robustness

Keyboard navigation through citations (`j`/`k`), `Space` play/pause, focus-visible everywhere, `prefers-reduced-motion` respected on the streaming text animation. Error boundaries around the player and the answer stream separately so a video failure doesn't blank the answer.

---

## 12. Infrastructure

### 12.1 Compose

```yaml
services:
  db:      # postgres:16 + pgvector; volume; healthcheck pg_isready
  redis:   # redis:7-alpine
  blob:    # minio; console on 9001
  api:     # build ./backend; depends_on healthy db/redis/blob; port 8000
  worker:  # same image, runs `arq app.ingest.worker.WorkerSettings`
           # gpu profile: deploy.resources.reservations.devices [gpu]
  web:     # build ./frontend; nginx serving dist; proxies /api → api:8000
```

Two compose files: `docker-compose.yml` (CPU, everything runs, slowly) and `docker-compose.gpu.yml` overlay. Model weights mount from a host volume so rebuilds don't re-download 4GB.

### 12.2 Storage and media

- Originals: `blob://originals/{asset_id}/{filename}` — never mutated
- Normalized: `blob://media/{asset_id}/720p.mp4` (faststart) + `blob://media/{asset_id}/hls/`
- Frames: `blob://frames/{segment_id}/{idx}.jpg` (640px long edge, q85)
- Thumbs: `blob://thumbs/{segment_id}.jpg` (320px)

Estimated total for 25 videos at ~5h: originals ~10–20GB, normalized ~4GB, frames ~1GB. A 100GB volume is comfortable.

### 12.3 CI

GitHub Actions, on every PR:

1. `ruff` + `mypy --strict` on `backend/app` and `eval`
2. `pytest tests/unit` (must be < 60s, no network, no GPU)
3. `pytest tests/integration` against a service-container Postgres with pgvector
4. `tsc --noEmit` + `eslint` + `vitest` on frontend
5. **Contract check**: regenerate the TS client from the live OpenAPI schema and fail if it differs from committed — catches silent API drift
6. **Golden retrieval test** (§14.4) on a 5-item fixture corpus, with fake embedders

Nightly (or on `main`): the full eval harness on the dev split, posting a metrics delta comment. This is how retrieval regressions get caught, and it is worth the half-day it costs to set up.


---

# PART V — PROVING IT WORKS

## 13. Evaluation

Evaluation is not the last phase. The eval set is built during Phase 0, the harness is built in Phase 1, and every phase from 1 onward reports numbers. A retrieval change that isn't measured didn't happen.

### 13.1 Splits

| Split | Size | Use |
|---|---|---|
| `dev` | ~60 queries | Every tuning decision, prompt iteration, weight choice. Look at it as much as you like. |
| `test` | ~90 queries | **Locked.** Run at the Phase 4 checkpoint, at Phase 6, and once at the end. Every run is logged. Never tuned against. |

The test split is written and then not read. If you find yourself opening the test file to see why a query failed, you have converted it into a dev split and must say so in the report.

### 13.2 Query composition

| Type | Count (test) | Shape | Primary metric |
|---|---|---|---|
| `video-only` | 20 | "Show me the segment where X is disassembled" | Segment Recall@k, IoU |
| `doc-only` | 15 | "What is the torque spec for the HP-400 mounting bolts?" | Chunk Recall@k |
| `multi-hop` | 30 | The canonical query — needs video **and** report/manual | Joint Recall, faithfulness |
| `visual` | 10 | "Find the video with the yellow safety cage" | Segment/image Recall@k |
| `unanswerable` | 10 | Plausible but not in the corpus | **Abstention rate** |
| `paraphrase` | 5 pairs | Rewrites of existing queries | Metric delta vs original |

The `unanswerable` set is the most underrated. A system that scores 0.8 on answerable queries and confidently hallucinates on all 10 unanswerable ones is worse than one scoring 0.7 that abstains correctly. **Report abstention as a headline metric, not a footnote.**

### 13.3 Retrieval metrics — exact definitions

Ambiguity here silently makes numbers incomparable, so they are pinned:

- **Recall@k** — fraction of queries for which ≥ 1 `grade=2` (essential) gold item appears in the top-k. Reported at k ∈ {1, 3, 5, 10}.
- **Full-set Recall@k** — fraction of queries where **all** essential gold items appear in top-k. This is the honest metric for multi-hop and will be much lower; report both.
- **MRR** — mean of `1/rank` of the first essential gold item; 0 if absent from top-20.
- **nDCG@10** — graded, using `grade` (2 = essential, 1 = helpful), standard log2 discount, ideal DCG from the gold set.
- **Temporal IoU** — for the top-1 retrieved segment of a video-grounded query:
  `IoU = |[p_s,p_e] ∩ [g_s,g_e]| / |[p_s,p_e] ∪ [g_s,g_e]|`
  using the **refined** span when temporal refinement is on, the raw segment span otherwise. Report mean IoU, and `R@1 | IoU≥0.3` and `R@1 | IoU≥0.5` (MomentSeeker-style), because mean IoU alone hides bimodal behaviour.
- **Lane attribution** — for each query, which lane first surfaced the winning item. Not a quality metric, but it is what tells you which lane to delete.

All implemented as **pure functions** in `eval/metrics.py` with unit tests against hand-worked examples. A metrics bug that inflates numbers is the worst failure mode in the project, because it's invisible.

### 13.4 Generation metrics — LLM-as-judge

Judge model is from a **different family** than the generator. Temperature 0. The judge sees: query, retrieved evidence, generated answer, reference answer (where one exists). It returns:

| Dimension | Scale | Definition |
|---|---|---|
| **Faithfulness** | 0–2 per claim, aggregated | Each atomic claim in the answer is `supported` / `partially supported` / `unsupported` by the provided evidence. Score = fraction fully supported. **This is the headline metric.** |
| **Correctness** | 0–3 | Against the reference answer, where one exists. |
| **Citation precision** | 0–1 | Fraction of citations that actually support the claim they're attached to. |
| **Citation recall** | 0–1 | Fraction of factual claims that carry any citation. |
| **Abstention appropriateness** | binary | Did it abstain when it should have, and answer when it could? |

**Judge validation is mandatory.** Before any judged number is reported: a human independently scores 30 answers; compute agreement (Cohen's κ or simple agreement rate) with the judge. If agreement < 0.7, the rubric gets rewritten and the judge re-run. Report the agreement number alongside every judged metric. An unvalidated LLM judge is a random number generator with good prose.

The rubric and judge prompt are Appendix E.

### 13.5 Ablation matrix

The briefing specifies `text-only → +image → +video → full`. Expanded into what's actually informative:

| # | Config | Lanes active | Extras | Question answered |
|---|---|---|---|---|
| A0 | `bm25-only` | chunk BM25 | — | The dumbest possible baseline. Publishable-honest floor. |
| A1 | `text-only` | chunk dense + BM25 | — | "Is this just RAG over PDFs?" |
| A2 | `+image` | A1 + image | — | What image retrieval adds |
| A3 | `+video-caption` | A2 + segment-text | — | The main event: caption-based video retrieval |
| A4 | `+video-visual` | A3 + segment-visual | — | Does the direct visual path add anything over captions? (§3.3's hypothesis under test) |
| A5 | `+links` | A4 | link expansion on | **The value of the hand-built connective layer** |
| A6 | `+rerank-local` | A5 | cross-encoder rerank | Cheap rerank baseline |
| A7 | `full` | A5 | LLM rerank + temporal refine + query analysis | The product |
| A8 | `full - query-analysis` | A5 | LLM rerank, no analyzer | What query analysis contributes |
| A9 | `oracle-evidence` | — | gold evidence injected | Generation quality, isolated |
| A10 | `adversarial` | A7 | + 2 injected distractors | Robustness / hallucination pressure |

Every config is a YAML file in `eval/configs/`. The runner executes all of them against a split and emits one markdown report with tables and a per-query diff against the previous run.

**A4 and A5 are the two results actually worth writing up.** A4 either validates or refutes the architecture's central bet. A5 quantifies the project's own contribution.

### 13.6 Statistical honesty

With ~90 test queries, a difference of 3 percentage points in Recall@5 is roughly 2–3 queries and means nothing. Rules:

- Report **95% bootstrap confidence intervals** (10,000 resamples) on every headline metric. It is two lines of code and it stops the whole class of overclaiming.
- Report `n` next to every number. Always.
- Compare configs with a **paired** test (bootstrap on per-query differences), never unpaired — same queries, same corpus.
- Never report a metric that was used for tuning as if it were held out.
- State the corpus size in the same sentence as any headline number. "Recall@5 of 0.74 (n=90 queries, 25-video corpus)" is honest; "Recall@5 of 0.74" is not.
- Run the full test eval **three times** with a fixed seed and report variance — LLM rerankers and judges are non-deterministic even at temperature 0.

### 13.7 External comparison (optional, high value)

If schedule allows, run the Phase 1–2 retriever unchanged on a ~200-clip LoVR subset and report the number next to LoVR's published baselines. This one number does more for credibility than any amount of self-reported metrics, because it is the only result in the project that isn't graded by its own authors. Budget one day.

---

## 14. Test plan

### 14.1 Layers

| Layer | Scope | Runtime | Runs |
|---|---|---|---|
| **Unit** | Pure logic: RRF, metrics, chunking, segment merging, citation parsing, span math | < 60s, no network | Every commit |
| **Integration** | DB + pgvector + stores with fake models | < 5 min | Every PR |
| **Contract** | OpenAPI schema ↔ generated TS client | seconds | Every PR |
| **Golden retrieval** | Fixed 5-asset fixture corpus, deterministic fake embedders, asserted rankings | < 30s | Every PR |
| **E2E** | Real stack, real (small) corpus, Playwright against the UI | ~5 min | Pre-merge to main, nightly |
| **Eval regression** | Full harness, dev split | ~20 min + LLM cost | Nightly on main |
| **Load** | k6/locust against `/query` | on demand | Before demo |

### 14.2 Unit tests worth writing (non-exhaustive but these specific ones catch real bugs)

**Segmentation** — merging two 4s shots produces one 8s segment; a 90s shot splits into ≤45s pieces at sentence boundaries; union of segments covers `[0, duration]` exactly; no segment has `end <= start`; fixed-window index has the expected count for a given duration and stride.

**Chunking** — a table is never split; every chunk has a `section_path`; overlap is within ±2 tokens of target; a 200-token section yields exactly one chunk; breadcrumb prefixing does not mutate stored `text`.

**RRF** — an item ranked 1 in one lane and absent elsewhere ranks above an item ranked 5 in two lanes with `k=60` (work the arithmetic by hand in the test); lane weight 0 removes a lane entirely; identical inputs give identical output order (stable sort).

**Metrics** — hand-worked fixtures: Recall@5 with the gold item at rank 5 is 1.0, at rank 6 is 0.0; MRR with first gold at rank 3 is 0.333…; IoU of `[10,20]` vs `[15,25]` is `5/15`; IoU of disjoint spans is 0; nDCG against a hand-computed ideal.

**Citation parsing** — `[E3]` in the token stream yields correct char offsets after marker stripping; a citation to a non-existent evidence id is rejected, not silently rendered; nested/malformed markers degrade safely.

**Temporal refinement** — a query term appearing at t=12.4s in the ASR yields a window containing 12.4; empty transcript falls through to frame scoring without raising; refined span is always within the segment ±5s.

### 14.3 Integration tests

Ingest a 30s fixture video end-to-end with fake models; assert stage_status rows, segment count, vectors present for every segment, no orphans. Re-run the same ingest and assert zero stages execute (idempotency). Bump the caption prompt version and assert exactly S5 and S6 re-run and nothing else — **this test is worth more than it looks**, because a broken invalidation chain produces stale embeddings that silently degrade every subsequent number.

Also: startup with a mismatched embedding model in config must raise, not boot.

### 14.4 The golden retrieval test

Five fixture assets, hand-built, with deterministic fake embedders (hash-based vectors, so "similar" text genuinely produces close vectors). Ten queries with hand-asserted expected top-3. Runs in 30 seconds with no GPU and no API key.

This test exists to catch the refactor that silently reorders results. It will fail legitimately when retrieval improves — that's fine, the fixture expectations get updated *deliberately*, in a commit whose message says why.

### 14.5 E2E (Playwright)

1. Type the canonical query → evidence panel populates within 5s → at least one segment evidence card present
2. Click citation `[E1]` → player seeks within 300ms → `currentTime` is within the highlighted span
3. Answer stream completes → every rendered citation chip maps to a visible evidence card
4. Unanswerable query → abstention UI renders, no confident answer
5. Reranker forced to fail (fault injection env var) → answer still returns, `degraded` indicator shows
6. Corpus browser → open an asset → segment list matches API

### 14.6 Manual QA checklist (pre-demo)

Run through this the day before any demo, on the demo machine, with the demo network:

- [ ] All 10 scripted demo queries return sensible answers (and you have watched each one)
- [ ] Every video plays; every seek lands correctly; no buffering stall over 1s
- [ ] Cold-start first query under 10s (warm the cache before demoing anyway)
- [ ] At least one abstention case in the demo script — show it deliberately
- [ ] Debug panel opens and is legible on a projector
- [ ] API keys valid, spend cap not hit, no rate-limit errors
- [ ] Offline fallback: recorded video of the demo exists, in case the network dies

---

## 15. Risks

Expanded from the briefing's table with concrete triggers and owners.

| Risk | Likelihood | Impact | Early warning sign | Mitigation |
|---|---|---|---|---|
| **Phase 0 scope creep** | High | High | Day 10 and the corpus is "nearly ready" | **[HARD CAP] 25 videos / 14 days.** On day 14, Phase 1 starts. Put the date in the calendar now. |
| **Caption quality is the bottleneck** | High | High | A3 ablation barely beats A1 | Budget 3 dedicated days for caption prompt iteration on 50 segments with human scoring before running S5 at full scale. Treat the prompt as code. |
| **Video licensing** | Medium | Medium | — | Corpus private by default; `redistributable` flag per asset; keep a ≥60% self-filmed/CC0 subset so a publishable version always exists. |
| **Small eval set → noisy, gameable metrics** | Certain | Medium | A config "wins" by 2pp | Bootstrap CIs on everything; paired tests; locked test split; three-run variance reporting (§13.6). |
| **Circular ground truth** | Certain | Medium | — | Author/time separation, paraphrase test, explicit disclosure in every artifact (§4.7). |
| **Domain shift from benchmarks** | Medium | Medium | Great LoVR numbers, poor own-corpus numbers | Never report a benchmark number as evidence the system works on our footage. Own-corpus eval from Phase 1 onward. |
| **Direct video embedding adds nothing** | Medium-High | Low | A4 ≈ A3 | This is a *result*, not a failure — report it. The architecture already treats captions as primary (§3.3). Cut the lane and save the GPU time. |
| **Generator hallucinates under bad retrieval** | Medium | High | A10 faithfulness ≪ A7 | Abstention instructions + citation validation; reject answers citing non-retrieved evidence at the API layer. |
| **LLM API cost overrun** | Medium | Medium | Spend alarm | Hard spend cap in config; cache every call on input hash; local cross-encoder fallback for rerank. |
| **Embedding model / stored vector mismatch** | Medium | High (silent) | Numbers degrade with no code change | `assert_model` at startup; model name on every vector row; `input_hash` includes model + prompt version. |
| **GPU unavailable at a critical moment** | Medium | Medium | — | All models have CPU paths; pre-compute and commit embeddings for the demo corpus so a demo never needs a GPU. |
| **Two-week slip in Phase 0 cascades** | Medium | High | — | Phases 1 and 4 (document RAG) do not depend on video corpus completeness and can start in parallel with 10 videos. |

---

## 16. Roadmap

Sequenced for a solo builder at focused pace. With two people, Phase 0 and Phase 4 run in parallel and total drops to roughly 8–9 weeks.

### Phase 0 — Linked corpus · 2–3 weeks · **[HARD CAP] 14 days**

Source 20–25 videos; source manuals; write reports; run the ingestion pipeline (built minimally in parallel); human-verify ~200 segments; build ~150 eval queries with gold links; write the annotation CLI/UI.

**Exit gate (all must be true):**
- ≥ 20 videos ingested, segmented, captioned, embedded
- ≥ 25 documents chunked and indexed
- ≥ 100 `evidence_links` created by a human
- ≥ 120 eval queries with gold, split dev/test, test split committed and closed
- `docs/licenses.md` complete for every asset

### Phase 1 — Whole-video retrieval baseline · 1 week

Caption-based segment-text lane; text embedder; pgvector HNSW; eval harness + metrics module with unit tests; first Recall@k numbers on dev.

**Exit gate:** Recall@5 ≥ 0.6 on `video-only` dev queries at whole-video granularity; eval harness runs from one command and emits a markdown report; metrics functions unit-tested against hand-worked fixtures.

### Phase 2 — Temporal / segment retrieval · 1.5–2 weeks

Dual segment index (shot + fixed window); temporal refinement (§8.7); IoU metrics; MomentSeeker-style reporting.

**Exit gate:** mean IoU ≥ 0.4 and `R@1|IoU≥0.3` ≥ 0.5 on dev; segment-level Recall@5 ≥ 0.6; the UI can seek to a returned span (even with a placeholder frontend).

### Phase 3 — Image retrieval · 1 week

SigLIP 2 image lane over frames + standalone images; OCR; FORGE zero-shot generalization check.

**Exit gate:** `visual` dev queries Recall@5 ≥ 0.6; FORGE check run and its number recorded in the report, whatever it is.

### Phase 4 — Document / RAG index · 1 week

Structure-aware chunking; hybrid dense + BM25; breadcrumb prefixing; link expansion.

**Exit gate:** `doc-only` dev Recall@5 ≥ 0.8; hybrid beats dense-alone and BM25-alone on dev, with the delta reported.

> ### ⚑ Week-4/5 checkpoint (the briefing's gate)
> Before committing to fusion and generation, confirm retrieval works. If segment Recall@5 is below 0.5 and IoU below 0.3 on dev, **stop and fix retrieval** — do not proceed to Phase 5. The usual culprit is caption quality; the fix is prompt iteration, not more models.

### Phase 5 — Cross-modal fusion + generation · 1.5–2 weeks

RRF fusion; LLM reranker; generation prompt with citations and abstention; SSE streaming; citation validation.

**Exit gate:** end-to-end answers on dev with ≥ 0.8 faithfulness (judge, validated); abstention correct on ≥ 7/10 unanswerable dev queries; no answer ever cites non-retrieved evidence (enforced at the API layer, tested).

### Phase 6 — Evaluation & ablation · 1–1.5 weeks

All 11 ablation configs on dev; judge validation against human scores; **then** the locked test split, three runs; bootstrap CIs; final report.

**Exit gate:** the §1.4 definition-of-done numbers, reported with `n` and CIs; judge–human agreement ≥ 0.7 reported; `docs/eval-reports/final.md` committed.

### Phase 7 — Demo UI · 1 week

Search screen, evidence panel, player sync, corpus browser, debug trace panel; E2E tests; demo script.

**Exit gate:** the six E2E scenarios pass; manual QA checklist clean; 10-query demo script rehearsed end to end.

### Suggested parallelisation (2 people)

```
Week:      1    2    3    4    5    6    7    8    9
Person A:  [── Phase 0 corpus ──][─ P2 temporal ─][─ P5 fusion ─][P6 eval]
Person B:  [ingest pipeline][P4 docs][P1 video][P3 img][── P7 UI ──][P6 eval]
                                     ▲ week-4 checkpoint
```

---

## 17. Cost and resource summary

| Item | Estimate |
|---|---|
| GPU | 1 × 16–24GB, ~40 GPU-hours total across all ingest runs |
| LLM API — captioning | ~2,500 segments × 6 frames × ~6 runs |
| LLM API — reranking | ~180 queries × 11 configs × 3 runs |
| LLM API — generation | ~180 queries × 6 generative configs × 3 runs |
| LLM API — judging | ~3,000 judgments |
| **Total API spend** | **Low hundreds of USD** with caching. Set a hard cap and alarm. |
| Storage | ~40GB |
| Human time | 10–13 focused weeks solo, ~8–9 with two people |

---

## 18. Definition-of-done checklist

- [ ] 20–25 videos, 25–40 reports, 15–30 manual excerpts ingested and indexed
- [ ] ≥ 100 human-authored evidence links
- [ ] 120–180 eval queries, dev/test split, test split never tuned on
- [ ] All 11 ablation configs run on the test split, three times, with CIs
- [ ] Judge validated against human scores, κ/agreement reported
- [ ] §1.4 target numbers met or the gap honestly explained
- [ ] UI does the full loop under 5s p95
- [ ] E2E suite green; golden retrieval test green; CI green
- [ ] `docs/eval-reports/final.md` with caveats section written before the results section
- [ ] README states corpus size, circularity limitation, and what the system does *not* do
- [ ] Demo script rehearsed, fallback recording made

---

## 19. Open decisions

Record the resolution as an ADR in `docs/decisions/` when each is settled.

| # | Decision | Default | Resolve by |
|---|---|---|---|
| D1 | Job queue: arq vs Celery | arq | Phase 0 |
| D2 | Text embedder: BGE-M3 vs E5-large | BGE-M3 | Phase 1 |
| D3 | OCR: Tesseract-first vs VLM-first | Tesseract with VLM fallback | Phase 4 |
| D4 | Keep or cut the direct visual video lane | Keep until A4 says otherwise | Phase 6 |
| D5 | Vector store: stay on pgvector vs move to Qdrant | Stay | Only if > 500k vectors |
| D6 | Build the `/eval` dashboard UI | Only if Phase 6 has slack | Phase 6 |
| D7 | Run the LoVR external comparison | Yes if ≥ 1 day of slack | Phase 6 |
| D8 | Observability: OTel/Jaeger vs logs only | Structured logs + OTel-to-console | Phase 5 |

---

## Appendix A — Environment variables

```bash
# --- database / infra ---
DATABASE_URL=postgresql+asyncpg://mmi:mmi@db:5432/mmi
REDIS_URL=redis://cache:6379/0
BLOB_ENDPOINT=http://blob:9000
BLOB_BUCKET=mmi
BLOB_ACCESS_KEY=...
BLOB_SECRET_KEY=...

# --- models (name + dim are validated against stored vectors at startup) ---
TEXT_EMBED_MODEL=BAAI/bge-m3
TEXT_EMBED_DIM=1024
IMAGE_EMBED_MODEL=google/siglip2-so400m-patch14-384
IMAGE_EMBED_DIM=1152
ASR_MODEL=large-v3
CAPTION_MODEL=<api-multimodal-model>
CAPTION_PROMPT_VERSION=cap-v3
RERANK_MODEL=<api-llm>
RERANK_LOCAL_MODEL=BAAI/bge-reranker-v2-m3
GENERATION_MODEL=<api-multimodal-model>
JUDGE_MODEL=<different-family-api-llm>

# --- retrieval ---
RRF_K=60
LANE_WEIGHTS='{"segment_text":1.0,"segment_visual":1.0,"chunk":1.0,"image":1.0}'
TOP_K_SEGMENT_TEXT=50
TOP_K_SEGMENT_VISUAL=30
TOP_K_CHUNK=50
TOP_K_IMAGE=30
TOP_K_AFTER_FUSION=30
TOP_K_FINAL=8
LINK_EXPANSION_ENABLED=true
LINK_EXPANSION_DISCOUNT=0.7
LINK_EXPANSION_MAX=10

# --- segmentation ---
MIN_SEGMENT_S=8
MAX_SEGMENT_S=45
FIXED_WINDOW_S=30
FIXED_WINDOW_STRIDE_S=15
SCENE_THRESHOLD=3.0

# --- generation ---
GENERATION_TEMPERATURE=0
GENERATION_MAX_TOKENS=800
ABSTAIN_THRESHOLD=1            # min rerank grade required to answer at all

# --- limits ---
LLM_SPEND_CAP_USD=250
RATE_LIMIT_PER_MIN=30
RERANK_TIMEOUT_S=8

# --- feature flags (ablation) ---
FF_QUERY_ANALYSIS=true
FF_RERANK=llm                  # llm | local | off
FF_TEMPORAL_REFINE=true
FF_SEGMENT_VISUAL_LANE=true
```

## Appendix B — Makefile targets

```
make dev            # compose up, migrate, seed fixture corpus
make ingest FILE=…  # ingest one asset
make ingest-all     # ingest everything in data/incoming
make rerun STAGE=S5 # force re-run a stage across all assets
make eval CONFIG=full SPLIT=dev
make ablation SPLIT=dev         # all configs, one report
make ablation-test              # locked split; prompts for confirmation
make test           # unit + integration
make e2e            # playwright
make report         # regenerate docs/eval-reports/
```

## Appendix C — Segment captioning prompt (v3, sketch)

```
You are annotating a segment of a manufacturing/maintenance video for a technical
search system. Technicians will search this index with natural language.

CONTEXT
  Video title: {title}
  Equipment family: {family}
  Segment: {start_s:.1f}s – {end_s:.1f}s of {duration_s:.1f}s
  Speech transcript for this span: {transcript or "(no speech)"}
  Frames: {n} frames sampled uniformly, first and last included.

TASK
  Return JSON only, matching this schema exactly:
  { "summary": str,            # 1-2 sentences, what happens, plainly
    "equipment": [str],        # named components visible or discussed
    "actions": [str],          # what is being done, gerund form
    "observations": [str],     # findings, readings, visible conditions, faults
    "visual_details": [str],   # distinctive visual features a searcher might recall
    "text_in_frame": [str],    # verbatim labels, gauges, part numbers, warnings
    "confidence": "high"|"medium"|"low" }

RULES
  - Describe only what is visible or stated. Never infer a fault that is not shown.
  - Use the specific component name when identifiable ("hydraulic pump"), the
    generic one when not ("cylindrical housing"). Never guess a model number.
  - Transcribe text_in_frame verbatim, including units. This is exact-match search bait.
  - observations[] is the highest-value field: gauge readings, leaks, wear, damage,
    alignment, anything a maintenance report would record.
  - If the segment is a transition, title card, or shows nothing identifiable,
    return confidence "low" and a minimal summary. Do not invent content.
  - Prefer the transcript for facts stated aloud; prefer the frames for what is shown.
    If they conflict, report both in observations[].
```

Iterate this on 50 hand-scored segments before running it across the corpus. Bump the version on every change; the pipeline invalidates S5→S6 automatically.

## Appendix D — Generation prompt (sketch)

```
Answer the technician's question using ONLY the evidence provided.

EVIDENCE
{for each: [E{n}] kind, source title, (timestamp | section path | page), content}

QUESTION
{query}

RULES
 1. Every factual claim must carry a citation like [E2]. Claims without evidence
    do not belong in the answer.
 2. If the evidence does not answer the question, say so explicitly and state what
    is missing. Abstaining is correct behaviour, not failure.
 3. Never introduce equipment names, part numbers, or measurements that do not
    appear in the evidence.
 4. When evidence conflicts, present the conflict; do not silently choose.
 5. Quote timestamps exactly as given in the evidence metadata. Never estimate one.
 6. Lead with the direct answer, then the supporting detail. Two to five sentences
    unless the question demands more.
 7. When a video segment is the primary evidence, name the video and the timestamp
    in the first sentence.
```

## Appendix E — Judge rubric (sketch)

```
You are evaluating an answer produced by a retrieval-augmented system.
You are NOT evaluating whether the answer is true in the world — only whether it is
supported by the evidence shown. An answer may be factually correct and still
score 0 on faithfulness if the evidence does not support it.

INPUT: question, evidence list, generated answer, reference answer (may be absent)

STEP 1 — Decompose the answer into atomic factual claims. List them.
STEP 2 — For each claim, mark SUPPORTED / PARTIAL / UNSUPPORTED against the evidence,
         naming the evidence id that supports it (or "none").
STEP 3 — Check each citation in the answer: does the cited evidence actually support
         the claim it is attached to? Count correct vs incorrect citations.
STEP 4 — If a reference answer is present, score correctness 0-3.
STEP 5 — If the question is unanswerable from the evidence, score abstention
         appropriateness: 1 if the answer declined and said what was missing, else 0.

Return JSON:
{ "claims": [{"text":…, "verdict":…, "evidence_id":…}],
  "faithfulness": float,          # supported / total claims
  "citation_precision": float,
  "citation_recall": float,
  "correctness": int|null,
  "abstention_appropriate": bool|null,
  "rationale": str }
```

Validate against 30 human-scored answers before trusting any number this produces.

## Appendix F — Glossary

| Term | Meaning here |
|---|---|
| **Segment** | A contiguous span of one video, the unit of video retrieval |
| **Chunk** | A contiguous span of one document, the unit of text retrieval |
| **Evidence** | Any retrieved item (segment, chunk, or image) presented to the generator or the user |
| **Evidence link** | A human-authored relation between two evidence items — the project's core contribution |
| **Lane** | One independent candidate-generation path (segment-text, segment-visual, chunk, image) |
| **RRF** | Reciprocal Rank Fusion — combining ranked lists by rank rather than by score |
| **Temporal refinement** | Narrowing a retrieved segment to the precise moment answering the query |
| **Gold** | Human-marked correct evidence for an eval query |
| **Grade** | Relevance level of a gold item: 2 = essential, 1 = helpful |
| **Oracle config** | Eval run where ground-truth evidence bypasses retrieval, isolating generation |
| **Abstention** | The system declining to answer when evidence is insufficient — a success state |

---

## Appendix G — Sources consulted

Dataset verification status is carried forward from the project briefing. The architectural claim in §3.3 about video embedding model performance draws on:

- Mixpeek, *Video Embedding Benchmark 2026: Gemini vs Marengo vs X-CLIP vs SigLIP vs InternVideo2* — https://mixpeek.com/blog/video-embedding-benchmark-2026 (vendor-published; 20 videos / 60 queries; local models handicapped by frame sampling; treat as directional only)
- *Natural-Language Temporal Grounding in Hour-Long Videos is a Search Problem* — https://arxiv.org/html/2606.12300v1
- *Awesome MLLMs for Video Temporal Grounding* (paper/code tracker) — https://github.com/ki-lw/Awesome-MLLMs-for-Video-Temporal-Grounding

Before Phase 1, re-verify every model and dataset named in this spec against its primary source and record the check in `docs/verified-sources.md`. The MELON finding in the briefing is the reason this rule exists.
