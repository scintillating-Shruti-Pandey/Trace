# External dataset setup report

Checked 2026-10-04 (Asia/Calcutta). Mode: **remote reads in memory; no saved dataset files**.

The user's latest instruction supersedes the old plan's local Parquet samples and clip
downloads. This is an access-verification milestone, not fulfillment of that plan's
original definition of done. In particular, **FORGE is blocked and no 500-row FORGE sample
has been obtained**. No external image-encoder or video retrieval evaluation has run.

## Preflight

- HF_TOKEN was absent; public access was tried for all four Hugging Face repositories.
- Free space on D: before checks: 394,576,916,480 bytes. Disk capacity was not a blocker.
- No dataset-related dependencies were installed; stdlib HTTPS was sufficient for the
  verified metadata and annotation reads.
- Dataset/media/cache bytes saved by this setup: **0**. Markdown reports and source code
  are intentionally local; no samples, media files, or data tables were persisted.
- Existing `data/external/gem/` contained no files and was left untouched.

## Results

| Dataset | Status | Method and exact tested scope | Remaining limitation |
|---|---|---|---|
| FORGE | **BLOCKED** | Hub catalog read; `/is-valid`, `/size`, `/splits` all returned HTTP 401. `gated=manual`. | Access approval and license clarification required; no row/image access. |
| LoVR | **OK — five caption rows** | `/rows`, config `default`, split `train`, offset 0, length 5; expected columns `path`, `vid`, `slice_num`, `cap`, `theme_info`. | Offset 32,312 returned HTTP 500. Full traversal, separate video-level reads, and 200-clip media access are unverified. |
| InspecSafe-V1 | **SKIPPED — complete sample access unresolved** | `/rows` returned HTTP 500. `/first-rows` returned ten previews; first five include truncated JSON/key fields, some truncated text. | Do not use previews as complete ground truth. Archives were not streamed or downloaded. |
| MomentSeeker | **OK — annotations** | Read `t2v.json` (1,000), `ti2v.json` (400), and `tv2v.json` (400) into RAM. Validated query/path/time-interval field presence. | No video/image bytes fetched. Current repository includes separate media archives, not just annotation files. |
| GEM | **SKIPPED** | Dropped per the existing plan; empty local folder. | No action requested; old download-link failure not rechecked. |

For every Hugging Face repository, public Hub metadata plus Viewer `/is-valid`, `/size`,
and `/splits` were checked. A failed Viewer size conversion is not proof a dataset is
empty: InspecSafe and MomentSeeker both returned zero-size conversion metadata with
failed conversion entries while their Hub file catalogs were nonempty.

## Revisions observed

| Repository | Hub commit at verification |
|---|---|
| AI4Manufacturing/forge | `e3db7358264772426c004da13f7ec05bd67fcce4` |
| debugger123/LoVR-benchmark | `5a46a68fd666b3390af92902d9199e70bc51ebe2` |
| Tetrabot2026/InspecSafe-V1 | `f3cb7d3e7827c1afc1c5bfd0524257984bba46ab` |
| avery00/MomentSeeker | `4a842253a60954cd8765b3d25f6274e2af56b2ff` |

MomentSeeker annotation requests used that immutable revision. Dataset Viewer conversion
responses are not guaranteed to correspond to the currently observed Hub commit.

## Reproduce

From `D:\Trace` in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m app.datasets.huggingface inspect all
.\.venv\Scripts\python.exe -m app.datasets.huggingface sample lovr --config default --split train --limit 5
.\.venv\Scripts\python.exe -m app.datasets.huggingface sample lovr --config default --split train --offset 32312 --limit 5
.\.venv\Scripts\python.exe -m app.datasets.huggingface sample inspecsafe --config default --split train --limit 5
.\.venv\Scripts\python.exe -m app.datasets.huggingface annotations --task text
.\.venv\Scripts\python.exe -m app.datasets.huggingface annotations --task text-image
.\.venv\Scripts\python.exe -m app.datasets.huggingface annotations --task text-video
.\scripts\dev.ps1 test
```

The two failing `sample` commands are included intentionally to reproduce the observed
limits; results may change upstream. CLI output contains summaries, not saved data rows.

## Validation

25 tests passed, including eight new remote-reader tests and the four existing real
PostgreSQL/Redis integration tests. Reader tests verify memory budgets, access-gate
handling, explicit HTTP errors, bounded pagination, truncated-row rejection, immutable
annotation URLs, and no data writes. Live reads verified LoVR's five train captions and
MomentSeeker's annotations. Ruff lint passed. Starlette's existing TestClient deprecation
warning remains non-blocking.

## Human actions still needed

1. Before the required FORGE evaluation, review/request access at
   [FORGE on Hugging Face](https://huggingface.co/datasets/AI4Manufacturing/forge) and clarify
   its missing license terms. No token should be pasted into chat.
2. Supply or identify real manufacturing videos and matching reports/manual excerpts for
   the linked corpus; external benchmarks do not provide that connective layer.

No large dataset download or GEM recovery is requested.
