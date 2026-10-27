# Trace: Rehearsed Demo Script & Fallback Presentation Guide

**Contract Reference**: `records/ENGINEERING_SPEC.md` §11 (UI Design), §14 (Demo), §18 (DoD Checklist Item 11: *"Demo script rehearsed, fallback recording made"*)  
**Execution URL**: `http://localhost:8000/` (or `http://localhost:8000/demo/seek`)  
**Corpus Inventory**: 25 IndEgo manufacturing videos (4.60 hours, 1,205 segments), 28 technical documents (67 chunks), 114 workpiece keyframes, 154 human evidence links  
**Local GPU Engine**: RTX 4050 6 GB GPU co-resident FP16 microservices (BGE-M3 port 8001, SigLIP 2 port 8002; $0.00 spent)

---

## 1. Demo Narrative & Positioning

Trace is an industrial multi-modal evidence search and grounded question-answering system. Unlike chatbots that search only PDFs or generic video retrieval models that return whole video clips without timestamps, Trace:
1. Pinpoints the **exact moment inside a manufacturing video** where an operation or fault occurs (temporal grounding).
2. Connects that moment across a **hand-built connective layer** of 154 human evidence links to the relevant maintenance report findings and technical manual specifications (multi-hop reasoning).
3. Streams a grounded, concise answer with **strict inline citations (`[E1]`, `[E2]`)** that jump the video player to `start - 2s` with sub-millisecond execution latency.
4. **Honestly abstains** on out-of-domain queries without hallucinating part numbers or specifications.

---

## 2. Canonical 4-Step Rehearsed Walkthrough

### Step 1: The Canonical Multi-Hop Query (Video + Document Fusion)
- **Input Query**: `tightening torque is specified for assemble`
- **What to Observe**:
  1. **Real-Time Token Streaming**: The Grounded Answer panel immediately begins streaming tokens via SSE (`GET /api/v1/generate/stream`).
  2. **Grounded Answer Structure**:
     - Lead sentence anchors directly to the primary video moment (`[E1]`), quoting start/end timestamps (`00:15 – 00:30` of `IndEgo assemble lower hinge`).
     - Supporting sentence anchors to the technical manual chunk (`[E2]`, `[E3]`), providing the torque specification.
  3. **Interactive Citation Badges**:
     - Click `[E1]` in the answer: The HTML5 video player instantly jumps to `00:13.0` (lead-in `start - 2s`), begins playback, and paints the green highlight band across the timeline.
     - Click `[E2]`: The connected technical document card smoothly scrolls and highlights with a green glow.
  4. **Strict Validation**: The answer footer reports `100% valid citations` (zero non-retrieved references).

### Step 2: Temporal Grounding & Instant Seek
- **Input Query**: `assemble lower hinge`
- **What to Observe**:
  1. The coarse-to-fine temporal refinement engine (§8.7) identifies the precise 15-second procedural keystep inside the longer video.
  2. The Seek HUD reports seek latency of **0.8–1.1 ms** (vastly beating the $< 300\text{ ms}$ spec threshold).
  3. The timeline playhead tracks playback synchronously at 4Hz.

### Step 3: Deep Technical Inspection
- **Input Query**: `casing bolt torque hydraulic pump`
- **What to Observe**:
  1. Retrieves connected maintenance reports (`MR-2026-014`) and equipment manual sections (`HP-400 Manual §4.2`).
  2. The answer cites both the observed inspection findings and the specification tolerance.

### Step 4: The Honest Abstention (Hallucination Robustness)
- **Input Query**: `curing time underwater epoxy`
- **What to Observe**:
  1. The system detects that "underwater epoxy" is outside the manufacturing equipment corpus.
  2. Instead of hallucinating a plausible chemical formula or fake cure time, the Grounded Answer panel shifts into an amber warning box:
     > *"Abstained (Honest): The retrieved manufacturing corpus does not contain evidence regarding curing time underwater epoxy."*
  3. **Talking Point**: *"Demonstrating an honest refusal is far more persuasive to an industrial engineering team than a confident hallucination."*

---

## 3. Secondary Views Walkthrough

### View A: Corpus Asset Explorer (`/corpus`)
- Navigate to the **Corpus Explorer** tab in the top header.
- **What to Observe**:
  - Live inventory cards across the 25 videos, 28 documents, 114 keyframes, and 154 links.
  - Filter pills allow instant slicing by `Videos`, `Documents`, or `Evidence Links`.
  - Click on any asset card to open the detail modal displaying its segment breakdown, timestamp bounds, chunk text, and license (`CC BY 4.0`).

### View B: Evaluation & Ablation Dashboard (`/eval`)
- Navigate to the **Evaluation & Ablation** tab in the top header.
- **What to Observe**:
  - The Definition of Done scorecard confirms all 6 acceptance criteria met.
  - The full 11-configuration ablation matrix ($A_0$–$A_{10}$) table with 10,000 bootstrap confidence intervals.
  - Key finding highlight cards:
    - **Connective Layer ($A_5$)**: $+3.3\%$ lift in Joint Recall@10 and $+0.0139$ lift in MRR over isolated retrieval.
    - **Multi-Modal Lift ($A_7$ vs $A_1$)**: $+46.7\%$ Joint Recall@5 ($p = 0.0000$) over text-only RAG.
  - Judge validation: $93.3\%$ agreement and Cohen's $\kappa = 0.8667 \ge 0.70$.

### View C: Debug Retrieval Trace (⚙ Overlay)
- Click **⚙ Debug Trace** in the top-right header.
- **What to Observe**:
  - Sliding drawer revealing the latency waterfall (BGE-M3 text embed, SigLIP 2 visual encode, pgvector HNSW search, GIN BM25, and SSE streaming).
  - Provenance breakdown: displays how many candidates were found directly versus pulled in through human evidence link expansion.

---

## 4. Offline Fallback Recordings Catalog

In accordance with Engineering Spec §18, the following screen recording WebP videos were captured during live browser sessions and are saved locally in the artifacts directory for offline presentation fallback:

| Recording File | Contents & Flow | Timestamp |
|---|---|---|
| `phase5_live_streaming_demo_1792865672104.webp` | Full Phase 5 live demo: real-time SSE token streaming, interactive `[E4]` badge click jumping to document card, and amber unanswerable abstention banner. | 2026-10-24 23:45 IST |
| `phase5_grounded_demo_1792865513887.webp` | Live verification of grounded multi-modal generation and player synchronization. | 2026-10-24 23:43 IST |
| `multimodal_seek_demo_1792856922729.webp` | Multi-modal moment seeking demo across video, keyframe, and document cards. | 2026-10-24 21:20 IST |
| `phase2_seek_demo_1792852014263.webp` | Instant timestamp seeking, refined window HUD (`11:28 – 11:34`), and lead-in jump (`686.1s`). | 2026-10-24 19:58 IST |

*These files can be played back in any standard modern web browser or presentation tool if local Docker services are unavailable.*
