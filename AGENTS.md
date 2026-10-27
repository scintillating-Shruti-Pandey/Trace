# Trace project instructions

## Follow the agreed plan

- The user requires ZERO monetary spending. Do not make potentially billable API
  calls, purchase credits, enable paid services or interpret an unlimited monthly
  limit/configured API key as free usage. Prior proposed paid pilots are superseded.
  Latest approval covers read-only billing inspection and continuing free local checks.

- Use `records/ENGINEERING_SPEC.md` as the build contract. The Word briefing supplies
  context; `records/AGENT_DATASET_SETUP.md` governs external dataset work.
- The user explicitly requires missing dependencies or prerequisites to be surfaced.
  Do not silently replace components or change the architecture to work around them.
- The user's latest instruction requires explaining each next step and obtaining
  permission before proceeding with it. Report actual data-access evidence at milestones.
  The latest 2026-10-24 approval covers resuming existing services and implementing
  remote readers: a small decoding check, followed by access/annotation validation
  targeting a 20–25-video selection. The subsequent request to inspect actual state
  and proceed authorizes PostgreSQL remote-source registration after that audit.
  Model setup, indexing and later milestones still need their own approval.
- Latest user approval additionally covers implementing the BGE-M3 HTTP adapter and
  offline tests using existing libraries; see `docs/embedding-api.md`. Live paid calls,
  installations and derived-data persistence still need approval.
- The earlier approval covered preparing the 6 GB model-runtime/download/cost/persistence
  plan only. Its proposed budgets and retention policy are not installation, spending
  or derived-data persistence authorization. See `docs/model-runtime-plan.md`.
- On 2026-10-24 the user explicitly removed FORGE from the delivery plan. Do not wait
  for its access, retry its gate, or treat it as a completion blocker. Define a separate
  industrial-image evaluation with explicit scope; do not claim FORGE-equivalent results.
- The existing RTX 4050 Laptop GPU (6 GB VRAM) is the fixed hardware budget. Plan
  sequential inference and bounded batches; benchmark feasibility before promises.
  Four/five-item checks are diagnostics only, never the final corpus or evaluation size.
- MinIO and media ingestion were deferred with user agreement on 2026-10-04. This is
  not authorization to replace MinIO or PostgreSQL with another implementation.
- For external datasets, the user's 2026-10-04 preference overrides the older plan's
  local samples: prioritize remote reads in memory, with no dataset/media files or
  persistent data caches on disk. Code and verification reports may be saved. Surface
  any required local download before doing it. Do not bypass Hugging Face access gates.

## Maintain the progress report

- Read `docs/build-status.md` before substantial project work.
- Update that same report after meaningful implementation work, validation, decisions,
  or blockers, before handing the task back to the user.
- Keep its current summary, roadmap, acceptance tracker, dependencies, and next steps
  consistent with the evidence. Add a dated history entry without deleting earlier history.
- Use Asia/Calcutta dates. Distinguish implemented, tested, prepared but unverified,
  deferred, and blocked work. Record test commands/results and material limitations.
- Do not invent completion percentages, corpus counts, benchmark scores, or passing tests.
  Label older verification as the last verified state rather than claiming a fresh check.
- Keep the README's milestone summary aligned when the milestone changes. The progress
  report is the single detailed tracking document; avoid creating competing status files.
- Update during project work; no recurring automation is requested.
