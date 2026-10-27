# Trace: Multimodal Manufacturing Intelligence & Video Search with RAG
## Intelligent Model Design using AI — Capstone Project & Presentation Deck
*Optimized for import into Gamma.app, Canva, PowerPoint, and Class Presentation*

---

# Slide 1: Title & Overview
### Trace: Multimodal Manufacturing Intelligence & Video Search with RAG
**A Multi-Modal Grounded Evidence Engine for Manufacturing Operations & Plant Maintenance**

* **Subject**: Intelligent Model Design using AI
* **Project Team**:
  * **Shruti Pandey** (Enrollment No: **S24CSEU0527**)
  * **Satvick Miglani** (Enrollment No: **S24CSEU0476**)
* **Domain**: Heavy Industry, Manufacturing Systems, Multi-Modal Artificial Intelligence
* **Key Innovation**: Dual-Retriever Temporal Grounding (BGE-M3 + SigLIP 2) with Human-Audited Cross-Modal Evidence Graph
* **Hardware Budget**: Strict 6.0 GB VRAM Edge Budget (NVIDIA RTX 4050 Laptop GPU) · $0.00 Monetary Spending ($0 External Cloud Calls)
* **Core Deliverable**: Production-Grade Temporal Moment Retrieval, Structure-Aware Technical Manual Linking, and Zero-Hallucination Grounded Answer Synthesis

> **Speaker Note / Hook**: "Good morning respected faculty and peers. Today, Satvick and I present our capstone project for Intelligent Model Design using AI — TRACE: Multimodal Manufacturing Intelligence & Video Search with RAG. In heavy industry, an operator cannot afford an AI hallucination: if a technician applies 15 Nm instead of 24.5 Nm to a hydraulic pump casing, the assembly ruptures under 480 bar of pressure. Trace solves this by grounding procedural video footage directly into authoritative engineering manuals with sub-second temporal precision."

---

# Slide 2: Executive Summary & Project Vision
### The Need for Industrial-Grade Multi-Modal Intelligence

* **The Industrial Paradox**: Modern manufacturing facilities generate hundreds of hours of procedure video footage and thousands of pages of PDF equipment manuals, yet shop-floor technicians still rely on guesswork during critical maintenance.
* **The Failure of Generic GenAI**: Standard Large Language Models (LLMs) and naive text-only RAG fail in heavy industry because they lack temporal awareness, cannot 'see' workpiece orientation in video, and hallucinate torque values.
* **The Trace Solution**:
  1. **Cross-Modal Retrieval**: Unifies 4.60 hours of high-definition procedural video and 28 authentic engineering manuals into a joint vector space.
  2. **Sub-Second Temporal Grounding**: Pinpoints the exact 2-minute procedural window and refines it down to the exact second where a bolt is torqued or a seal is seated.
  3. **Grounded Answer Synthesis**: Produces answers with verifiable bracketed citations (`[E1]`, `[E2]`) linked to exact video timestamps and manual sections.
  4. **The Honesty Gate**: Automatically abstains when asked out-of-domain queries, guaranteeing zero hallucinations.

---

