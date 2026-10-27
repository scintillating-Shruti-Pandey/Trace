# Data licenses

## Proposed model software — 2026-10-24

Official Hub metadata identifies BAAI/bge-m3 and Systran/faster-whisper-large-v3 as MIT,
and google/siglip2-so400m-patch14-384 as Apache-2.0. These were metadata-only checks;
weights have not been downloaded. Preserve notices with future installs and inspect
resolved software dependencies' licenses separately. See the
[pinned metadata inventory](verification/model-catalog-2026-10-24.json).

No real corpus assets have been imported. Every incoming asset must carry its actual
source, license, and redistribution flag; record its license reference here.

October 24 registration: 25 IndEgo remote references now have CC BY 4.0, the publisher's
dataset URL, pinned revision and verification provenance in PostgreSQL. These are source
references only; no underlying media or raw narration/annotation text is stored locally.
Source: [Fraunhofer IPK IndEgo](https://huggingface.co/datasets/FraunhoferIPK/IndEgo),
revision `c822468b5e0c9c42ebbf2939d3be936c2b203704`. Terms metadata rechecked at registration.
The exact selection is [the compliant verification report](verification/indego-final-2026-10-24.jsonl).

## Candidate review — 2026-10-24

| Dataset | Terms and current scope |
|---|---|
| [IndEgo](https://huggingface.co/datasets/FraunhoferIPK/IndEgo) | Hub metadata/card: CC BY 4.0. Candidate only; retain attribution and provenance in any future derived index. Bounded media ranges, narration and temporal annotations inspected in RAM; no dataset copies persisted. |
| [IMPACT](https://huggingface.co/datasets/KratosWen/IMPACT) | Dataset/documentation: CC BY-NC-SA 4.0; [official repository](https://github.com/Kratos-Wen/IMPACT) distinguishes Apache-2.0 code. Candidate only, no archive/media access. Honor research/education and noncommercial use constraints if adopted. |
| [InspecSafe-V1](https://huggingface.co/datasets/Tetrabot2026/InspecSafe-V1) | Previously recorded CC BY 4.0. Four preview images decoded in RAM October 24; future use requires attribution. Preview media access does not authorize inventing missing/truncated annotations. |
| [MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) | Official page: CC BY-NC-SA 4.0. Download unavailable; not adopted and no samples accessed. |
| [Worlddatalabs manufacturing dataset](https://huggingface.co/datasets/Worlddatalabs/egocentric-manufacturing) | Hub license `other` and manual access gate. Terms unresolved; not adopted and no gated payload accessed. |

The user's later October 24 instruction removes FORGE from delivery. Earlier access and
terms issues are historical, not pending user actions. Alternative evaluation has not
yet been adopted and must carry its own source terms and explicitly different scope.

## External datasets checked 2026-10-04

| Dataset | Terms recorded from the current dataset page/card | Handling |
|---|---|---|
| [FORGE](https://huggingface.co/datasets/AI4Manufacturing/forge) | **NOT FOUND, check manually.** License section is a placeholder; Hub license metadata absent. Manual access approval required. | Do not use samples until access and terms are resolved. |
| [LoVR](https://huggingface.co/datasets/debugger123/LoVR-benchmark) | `cc-by-nc-sa-4.0`; card describes academic/educational use and responsible-use practices. | Keep attribution and noncommercial/share-alike restrictions with any future retained or redistributed derivatives. Only five caption rows were read into RAM for access verification. |
| [InspecSafe-V1](https://huggingface.co/datasets/Tetrabot2026/InspecSafe-V1) | Current metadata and card name `cc-by-4.0`, more specific than the old plan's research-use description. | Retain attribution if later used. Truncated previews were inspected, not treated as complete records. |
| [MomentSeeker](https://huggingface.co/datasets/avery00/MomentSeeker) | `cc-by-nc-sa-4.0` in current Hub metadata/card. | Annotation-only reads in RAM; preserve attribution and noncommercial/share-alike restrictions for future derivatives. |
| GEM | Not rechecked; dataset remains dropped under the supplied plan. | No files accessed. |

Streaming does not remove dataset license conditions. No dataset payload or media was
saved locally during these checks, and no rights to redistribute underlying videos are
assumed from public availability.

MinIO's deferred source build uses its [official AGPL-3.0 licensed source](https://github.com/minio/minio/blob/master/LICENSE).
It is not currently built or running. Other software dependencies retain their upstream
licenses. No distribution of third-party media is part of this milestone.
