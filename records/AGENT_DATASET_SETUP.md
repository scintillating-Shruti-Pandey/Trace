# AGENT TASK: External Dataset Setup (mmi project)

> **User-approved amendment — 2026-10-24:** FORGE is dropped from delivery; its
> required registry entry, sample instruction and acceptance check below are superseded.
> Do not wait for access or retry the gate. Verify an alternative industrial-image
> evaluation source/protocol before adopting it. The user's remote-memory preference
> overrides saved samples, and each implementation step still requires approval.
> Five-item checks establish reader correctness only; scale to the engineering spec's
> full corpus and held-out evaluation targets once those checks pass.

You are setting up the external datasets for the Multimodal Manufacturing Intelligence project.
Inputs you were given: `ENGINEERING_SPEC.md` (the contract) and this file (the dataset plan).
Work autonomously. Stop and ask the human only in the cases listed under "Stop conditions".

## Goal

Make every external dataset usable with the **smallest possible local footprint**: stream or
sample remotely where possible, keep only small subsets, embeddings, and annotation tables.
Do NOT download full datasets unless a row below says so.

## Ground rules

1. Never invent a dataset, URL, file name, or number. If a link or repo fails, log it and move on.
2. MELON is dropped. Never use or search for it.
3. No public dataset provides the linked video + report + manual corpus. That corpus is a **human task**
   (spec Phase 0, hard cap 25 videos, 2 weeks). Create `data/incoming/` and a README there. Never fabricate videos, reports, or manuals.
4. Code snippets in this file are untested. Run each on a tiny sample (5 rows) before scaling up.
5. Spec §5 standing rule: record every dataset in `docs/verified-sources.md` (URL + date checked)
   and its terms in `docs/licenses.md`.
6. Never commit data. Add `data/external/` and `data/cache/` to `.gitignore`.

## Dataset registry

| Order | Name | Needed? | Source (HF repo unless noted) | Access mode | Local path |
|---|---|---|---|---|---|
| 1 | FORGE | **Required** (Phase 3 exit gate) | `AI4Manufacturing/forge` (about 11.6 GB, parquet, 7,346 rows) | Stream; sample a subset | `data/external/forge/` |
| 2 | LoVR | Optional (Phase 6, D7) | `debugger123/LoVR-benchmark` (95.9 GB total, 41,271 rows, cc-by-nc-sa-4.0; page showed no gate when checked, but verify) | Read caption tables remotely (columns: path, vid, slice_num, cap, theme_info); fetch ~200 clips only. Never download the full 95.9 GB | `data/external/lovr/` |
| 3 | InspecSafe-V1 | Optional (Phase 3 stretch) | `Tetrabot2026/InspecSafe-V1` (packaged as `train.tar.gz`) | Try streaming; else fetch a small subset | `data/external/inspecsafe/` |
| 4 | MomentSeeker | Optional (metric reference) | `avery00/MomentSeeker` (annotations only) | Download in full (small) | `data/external/momentseeker/` |
| 5 | GEM | **DROPPED: download link is dead** (gemdata.blob.core.windows.net does not resolve). Do not wait for it. Use LoVR for the generic retrieval check instead. If the human ever recovers the files, the notes below apply. | https://microsoft.github.io/GEM/ and https://github.com/microsoft/GEM (not on HF; the human must accept the terms of service on the GEM Leaderboard) | Manual download by human, then agent processes whatever is placed in the folder | `data/external/gem/` |

Reference links: LoVR https://github.com/TechNomad-ds/LoVR-benchmark, FORGE https://ai4manufacturing.github.io/forge-web/,
InspecSafe-V1 https://huggingface.co/datasets/Tetrabot2026/InspecSafe-V1.

## Steps

### Step 0: Preflight
- `pip install -U huggingface_hub datasets duckdb pyarrow`
- Check `HF_TOKEN` env var. If absent, still try every dataset without a token first. Only mark a dataset `BLOCKED` if you get an actual access error (401/403).
- Check free disk space and record it in the final report.
- Create dirs: `data/external/{forge,lovr,inspecsafe,momentseeker}`, `data/cache`, `data/incoming`, `docs`.

