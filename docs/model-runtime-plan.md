# Model runtime and persistence plan

> Historical dependency note (2026-10-24), retained here as a dated environment finding:
> That audit found torch/transformers in system Python but not in the project venv or API
> container. Any recommendation below for hosted inference, paid APIs, or downloads is
> superseded by the 2026-11-26 zero-spend plan and is not authorized. The dated model-file
> inventory remains historical sizing evidence, not a required download list.

Prepared 2026-10-24 (Asia/Calcutta). **Proposal, not installation approval.**
The running status remains [build-status.md](build-status.md).

## Revised zero-spend plan (2026-11-26)

This section supersedes the paid caption-provider recommendation and all proposed
paid pilots/costs later in this document. The user's current hard constraint is **$0
spend**: no hosted inference, paid APIs, credits, or purchases. The user approved
local diagnostic acquisition and a <=3 interval pilot on 2026-11-26. That approval
does not include persistence, indexing, or paid services.

### Current runtime evidence

- Read-only check on 2026-11-26: Docker Compose reports `api`, `db`, and `redis` up
  and healthy; `/healthz` is `ok` and `/readyz` reports `ready`.
- The API container cannot connect to the configured BGE (`host.docker.internal:8001`)
  or SigLIP (`:8002`) endpoints (connection refused). Their search stages are therefore
  not presently available from the running API, despite `search_enabled=true`.
- The local Ollama endpoint lists only `llama3.2:3b` (about 2.02 GB); no model was
  loaded at inspection. This is available for text-only query analysis/reranking after
  code activation, but is not a video/image captioner.
- The workspace `.venv` is Python 3.12.4 and lacks `httpx`, `pytest`, `ruff`,
  `faster-whisper`, PyTorch, Transformers and OpenCV. The running API image is separate
  and healthy. `nvidia-smi` was unavailable in the inspection shell, so current GPU free
  memory is unknown; the previously measured laptop budget remains 6,141 MiB VRAM.
- The newly added AI routes and search paths have not been loaded by the running API:
  it was not restarted and is not configured for autoreload. All new feature flags are
  false by default.

### Proposed exact acquisition list (prepared, not approved)

All choices below are local-only and have **$0 model/API fees**. They still use network
bandwidth and local disk, so this is not download/install authorization.

| Stage | Package/model | Version or pinned identifier | Payload / constraints | Status |
|---|---|---|---|---|
| Captioning pilot | Ollama `qwen3-vl:2b-instruct-q4_K_M` | Ollama tag; 1.72B parameter Q4_K_M; Apache-2.0 | Ollama lists about **1.9 GB**; text+image input; needs Ollama >= 0.12.7. Local Ollama is **0.40.17**, so the version floor is already met. | Best first VLM candidate; industrial action-caption quality and 6 GB fit are untested. |
| ASR runtime | `faster-whisper==1.2.1` | PyPI release | Wheel **1.1 MB**; Python >=3.9. | Candidate for current Python 3.12.4 venv; not installed. |
| ASR runtime | `ctranslate2==4.9.1` | PyPI release | CPython 3.12 Windows x64 wheel **23.1 MB**. | Candidate CPU runtime; compatibility with this exact dependency set is untested. |
| ASR runtime deps | `av>=11`, `huggingface_hub>=0.23`, `tokenizers>=0.13,<1`, `onnxruntime>=1.14,<2`, `tqdm` | Requirements declared by faster-whisper | Resolved versions and wheel sizes still need an approved dry-run; do not install the unpinned ranges directly into the app environment. | Required package set; resolve in an isolated environment. |
| ASR weights | `Systran/faster-whisper-large-v3` | revision `edaa852ec7e145841d8ffdb056a99866b5f0a478` | **3,090,835,702 bytes** selected files (3.091 GB), MIT. CPU `int8`, word timestamps, one <=60s clip at a time. | Existing engineering-spec model; weights absent from the standard cache. CPU latency unmeasured. |
| Text embeddings (restore search) | `BAAI/bge-m3` | revision `5617a9f61b028005a4858fdac845db406aefb181` | **2,293,315,801 bytes** (2.293 GB), MIT. | Needed for live dense text queries; not needed for the isolated caption/ASR pilot. |
| Visual embeddings (restore search) | `google/siglip2-so400m-patch14-384` | revision `e8e487298228002f3d8a82e0cd5c8ea9c567f57f` | **4,582,795,867 bytes** (4.583 GB), Apache-2.0. | Needed for live visual queries; not needed for the isolated caption/ASR pilot. |

