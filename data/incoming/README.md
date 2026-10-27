# Phase 0 corpus inputs

Put real source files here. Nothing in this folder is committed except this guide and
the example manifest. No generated or fabricated maintenance evidence should enter the corpus.

Target 20–25 videos (hard cap 25, total duration at most six hours), 25–40 authored
maintenance reports, and 15–30 manual/SOP excerpts. Use the hydraulic, rotating-machinery,
and CNC equipment families. Record source, license, and redistribution permission per asset.

Start with one real video and its matching report and manual passage. Note the exact
timestamps linking the observed action or finding to the document passages. Humans must
verify captions, write reports based on actual footage, and author evaluation questions.
The annotation plan in the engineering spec remains the authority.

Copy `manifest.example.json` outside its tracked template location and replace every
placeholder. Paths are relative to this folder, for example `pump/inspection.mp4`.
Media registration is currently disabled pending MinIO setup. Once enabled:

```powershell
trace ingest data/incoming/my-manifest.json
trace job RETURNED_JOB_ID
```

The service never downloads the `source_uri`; it is provenance metadata.
Registration is not completed model ingestion. Segmentation, captions, ASR, and embeddings
will be implemented in subsequent milestones.
