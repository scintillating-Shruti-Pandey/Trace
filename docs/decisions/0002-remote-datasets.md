# Remote external dataset access — 2026-10-04

The user asked to use the Hugging Face data while avoiding local downloads. This
instruction supersedes the older dataset plan's saved FORGE sample, LoVR clips/tables,
and local MomentSeeker annotations. Keep dataset responses in RAM; save only source
code and verification reports. Surface any need for local payload files before acting.

For the currently verified annotation paths, use stdlib HTTPS and the Dataset Viewer
instead of a bulk dataset loader. This avoids implicit dataset caching and unnecessary
package installations. Enforce a per-response byte limit and reject gated repositories
and truncated rows. Do not automatically follow media references or fetch archives.

This is a storage/access decision, not a replacement for the linked manufacturing
corpus or permission to claim benchmark success. It does not change PostgreSQL, MinIO,
model choices, or the retrieval architecture. MinIO remains deferred for actual corpus
media; external benchmark annotation reads do not depend on it.

Observed limits and reproducible commands live in `data/external/SETUP_REPORT.md`.
FORGE is blocked, LoVR is verified only for a small caption read, InspecSafe full rows
are unresolved, and MomentSeeker is verified only for annotation files. Do not label
the original external dataset setup definition of done as achieved.