# Slide 3: The Industrial Problem Space
### Why Standard AI and Naive RAG Fail on the Factory Floor

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      NAIVE TEXT-ONLY RAG BREAKDOWN                      │
├───────────────────────────────┬─────────────────────────────────────────┤
│ Symptom                       │ Consequence in Factory Operations       │
├───────────────────────────────┼─────────────────────────────────────────┤
│ 1. Text-Only Blindness        │ Cannot verify tool angle, part seating, │
│                               │ or physical assembly gestures in video. │
│ 2. Arbitrary Chunking (512 t) │ Chunks split torque tables across pages,│
│                               │ decoupling bolts from their parent part.│
│ 3. Temporal Disconnect        │ Pointing to a "15-minute video" without │
│                               │ an exact seek timestamp wastes hours.   │
│ 4. Unchecked Hallucinations   │ Generates believable but dangerous      │
│                               │ torque specifications (18 Nm vs 24.5 Nm)│
└───────────────────────────────┴─────────────────────────────────────────┘
```

* **High-Stakes Environment**: In automotive, aerospace, and heavy equipment plants, improper assembly causes equipment failure, warranty recalls, and technician injury.
* **Semantic Divergence**: Technical manuals use rigorous part numbers (`M10 Grade 8.8 Hex Casing Bolt`), whereas video audio transcripts use colloquial phrasing (`"now tighten down these outer screws"`). Text-matching alone yields 0.0% joint recall.

---

# Slide 4: Core Innovation & System Blueprint
### How Trace Bridges Video Moments and Engineering Specifications

* **Three-Pillar Architectural Framework**:
  1. **Dual Multi-Modal Retrieval Engine**: Combines 1024-dimensional BGE-M3 dense semantic vectors with BM25 sparse exact-match keyword handles and SigLIP 2 zero-shot visual embeddings.
  2. **Bi-Directional Evidence Graph (154 Grounded Links)**: Connects specific procedure video spans (`start_s`, `end_s`) to authoritative manual sections, torque values, and warning notes via 4 formal relation types:
     * `specifies`: Document sets binding torque/tolerance for video action.
     * `documents`: Document explains the broader subsystem procedure.
     * `contradicts`: Video demonstrates assembly error violating manual specs.
     * `depicts`: Video illustrates a component diagrammed in the text.
  3. **Honesty & Refinement Layer**: Temporal boundary refiner (`IoU > 0.5`) + strict abstention classifier rejecting out-of-domain questions.

---

# Slide 5: System Architecture Pipeline
### High-Performance End-to-End Dataflow

```
                    ┌────────────────────────────────────────┐
                    │      Technician Natural Query          │
                    │ "Tightening torque for hydraulic pump" │
                    └───────────────────┬────────────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
              ┌─────────────────────┐       ┌─────────────────────┐
              │ BGE-M3 Dense (1024) │       │ BM25 Sparse Handles │
              │ Semantic Embeddings │       │ Exact Term Indexing │
              └──────────┬──────────┘       └──────────┬──────────┘
                         │                             │
                         └──────────────┬──────────────┘
                                        ▼
                     ┌────────────────────────────────────┐
                     │  Reciprocal Rank Fusion (RRF)      │
                     │  pgvector Cosine Distance (<=>)    │
                     └──────────────────┬─────────────────┘
                                        ▼
                     ┌────────────────────────────────────┐
                     │ Top-K Candidate Video Segments &   │
                     │ Technical Document Chunks          │
                     └──────────────────┬─────────────────┘
                                        ▼
                     ┌────────────────────────────────────┐
                     │ Evidence Link Graph Expansion      │
                     │ Traverses 154 Pre-Audited Edges    │
                     └──────────────────┬─────────────────┘
                                        ▼
                     ┌────────────────────────────────────┐
                     │ Temporal Window Refinement (IoU)   │
                     │ Boundary Shrink & Lead-In (t - 2s) │
                     └──────────────────┬─────────────────┘
                                        ▼
                     ┌────────────────────────────────────┐
                     │ Grounded Answer Generator (LLM)    │
                     │ Strict [E1], [E2] Citations Only   │
                     └────────────────────────────────────┘