### Step 1: Verify each dataset exists
For each HF repo call `https://datasets-server.huggingface.co/is-valid?dataset=<repo>` and
`.../size?dataset=<repo>`, and record the result. If a repo does not exist or the contents differ from the registry,
log it in `docs/verified-sources.md` as FAILED and do not proceed with that dataset.

### Step 2: Fetch, in registry order, using the lightest method that works
Try in this order and keep the first that works:
1. `load_dataset(repo, split=..., streaming=True)` and `.take(N)`
2. DuckDB over `hf://datasets/<repo>@~parquet/default/<split>/*.parquet`
3. Dataset Viewer API: `https://datasets-server.huggingface.co/rows?dataset=<repo>&config=default&split=<split>&offset=0&length=100`
4. `list_repo_files` then `hf_hub_download` for selected files only
5. Download, process, store only the derived output, delete the raw file

Per dataset:
- **FORGE**: sample a subset (default 500 rows, stratified by workpiece category if a category field exists). Save the sample as `data/external/forge/sample.parquet`. This feeds the Phase 3 zero-shot image-encoder check.
- **LoVR**: read clip-level and video-level caption tables remotely and save as parquet. Select ~200 clips with a fixed random seed (42), fetch only those, and save the clip list to `data/external/lovr/subset_manifest.json`. Delete raw clips after embedding once the pipeline exists.
- **InspecSafe-V1**: test streaming on 5 items. If it fails, fetch the smallest viable subset. Record in the report which method worked. Ignore infrared, audio, depth, and radar data (out of scope per spec).
- **MomentSeeker**: download annotations in full. Check the dataset card and note whether source videos are separate. Do not fetch videos.
- **GEM** (dropped; only if files already exist in `data/external/gem/`): the human downloads only the **GEM-V Data** package (video tasks; QV_mR query-video retrieval is the relevant task; use the dev/validation split and filter to English). GEM-I is not needed. Never attempt to accept terms or scrape the leaderboard. If `data/external/gem/` already contains files, inspect them, convert any annotation tables to parquet, and sample a small subset (e.g. 500 rows) for the generic-retrieval smoke test. If the folder is empty, log `SKIPPED: download link dead, dropped` in `docs/verified-sources.md`. Do not list it as a pending human action.

### Step 3: Convert annotation tables to parquet
Any CSV/JSON annotation table you keep goes to parquet in the same folder. Keep raw video as-is.

### Step 4: Write the docs
- `docs/verified-sources.md`: one line per dataset: name, URL, date checked, status (OK / FAILED / SKIPPED / BLOCKED).
- `docs/licenses.md`: license or terms text found on each dataset page, with the URL. If none found, write `NOT FOUND, check manually`. LoVR is cc-by-nc-sa-4.0 (non-commercial, share-alike) and its paper recommends responsible-use practices; InspecSafe-V1 is described as free for research.

### Step 5: Final report
Write `data/external/SETUP_REPORT.md` containing: per dataset status, method used, local size on disk, what was
sampled, any errors, and the exact commands to reproduce. End with a list of the human actions still needed.

## Stop conditions (ask the human, do not guess)
- LoVR returns an access error (401/403). Log it, finish the other datasets first, then report.
- Free disk space is under 15 GB and you cannot stream.
- A repo's contents contradict the registry.
- Licensing terms forbid research use or caching.

## Definition of done
- FORGE sample is saved and readable with pandas, and FORGE status is OK. If FORGE failed, say so loudly.
- Every other dataset is OK, SKIPPED, or BLOCKED with a reason.
- `docs/verified-sources.md`, `docs/licenses.md`, and `data/external/SETUP_REPORT.md` exist.
- No full dataset was downloaded except MomentSeeker annotations.
- `data/incoming/README.md` tells the human what Phase 0 needs: 20-30 self-filmed or openly licensed videos
  (cap 25), plus report and manual excerpts tied to timestamps.