The proposed **diagnostic pilot** requires about **4.99 GB of model payload** (Qwen's
Ollama-reported ~1.9 GB plus the exact 3.091 GB Whisper files), plus Python wheels and
installation/cache overhead. The two known direct ASR wheels total about 24.2 MB; the
remaining transitive wheel sizes have not been resolved. Restoring both embedding services
adds **6.876 GB** of exact model files, bringing the full new model payload to about
**11.87 GB**. These totals exclude the already-present Llama 3.2 3B weights (about 2.02 GB),
package/container duplication, temporary download buffers, and caches. Actual free disk was
not established in this environment; check it before any acquisition. The previous 20 GB
allowance was a planning estimate for an earlier BGE-only stage, not a verified guarantee for
this larger set.

The Qwen3-VL pilot candidate is published in Ollama's model library and its registry
reports text/image input, an approximately 1.9 GB Q4_K_M package, and Apache-2.0 terms
([Ollama model tag](https://ollama.com/library/qwen3-vl%3A2b-instruct-q4_K_M)). Ollama's
model API supports `keep_alive: 0` to unload after a call ([Ollama chat API](https://docs.ollama.com/api/chat));
before activation, TRACE must set an explicit bounded context and unload behavior so the VLM,
existing Llama model, and embedding services are not left resident together. Model-file size
does not prove GPU memory fit. The existing `llava:7b` setting is only a placeholder and
should be changed to the selected tag only after approval and pilot review.

The faster-whisper project documents Python >=3.9, CPU `int8`, word-level timestamps, and
its package requirements ([official README](https://github.com/SYSTRAN/faster-whisper),
[PyPI 1.2.1](https://pypi.org/project/faster-whisper/1.2.1/)). Its GPU path additionally
requires CUDA/cuBLAS/cuDNN compatibility; the proposal uses CPU first to avoid competing for
6 GB VRAM. No performance estimate is made for CPU transcription.

### Proposed implementation sequence

1. **Approve the acquisition manifest.** User approval is needed for the named Qwen tag,
   pinned Whisper revision, package set, and exact transfer/install limits before anything is
   pulled. No hosted inference is in the plan.
2. **Run the diagnostic pilot.** After acquisition approval, run at most three short remote
   IndEgo intervals, using bounded in-memory frames/audio and no persistent output. If its
   results are poor or fit fails, stop and report rather than scale up.
3. **Restore current retrieval prerequisites separately.** BGE-M3 and SigLIP 2 are absent
   from the inspected standard cache; their launch scripts can download by default. Their
   packages/weights need their own approved setup and GPU compatibility check before endpoints
   are started. Confirm service health from inside the API container before claiming retrieval
   works.
4. **Keep inference sequential and bounded.** Process one segment at a time and sample at
   most eight frames from an interval no longer than 60 seconds. Run transcription and
   captioning sequentially; do not keep BGE, SigLIP, ASR, VLM, and Llama resident together on
   the 6 GB GPU. Measure peak GPU/RAM, latency, errors, and quality; stop on memory pressure.
5. **Review outputs before persistence.** Keep machine captions distinct from IndEgo human
   labels. Before indexing, prepare a migration/data contract with separate machine-caption
   provenance and word-timestamp fields; define which text is embedded and how it joins the
   existing corpus. Obtain explicit approval before any database migration, caption/ASR
   persistence, vector replacement/addition, or full-corpus indexing.
6. **Evaluate before changing claims.** After persistence is approved, run a bounded dev
   comparison against the current search path; do not change the locked test split. Report
   caption/ASR failure rates, retrieval metrics, latency, hardware use, and limitations.
   Only update the paper/report after those results exist.

### What can be reused without new weights

- Existing local `llama3.2:3b` can back optional query analysis and text-only candidate
  reranking; verify the Ollama model call after a controlled API restart.
- Existing BGE-M3/SigLIP 2 model definitions and indexed vectors can support optional
  query-variant and text/visual segment RRF once their endpoints are reachable. No claim is
  made that their current host services or cached weights exist until inspected.
- Timed ASR results are currently returned in memory. The search refinement adapter accepts
  a compact word-timestamp payload, but the existing corpus contains no generated timed
  transcripts. Persistence and re-embedding remain unimplemented and gated as above.

**Current decision (updated 2026-11-26):** prepared local-only code is not activated. The
read-only cache check found no BGE-M3, SigLIP 2, or Whisper model directories in the standard
Hugging Face cache; no matching model-cache environment variable is set. Ollama contains only
the text-only Llama 3.2 3B model. After the user approved named ASR/VLM acquisition for a <=3
interval in-memory pilot, the pinned ASR package set was installed into the isolated workspace
`.venv`; `pip check` reports no broken requirements. The host memory query observed 1,142 MiB
free; a later user-provided Task Manager screenshot shows Intel Iris Xe integrated
graphics using shared memory (1.7/7.8 GB at capture) and system memory at 14.4/15.6 GB. This
differs from the earlier project-plan assumption of a discrete RTX 4050; the hardware identity
and runtime are not reconciled. The current WSL Docker probe reports no GPU adapter. Ollama
0.40.17 responds locally, but Qwen was not downloaded; its Windows documentation lists NVIDIA
and AMD support, not a verified Intel Iris Xe path. [Ollama Windows documentation](https://github.com/ollama/ollama/blob/main/docs/windows.mdx)
The running API container's OpenCV 5.1.0 reports OpenCL unavailable (`haveOpenCL=False`,
`useOpenCL=False`); consequently its current classical IVP path is CPU-only as well.
Large-v3 CPU inference may exceed available RAM; the user's latest screenshot shows 2.2 GB
available (13.4/15.6 GB used, 86%), still a high memory load. Therefore no model weights were downloaded
or loaded and the pilot is paused before inference for resource safety. No service restart,
corpus read, or derived-data persistence occurred. Resume after memory pressure is relieved
and the runtime/model accelerator is verified; do not silently substitute a smaller model.

## Verified environment and limits

- RTX 4050 Laptop: 6,141 MiB VRAM; 5,921 MiB free at inspection; driver 581.57.
- `docker run --rm --pull never --gpus all --read-only trace-api:latest nvidia-smi`
  successfully saw the GPU. No new image was pulled. This proves device visibility,
  not CUDA tensor execution, cuDNN compatibility or model fit.
- The project venv and running API container have no torch, transformers,
  sentence-transformers, faster-whisper, CTranslate2 or Pillow installed.
- Existing FFmpeg can decode remote video. CPU decoding remains separate from inference.
- `ANTHROPIC_API_KEY` is absent from the running API container. Only presence was checked;
  this says nothing about accounts/credentials elsewhere. Never paste keys into chat.
- Last verified corpus: 25 registered remote references, 4.60 hours; no indexed assets.
  No new corpus query or application test run is claimed in this planning step.

Keep the specified models. Run one model process at a time and terminate it between
stages to release VRAM. Start with batch size 1; increase only after measurement.
GPU memory limits batch size and throughput, not the number of videos in the corpus.
Do not load a local generative VLM alongside these encoders. API captioning is already
the spec's choice, but needs an approved provider, budget and permission to transmit frames.

## Exact model-file downloads

Public Hub metadata was read in RAM; only the file inventory was saved in
[model-catalog-2026-10-24.json](verification/model-catalog-2026-10-24.json).
Its `selected_files` lists every proposed file with its exact byte count. Sizes exclude
HTTP overhead, installed packages, caches, container layers and temporary duplicates.
No weights were downloaded. Decimal GB are used below.

| Stage | Official model and pinned revision | Selected bytes | Proposed inference |
|---|---|---:|---|
| Text, first | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3), `5617a9f61b028005a4858fdac845db406aefb181` | 2,293,315,801 (2.293 GB) | FP16, batch 1 initially, 1024-dimensional normalized dense vectors |
| Images, later | [google/siglip2-so400m-patch14-384](https://huggingface.co/google/siglip2-so400m-patch14-384), `e8e487298228002f3d8a82e0cd5c8ea9c567f57f` | 4,582,795,867 (4.583 GB) | FP16, batch 1, official processor at 384 resolution; verify 1152-dimensional outputs |
| Speech, later | [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3), `edaa852ec7e145841d8ffdb056a99866b5f0a478` | 3,090,835,702 (3.091 GB) | `int8_float16`, one audio chunk at a time, word timestamps |

Combined selected model files: **9,966,947,370 bytes (9.967 GB)**. Downloading in FP32
and loading in FP16 does not halve the network/disk requirement. Whisper's published
files are FP16 even when loaded for INT8 inference. BGE's selected PyTorch weights
are `.bin`; do not enable arbitrary remote model code. Use a maintained compatible
PyTorch/Transformers loader with restricted weight loading. Exclude the duplicate ONNX
export and optional sparse/ColBERT heads from this dense-only first stage.

BGE supports reduced precision and configurable sequence lengths. Start with 512-token
inputs for the memory test; report truncation and subsequently validate longer document
chunks. Do not silently truncate production evidence. Model dimensionality and finite,
normalized embeddings must be tested before accepting any database writes.

These are candidate runtime settings, not claims that each model fits this laptop.
For each stage record peak allocated/reserved VRAM, process memory, batch/input size,
latency and failures. Stop on OOM; retry batch 1 if a larger batch fails. A model swap,
CPU fallback or changed precision policy must be surfaced rather than applied silently.

## Software installation scope

Use a separate Docker processing image/profile; keep PostgreSQL, Redis and the API
environment stable. Base it on the cached Python/FFmpeg environment where compatible.
Enable GPU access explicitly. Reuse the Windows host driver; no driver replacement is
currently justified. Pin package versions and record their resolved dependencies.

First stage needs a CUDA-compatible PyTorch build, Transformers, sentence-transformers,
tokenizers, sentencepiece and their resolved dependencies. Image processing later adds
the appropriate processor/Pillow stack. ASR adds faster-whisper, CTranslate2, PyAV and
compatible NVIDIA runtime libraries. Avoid a blanket upgrade of the API environment.

**Package/image byte totals remain unresolved.** The catalogs above give exact model
sizes, not an exact all-in install size. A version-specific dependency resolution and
wheel inventory is still needed before claiming that total. Package resolution can itself
download wheels; it was not run under this metadata-only approval. Proposed initial
allowance: at most **8 GB network transfer for software dependencies**, plus the 2.293 GB
BGE selection. Stop and report before exceeding it. Reserve approximately **20 GB free
disk** for this first stage including installed/container copies; this is a planning
allowance, not a measured requirement. Do not install all three model stages together.

Compatibility needs care: the current faster-whisper instructions specify CUDA 12 and
cuDNN 9, while the fetched CTranslate2 installation page still mentions cuDNN 8. Resolve
the exact version combination from release requirements and test real inference before
ASR deployment; device visibility alone is insufficient. Sources:
[faster-whisper requirements](https://github.com/SYSTRAN/faster-whisper#requirements),
[CTranslate2 installation](https://opennmt.net/CTranslate2/installation.html),
[PyTorch installation](https://docs.pytorch.org/get-started/locally/).

## Captioning provider and cost proposal

Candidate: Claude Sonnet 5.5 for segment captioning, subject to account/model availability
and a quality check. This is a proposal, not a configured provider. Its current listed
standard price is $2/million input tokens and $10/million output tokens. Use image blocks
with in-memory base64 frames, avoiding a separate persistent file upload. Prompt versions,
model ID, frame timestamps, usage and response provenance must be recorded.
Sources: [official pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[image input documentation](https://platform.claude.com/docs/en/build-with-claude/vision).

Illustrative cost only: assume six frames billed at 500 tokens each, 1,000 additional
input tokens and 400 output tokens per segment. That is 4,000 input + 400 output tokens:
**$0.012/segment**, or **$18–36 for 1,500–3,000 segments per pass**. Actual image tokens
depend on the selected model and image processing; 500 is a budgeting assumption, not
a measured count. Six full passes would be $108–216 at those assumptions, excluding
reranking, answer generation, judging, retries and taxes. Do not call that a project quote.

Before any paid run: verify exact model ID/access and rates; approve a **$2 pilot cap**,
then measure usage on 20 representative segments and approve the resulting full-run
estimate. Use token estimates, output caps, retry accounting and a persistent spend ledger
to stop before the approved budget. The spec's $250 limit is a proposed project ceiling,
not permission to spend it. No paid API call is authorized by this planning step.

Later judging must use a different model family from the generator, as specified.
Its provider, credentials and cost are a later decision. No local caption-model substitution
or extra GPU purchase is assumed. Choosing no paid API requires an explicit revised plan.

## Proposed persistent-data policy — needs approval

| Data | Location and retention proposal |
|---|---|
| Original videos/images/audio; decoded frames and audio chunks | Remote originals; bounded RAM buffers only. No local media cache, image previews, temporary audio files or swap-backed application cache intentionally created. OS paging is outside the reader's guarantees. |
| Model weights and software | Approved local model directory/Docker volume, reused across runs. This is a necessary exception for local inference software, distinct from a dataset download. Keep exact revision/hash inventory. |
| Source provenance | Existing PostgreSQL `remote_sources`, already authorized. |
| Segment timestamps, generated captions, ASR text, OCR text, vectors | PostgreSQL persistent derived outputs, **not yet authorized**. Label machine-generated content and its model/prompt/input hashes. Never label dataset action labels as generated captions or human ground truth. |
| Source annotations/narration | Continue RAM-only reads by default. Request explicit permission before retaining their text as corpus data. Do not put full-video narration into arbitrary segment transcripts. |
| Human reports, manual excerpts, links and query/gold splits | Persist in PostgreSQL only after the human source/annotation workflow and relevant text retention are approved. Real sources and attribution required. |
| Verification and evaluation reports | Workspace documents containing counts, parameters, metrics and provenance; avoid copied media or full text dumps. |
| Provider response cache | Proposed PostgreSQL derived-output cache keyed by input/model/prompt hashes, covered by the same future derived-data approval; no raw-frame payload logs. |

At 3,000 segments, one 1024-d float32 vector plus one 1152-d float32 vector is
26,112,000 bytes of raw values. At 400 images, their 1152-d vectors add 1,843,200 bytes.
These are arithmetic lower bounds, not database disk estimates: HNSW, row overhead,
text, indexes, WAL and backups add space; document chunk count is not yet measured.

Current asset rows require object-store keys and media checksums. Processing remote
references into indexed evidence therefore needs a deliberate provenance/schema extension;
do not fake MinIO keys, use URL hashes as media checksums, or mark S0 ingestion done.
MinIO remains deferred, not replaced. Any normalized-video/HLS/image artifact persistence
required by the original pipeline conflicts with the current no-media-copy preference
and must be agreed before that part is implemented.

## Next approval and acceptance evidence

### Read-only package and storage preflight (2026-11-26)

The workspace `C:` volume reports **213.93 GiB free of 542.5 GiB**. This is ample
for the proposed diagnostic payload on raw capacity alone, but does not account for
other consumers, package installation overhead, model duplication, or a GPU/RAM fit.
Metadata inspection confirms a 1.1 MB universal wheel for faster-whisper 1.2.1 and
a CPython 3.12 Windows x86-64 PyAV 19.0.2 wheel of 28.2 MB; these are examples, not
the complete dependency closure. No complete transitive wheel resolution was performed:
the approved preflight explicitly stopped before fetching package artifacts. The user
subsequently approved the bounded pilot; the pinned ASR package set was installed and its
runtime resolution is documented in the current decision above. Model weight downloads remain
paused pending safe hardware capacity evidence.

Recommended next step: **install only the text runtime and BGE-M3**, under the allowance
above, and implement its adapter. No paid captioning, full corpus indexing, ASR or image
weights in this step. Run synthetic technical-text probes first, then small in-memory
source probes without saving source text. Record actual peak memory and throughput,
1024-dimensional normalized outputs, deterministic behavior within a declared tolerance,
and out-of-memory handling. Test semantic ranking as a sanity check, not a retrieval score.

This makes the next architecture decision evidence-based. Separately approve derived
PostgreSQL persistence, captioning provider/budget, and remote asset processing before
full corpus indexing. Human trial/equipment review, genuine reports/manuals and evaluation
queries remain prerequisites for meaningful methodology results.