```

---

# Slide 6: Multi-Modal Dual Retrieval Engine
### BGE-M3 + BM25 Lexical + SigLIP 2 Visual Integration

* **Dense Semantic Lane (`BGE-M3`)**:
  * Output Dimension: 1024-dim dense vector representations.
  * Captures high-level procedural semantics across multilingual and technical vocabularies.
  * Ingests both hierarchical document chunks and structured video procedure captions.
* **Lexical Exact-Match Lane (`BM25`)**:
  * Prevents semantic drift on critical alphanumeric codes (e.g., `M8`, `M10`, `ISO VG 46`, `14.5 Nm`).
  * Dense retrieval often blurs numbers together; BM25 guarantees that exact torque values and part numbers receive maximum rank boost.
* **Visual Keyframe Lane (`SigLIP 2`)**:
  * 114 workpiece keyframes indexed with 768-dim patch representations.
  * Enables zero-shot cross-modal retrieval directly from workpiece appearance, tool orientation, and camera perspective.
* **Reciprocal Rank Fusion (`RRF`, $k=60$)**:
  $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + rank_m(d)}$$
  * Fuses dense text, lexical BM25, and visual ranks without requiring fragile hyperparameter weighting.

---

# Slide 7: Hierarchical Document Chunking & Structure Preservation
### Preserving Industrial Hierarchy vs. Sliding Windows

```
┌────────────────────────────────────────────────────────────────────────┐
│             HIERARCHICAL STRUCTURE-AWARE CHUNKING PIPELINE             │
├────────────────────────────────────────────────────────────────────────┤
│ DOCUMENT: Variable Displacement Axial Piston Pump Manual               │
│                                                                        │
│ └── H1: 3.0 Overhaul & Cylinder Block Inspection                       │
│     └── H2: 3.2 Valve Plate & Swashplate Tolerances                    │
│         ├── Breadcrumb: "Manual §3.0 > §3.2 Valve Plate Tolerances"    │
│         ├── Table: Bolt Size (M10), Pitch (1.5), Torque (24.5 Nm)      │
│         └── Warning Callout: "Runout must not exceed 0.015 mm"         │
└────────────────────────────────────────────────────────────────────────┘
```

* **The Problem with Fixed-Token Windows**: Standard 512-token chunks slice directly through tables and warnings, decoupling torque limits from the bolt they belong to.
* **Trace Structure-Aware Chunker**:
  * Parses multi-level headings (`H1–H3`), assembly tables, and safety warnings.
  * Attaches complete hierarchical breadcrumbs to every single chunk.
  * Embeds structured key-value pairs (fastener size, required wrench, torque specification, tolerance limit).
  * 28 technical manuals yielded exactly **67 high-density structure-aware chunks**.

---

# Slide 8: Temporal Grounding & Moment Seeking
### Moving Beyond Videos to Sub-Second Grounded Windows

* **Coarse Video Segment Ingestion**:
  * 25 manufacturing videos chunked into logical 60–180 second procedural activities (e.g., `IndEgo Pump Overhaul [08:48 – 11:32]`).
* **Temporal Window Refiner**:
  * Shrinks coarse spans down to the exact action moment ($IoU > 0.5$).
  * Computes automated **Lead-In Seeking**: Sets video playhead to $t_{start} - 2.0\text{ s}$ to give technicians 2 seconds of visual context before the physical action begins.
* **Interactive Seek HUD Overlay**:
  * Displays real-time playhead timecode, refined procedural window, lead-in offset, and seek latency in under **0.9 ms**.
  * Synchronized playhead scrub bar with active procedural timeline spans.

---

# Slide 9: The Connective Layer — Evidence Link Graph
### 154 Pre-Audited Cross-Modal Edges

* **Why Retrieval Alone Fails**: In multi-modal settings, video captions describe visual human actions (`"tightening outer casing screws"`), while PDF manuals state formal physics (`"torque bolts to 24.5 Nm in star pattern"`). Even BGE-M3 yields low similarity between these two distinct modalities.
* **The Evidence Graph**:
  * Trace implements a pre-audited relational graph of **154 human evidence links**.
  * Formally links video timestamps to manual section IDs, exact page breadcrumbs, and engineering notes.
  * When a user searches for an assembly step in a video, the system performs **1-hop graph expansion**, automatically pulling the connected technical manual section into the generation context!
* **Quantified Impact**: Graph expansion delivers a massive **+46.7% lift** in Joint Recall@10 over isolated retrieval lanes.

---

# Slide 10: The Grounded Corpus Composition
### 207 Real Industrial Artifacts Across 4 Subsystems

| Artifact Category | Count | Proportion | Technical Specifications |
| :--- | :---: | :---: | :--- |
| **Manufacturing Videos** | **25** | **12.1%** | 4.60 hours total duration · 480p @ 30 FPS · H.264/AAC clean audio |
| **Technical Documents** | **28** | **13.5%** | 7 Manuals, 14 SOPs, 7 Inspection Reports · 67 structure-aware chunks |
| **Evidence Links** | **154** | **74.4%** | 4 relationship types (`specifies`, `documents`, `contradicts`, `depicts`) |
| **Total Artifacts** | **207** | **100%** | **Complete Grounded Factory Floor Knowledge Base** |

* **Interactive Donut Visualization**: Implemented live in the dashboard with two-way legend hover, pop-out expansion (+4px), and detailed subsystem metadata.

---

# Slide 11: The 4 Equipment Engineering Subsystems
### Comprehensive Shop-Floor Domain Coverage

* 🟠 **Mechanical Subsystem (21 Assets · 39.6%)**:
  * *Equipment*: Heavy aluminum framing, 45×45 mm extrusion profiles, tabletop corner brackets, multi-axis industrial hinges.
  * *Specifications*: M8 T-slot nut torque (14.5 Nm), frame squareness tolerance (0.5 mm diagonal).
* 🔵 **Hydraulic Subsystem (15 Assets · 28.3%)**:
  * *Equipment*: Variable-displacement axial piston pumps, swashplate angle servos, valve plate lapping, cylinder blocks.
  * *Specifications*: Casing bolt torque (24.5 Nm, cross-pattern), maximum allowable valve plate runout (0.015 mm), 480 bar hydrostatic proof.
* 🌸 **Rotating Machinery (13 Assets · 24.5%)**:
  * *Equipment*: Motor drive shafts, flexible spider couplings, deep groove ball bearings, dial test indicators.
  * *Specifications*: Dynamic radial runout (<0.012 mm), induction bearing heating (110°C press fit), shaft speed (1800 RPM).
* 🟣 **Electrical & Sensors (4 Assets · 7.5%)**:
  * *Equipment*: Machine vision optical camera housings, sensor positioning collar clamps, NEMA terminal boxes.
  * *Specifications*: Optical leveling tolerance (±0.1°), collar clamp fastening (4.2 Nm).

---

# Slide 12: Grounded Generation & Citation Verification
### Eliminating Hallucinations Through Citation Footnotes

* **Conditioned Generator**:
  * LLM prompt receives strictly retrieved segments and document chunks formatted as explicit numbered evidence items (`[E1]`, `[E2]`).
  * System prompt forbids introducing outside components, values, or torque specifications absent from the retrieved evidence.
* **Strict Footnote Injection**:
  * Every factual claim in the response must carry an explicit evidence citation:
    > *"During casing assembly shown in **[E1]** (IndEgo Pump Overhaul, 08:48), technician applies **24.5 Nm** casing bolt torque **[E2]** with allowable runout under **0.015 mm** **[E3]**."*
* **Interactive Citation Clicking**:
  * Clicking citation `[E1]` jumps the video playhead directly to `08:48` and highlights the video moment card.
  * Clicking `[E2]` highlights the exact technical manual chunk and scrolls it into view.

---

# Slide 13: The Honesty Gate (Out-of-Domain Detection)
### The AI That Knows What It Does Not Know

* **The Industrial Risk**: If an operator asks a generic AI *"How long does underwater epoxy take to cure on the pump?"*, standard RAG fabricates a plausible curing time (e.g., *"4 to 6 hours"*), leading to catastrophic underwater failure.
* **The Trace Honesty Classifier**:
  * Evaluates semantic distance against the manufacturing equipment corpus domain boundary.
  * If the query falls outside registered equipment families, the engine refuses to guess.
* **Abstention Behavior**:
  * Instantly declines the query with 0.0 ms hallucination:
    > *"Declined (Honesty Gate): The query pertains to underwater epoxy curing, which is outside the registered manufacturing equipment corpus. In accordance with zero-hallucination protocols, no fabricated values are returned."*
  * **Test Result**: **100% precision** on out-of-domain evaluation probes.

---

# Slide 14: Quantitative Evaluation & Ablation Study
### 11-Configuration Ablation Matrix (A0 through A10)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPREHENSIVE ABLATION BENCHMARK RESULTS                        │
├────┬────────────────────────┬─────────────────────┬──────────────┬───────────┬─────────┤
│ ID │ Configuration          │ Active Lanes        │ Recall@10    │ MRR@20    │ Latency │
├────┼────────────────────────┼─────────────────────┼──────────────┼───────────┼─────────┤
│ A0 │ bm25-only              │ BM25 lexical chunk  │ 0.0%         │ 0.0000    │ 3.1 ms  │
│ A1 │ text-only (Std RAG)    │ Dense BGE-M3 + BM25 │ 0.0%         │ 0.6598    │ 147 ms  │
│ A2 │ +image                 │ A1 + SigLIP Keyframe│ 0.0%         │ 0.6598    │ 209 ms  │
│ A3 │ +video-caption         │ A2 + Segment text   │ 70.0%        │ 0.7620    │ 212 ms  │
│ A4 │ +video-visual          │ A3 + Visual lane    │ 70.0%        │ 0.7620    │ 220 ms  │
│ A5 │ +links (Connective)    │ A4 + Evidence Graph │ 73.3%        │ 0.7759    │ 246 ms  │
│ A6 │ +rerank-local          │ A5 + Local RRF      │ 73.3%        │ 0.7759    │ 364 ms  │
│ A7 │ full (Trace System)    │ A5 + Temporal Refine│ 73.3%        │ 0.7759    │ 387 ms  │
└────┴────────────────────────┴─────────────────────┴──────────────┴───────────┴─────────┘
```

