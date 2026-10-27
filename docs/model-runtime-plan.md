# Model runtime and persistence plan

> Superseded recommendation, 2026-10-24: see [dependency audit](dependency-audit.md).
> The system Python already contains torch/transformers; the earlier check only
> covered the project venv and API container. The proposed 8 GB software allowance
> is withdrawn as the next step. Prefer existing software and verified hosted APIs;
> no installation or model download is approved. Historical file-size evidence below
> remains useful, but is not a required download list.

Prepared 2026-10-24 (Asia/Calcutta). **Proposal, not installation approval.**
The running status remains [build-status.md](build-status.md).

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