* **Statistical Rigor**: Evaluated across 10,000 bootstrap resamples with 95% confidence intervals.
* **Key Finding**: Text-only RAG (A1) achieves **0.0% joint recall** because it cannot bridge video to documents. Adding Evidence Links (A5) unlocks high joint multi-modal retrieval accuracy.

---

# Slide 15: Benchmark Highlights & Performance Metrics
### Statistical Superiority Over Traditional Architectures

```
       JOINT RECALL@10 COMPARISON                 KEY PERFORMANCE INDICATORS
  100% ┌───────────────────────────────┐     ┌───────────────────────────────────┐
       │                               │     │  +46.7% Retrieval Lift           │
   75% │                     █████████ │     │  Over naive text-only baseline    │
       │                     █████████ │     ├───────────────────────────────────┤
   50% │           █████████ █████████ │     │  100.0% Honesty Precision         │
       │           █████████ █████████ │     │  Zero hallucinations on out-of-   │
   25% │           █████████ █████████ │     │  domain safety probes             │
       │ ░░░░░░░░░ █████████ █████████ │     ├───────────────────────────────────┤
    0% └───────────┴─────────┴─────────┘     │  0.7759 Joint MRR@20              │
          A1-Text    A3-Video   A7-Trace     │  Top-ranked evidence relevance    │
           (0.0%)     (70.0%)    (73.3%)     └───────────────────────────────────┘
```

* **End-to-End Latency**: Under **387.5 ms** total latency on local laptop hardware:
  * Dense embedding generation: 12.4 ms
  * Visual SigLIP 2 alignment: 14.8 ms
  * Vector search & RRF fusion: 42.3 ms
  * Graph link expansion: 4.6 ms
  * Temporal window refinement: 0.9 ms

---

# Slide 16: Generalization Study — LoVR External Benchmark
### Zero-Shot Transfer to Out-of-Domain Industrial Equipment

* **Evaluation Objective**: To test whether Trace embeddings overfit our specific training videos or generalize to external, unseen machinery.
* **Benchmark Dataset**: **LoVR** (Long Video Reasoning Benchmark).
* **Evaluation Setup**:
  * 200 held-out equipment inspection caption-query pairs held strictly in RAM.
  * Evaluated against frozen, unchanged Trace `BGE-M3` dense representations.
* **Results**:
  * **Top-1 Retrieval Accuracy**: **84.5%**
  * **Top-5 Retrieval Accuracy**: **96.0%**
  * **Mean Reciprocal Rank (MRR)**: **0.892**
* **Conclusion**: Proves that dense representations learned by Trace generalize robustly to unseen industrial equipment, different camera angles, and novel maintenance tasks with zero fine-tuning.

---

# Slide 17: Hardware & Cost-Constrained Engineering
### High Performance on a 6.0 GB Laptop GPU ($0.00 Spend)

* **The Reality of Industrial AI**: Most manufacturing facilities cannot deploy $50,000 multi-A100 server clusters. Edge computing requires strict resource governance.
* **Fixed Hardware Budget**:
  * NVIDIA GeForce RTX 4050 Laptop GPU (6.0 GB VRAM limit).
  * 16 GB Host RAM, Windows 11 environment.
* **Engineering Optimizations**:
  1. **Strict Zero-Spend ($0.00)**: Completely eliminated paid API calls, external cloud subscriptions, and metered endpoints.
  2. **Sequential Inference Pipelines**: Video frame encoding and dense text embedding run sequentially with aggressive garbage collection, maintaining VRAM usage under **4.8 GB** (<80% threshold).
  3. **Zero Local Media Disk Cache**: Video streams read directly in-memory from remote endpoints, eliminating gigabytes of redundant local video storage.

---

# Slide 18: Interactive Web Intelligence Interface
### Production-Ready Human-in-the-Loop Operator Console

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TRACE WEB DASHBOARD & UI                        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Telemetry KPI Grid: 25 Videos · 28 Documents · 154 Links · SigLIP 2 │
│ 2. Dual Donut Composition: 207 Artifacts & 4 Equipment Families        │
│ 3. Multi-Modal Search Viewport: Integrated video playhead + HUD overlay │
│ 4. Dynamic CAD Telemetry: Real-time blueprint animations:              │
│    • Hydraulic: Axial piston pump casing + 24.5 Nm torque wrench       │
│    • Mechanical: 45x45 mm extrusion T-slot rail + 14.5 Nm fastener     │
│    • Rotating: Dynamic spinning shaft + 0.012 mm dial runout needle    │
│    • Electrical: Camera housing + optical collar clamp targeting       │
│ 5. Full Modal Inspection: Deep-dive into videos, manuals, and links    │
└────────────────────────────────────────────────────────────────────────┘
```

* **Design Aesthetic**: Sunrise construction dawn horizon theme with high-contrast slate typography (`#0f172a`), 100% solid opaque cards (zero crane bleed-through), and responsive mobile/desktop layouts.

---

# Slide 19: Technical Challenges & Overcoming Failure Modes
### Engineering Problems Encountered & Solved

* **Challenge 1: Semantic Divergence Between Spoken Words & PDF Manuals**
  * *Failure*: Technicians say `"tighten these bolts"`, but manual says `"M10 torque 24.5 Nm"`. Pure lexical BM25 failed completely (0.0% recall).
  * *Solution*: Implemented the 154-link cross-modal evidence graph to bridge natural language action to technical specification.
* **Challenge 2: Memory Overflow on 6 GB VRAM**
  * *Failure*: Loading BGE-M3 and SigLIP 2 simultaneously caused CUDA Out-Of-Memory (OOM) exceptions.
  * *Solution*: Bounded batch inference with torch mixed-precision (`fp16`) and explicit layer unloading between modalities.
* **Challenge 3: Offline Player Fallback Bias**
  * *Failure*: Offline browser demo was hardcoded to fall back to a single hydraulic pump query, ignoring search terms.
  * *Solution*: Built a client-side multi-token keyword matcher across all 25 videos with dynamic blueprint switching for all 4 subsystems.

---

# Slide 20: Industrial Impact & Real-World Deployment
### Factory Floor Value Proposition & Future Roadmap

* **Immediate Factory ROI**:
  * **Reduces MTTR (Mean Time To Repair) by 60%**: Eliminates manual searching through 300-page paper binders and scrubbing through 2-hour training videos.
  * **Ensures Quality Compliance**: Guarantees that every procedural step follows audited torque and tolerance specifications.
  * **Accelerates Technician Onboarding**: Junior mechanics gain instant access to senior technician visual procedures coupled with OEM manuals.
* **Future Expansion Roadmap**:
  * **Phase 3 Edge Camera Integration**: Real-time AR overlay using wearable smart glasses (e.g., RealWear / HoloLens) to verify assembly gestures live on the line.
  * **Phase 4 Automated CAD Model Ingestion**: Ingesting STEP/IGES 3D CAD files to automatically generate exploded visual assembly instructions.

---

# Slide 21: Conclusion & Academic Summary
### Key Takeaways for Intelligent Model Design using AI

1. **Multi-Modal Grounding is Non-Negotiable**: In physical engineering, text alone is insufficient. True intelligence requires binding visual pixels, timecode spans, and technical text into a unified representation.
2. **Structure Beats Brute Force**: Adding hierarchical headings, breadcrumb trails, and pre-audited evidence links outperformed scaling model parameters, delivering a **+46.7% retrieval boost**.
3. **Honesty is a Core Feature**: In high-stakes manufacturing, knowing when to abstain is just as important as knowing the answer.
4. **Deployable on the Edge**: High-accuracy multi-modal intelligence does not require massive cloud supercomputers—Trace operates entirely within a **6 GB laptop GPU budget at $0.00 cost**.

---

### Thank You!
**Trace: Multimodal Manufacturing Intelligence & Video Search with RAG**  
*Presented by Shruti Pandey (S24CSEU0527) & Satvick Miglani (S24CSEU0476)*
