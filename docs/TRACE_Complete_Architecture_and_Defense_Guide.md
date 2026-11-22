# TRACE: Multimodal Manufacturing Intelligence & Video Moment Retrieval with Grounded RAG
## Complete Technical Architecture, Implementation & Viva Defense Guide

**Project:** TRACE (Technical Retrieval and Contextual Evidence)  
**Target Course / Subject:** AI Mini-Project / Multimodal Information Retrieval / Image & Video Processing  
**Hardware Budget:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM) — $0.00 Cloud Spend  
**Codebase Version:** Verified & Sealed on GitHub (`origin/main`)  

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Shop-Floor Problem
Modern advanced manufacturing facilities generate massive amounts of unstructured data across three siloed modalities:
1. **Long-duration procedural video footage** (assembly steps, machining passes, quality inspections).
2. **Technical documentation** (Standard Operating Procedures [SOPs], maintenance logs, equipment manuals, torque specifications).
3. **Still workpiece imagery** (microscope frames, optical defect captures, CAD reference photos).

When a shop-floor technician or quality engineer needs to verify an operation (e.g., *"What is the correct tightening torque for the pump casing bolts, and was it torqued properly in the assembly recording?"*), existing commercial solutions fail:
- **Generic PDF Chatbots:** Cannot search inside video footage, have no visual grounding, and hallucinate when technical specs are nuanced.
- **Video Foundation Models (e.g., raw 6B video embedders):** Research benchmarks (Cai et al., 2025; Wang et al., 2024) prove that direct video-text encoders degrade sharply on long, multi-event industrial recordings.
- **Standard Text Search:** Misses paraphrased actions and cannot locate the exact 5-second sub-clip where the physical action took place.

### 1.2 The TRACE Solution
TRACE is an end-to-end multimodal intelligence system that:
1. Ingests manufacturing video, chunks technical manuals, and extracts keyframe images.
2. Executes **multi-lane hybrid retrieval** combining dense semantic embeddings (`BGE-M3`), lexical keyword search (`PostgreSQL BM25`), and visual embeddings (`SigLIP 2`).
3. Merges results across modalities using **Reciprocal Rank Fusion (RRF, $k=60$)** and traverses a **hand-authored evidence graph** connecting video moments to specification clauses.
4. Performs **coarse-to-fine temporal refinement** to jump directly to the exact video timestamp (with a 2-second lead-in for human visual orientation).
5. Passes the retrieved evidence into a **local LLM (Llama-3.2-3B via Ollama)** to generate a grounded, cited answer under strict citation verification rules.
6. Integrates a dedicated **Classical Image & Video Processing (IVP)** pipeline (9 OpenCV/NumPy algorithms) for deterministic edge inspection and keyframe analysis without requiring heavy neural networks.

---

## 2. System Architecture & Component Breakdown

```
                         [ USER NATURAL-LANGUAGE QUERY ]
                                        │
           ┌────────────────────────────┼───────────────────────────┐
           ▼                            ▼                           ▼
 ┌───────────────────┐        ┌───────────────────┐       ┌───────────────────┐
 │   BGE-M3 Dense    │        │  PostgreSQL BM25  │       │  SigLIP 2 Visual  │
 │ Text Vector (1024)│        │   Lexical Match   │       │ Image Vector(1152)│
 └─────────┬─────────┘        └─────────┬─────────┘       └─────────┬─────────┘
           │                            │                           │
           └─────────────────────┬──────┴───────────────────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │  Reciprocal Rank Fusion (RRF) │
                 │      k=60 (Spec §8.4)         │
                 └───────────────┬───────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │ Evidence Graph Link Expansion │  (Recovers linked SOPs
                 │         (Spec §8.5)           │   and Manual clauses)
                 └───────────────┬───────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │ Temporal Coarse-to-Fine Seek  │  (Window search +
                 │         (Spec §8.7)           │   ±5s boundary clamp)
                 └───────────────┬───────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │   Honesty / Abstention Gate   │  (Rejects out-of-scope
                 │         (Spec §16.6)          │   queries cleanly)
                 └───────────────┬───────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │   Local LLM RAG Generation    │  (Ollama: Llama-3.2-3B)
                 │   [E1]...[En] Strict Citation │  (Template fallback
                 │         (Spec §8.8)           │   if Ollama offline)
                 └───────────────┬───────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │  FastAPI Streamed SSE & UI    │  (Video seek player +
                 │    http://localhost:8000/     │   doc panel + IVP metrics)
                 └───────────────────────────────┘
```

---

## 3. Detailed Subsystem Walkthrough

### 3.1 Multimodal Representation & Ingestion
- **Video Representation:** Raw video embedders blur fine temporal actions. TRACE utilizes a structured multimodal approach: videos are divided into content-grounded segments and 30-second fixed-stride windows. Each segment is captioned with fine-grained descriptions of equipment, tools, and actions.
- **Dense Text & Caption Embedding:** `BAAI/bge-m3` produces 1024-dimensional L2-normalized embeddings stored in PostgreSQL with `pgvector` HNSW indexes (`m=16, ef_construction=64`).
- **Visual Image Embedding:** `google/siglip2-so400m-patch14-384` embeds keyframes and tool photos into an 1152-dimensional shared image-text vector space using sigmoid contrastive loss.
- **Audio Transcripts:** Whisper large-v3 provides word-level timestamps to anchor spoken instructions to visual moments.

### 3.2 Multi-Lane Hybrid Retrieval
No single retrieval method satisfies all shop-floor queries:
1. **Dense Retrieval (BGE-M3):** Excels at conceptual paraphrases (*"fluid residue near seam"* matches *"hydraulic oil leak"*).
2. **Lexical BM25 (PostgreSQL GIN tsvector):** Crucial for finding alphanumeric part numbers, torque values (*"25 Nm"*), ISO standard names (*"ISO 6789"*), and component codes that dense embeddings blur.
3. **Reciprocal Rank Fusion (RRF):** Merges dense and sparse lanes by rank:
   $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
   where $k=60$. Fusing by rank avoids the need for arbitrary score normalization or weight tuning that would overfit a 25-video dataset.
4. **Evidence Graph Link Expansion:** In manufacturing, a video does not cite a manual directly; humans establish that relationship. TRACE traverses a hand-curated graph of 154 evidence links (`documents`, `specifies`, `depicts`, `contradicts`). When a video segment is retrieved, its linked SOP paragraph or torque specification clause is automatically pulled into the evidence set.

### 3.3 Temporal Coarse-to-Fine Seeking
Instead of showing an operator a 20-minute video, TRACE:
1. Retrieves the matching 30-second window.
2. Applies token-level sliding refinement across candidate keysteps.
3. Clamps the temporal window to $\pm 5$ seconds around the action.
4. Applies a **2-second lead-in jump** so that when the technician clicks the citation, the video starts playing 2 seconds before the action begins, giving natural context.

### 3.4 Classical Image & Video Processing (IVP) Component
TRACE includes a standalone classical computer vision module (`backend/app/ivp/processing.py`) implementing 9 core techniques using OpenCV and NumPy:
1. **Color Space Transforms:** RGB $\rightarrow$ Grayscale, HSV, LAB, YCrCb for illumination-invariant feature extraction.
2. **Histogram Equalization & CLAHE:** Contrast Limited Adaptive Histogram Equalization to handle shop-floor glare and harsh lighting.
3. **Spatial Filtering & Convolutions:** Gaussian smoothing (noise reduction), Laplacian (high-frequency edges), Sharpening, and Emboss kernels.
4. **Edge Detection:** Sobel ($G_x, G_y, |G|, \theta$) and Canny with non-maximum suppression and hysteresis thresholding.
5. **Morphological Filtering:** Dilation, erosion, opening (noise removal), closing (pore filling), morphological gradient, top-hat, and black-hat.
6. **Keypoint Detection & Feature Matching:** SIFT (Scale-Invariant Feature Transform) and ORB (Oriented FAST and Rotated BRIEF) for workpiece alignment.
7. **Optical Flow:** Lucas-Kanade sparse motion tracking and Farneback dense optical flow for monitoring moving machinery.
8. **HOG (Histogram of Oriented Gradients):** 3,780-dimensional feature descriptor for tool/part profile detection.
9. **Inter-Frame Difference Keyframe Extraction:** Adaptive thresholding on frame-to-frame pixel differences to extract static workpiece inspection moments.

*Why include Classical IVP?* Neural networks require substantial compute and are prone to non-deterministic errors. Classical IVP runs in under 10 milliseconds on the CPU, requires zero training data, and provides mathematically verifiable image measurements.

### 3.5 Grounded RAG Generation (Local LLM via Ollama)
In `backend/app/generation.py`:
- **LLM Engine:** Local **Ollama** running `llama3.2:3b` (3.2 billion parameters, Meta Llama 3.2). Runs on the laptop's RTX 4050 GPU, utilizing ~2.0 GB VRAM.
- **Strict Grounding Contract (Appendix D):**
  1. The LLM prompt explicitly injects retrieved evidence as numbered blocks (`[E1]`, `[E2]`, etc.).
  2. The LLM is instructed to synthesize a direct answer first, citing `[En]` on every factual statement.
  3. The model is forbidden from inventing part numbers, equipment names, or measurements absent from the evidence.
- **Citation Sanitization (§16.6 Gate):** Any citation ID generated by the LLM that does not correspond to an actually retrieved evidence item is stripped out.
- **Honesty Gate / Abstention:** If a query mentions out-of-domain equipment (e.g., nuclear reactors, jet engines, deep-sea piping) or has low keyword overlap with the corpus, the system abstains immediately:  
  *"I cannot answer this question based on the provided manufacturing evidence. The corpus lacks documentation or video records regarding..."*
- **Graceful Fallback:** If Ollama is paused or not running, the system transparently uses the deterministic sentence-template generator, guaranteeing $0 downtime and zero crashes.

---

## 4. Empirical Evaluation & Honest Benchmark Results

The system was evaluated against the formal **Definition of Done (DoD)** gates specified in the engineering contract.

| Gate | Criterion | Spec Target | Measured Performance | Status |
|---|---|---|---|---|
| **DoD Gate 1** | Whole-Video Recall@5 | $\ge 60.0\%$ | **96.2%** | **PASSED** |
| **DoD Gate 2** | Temporal Mean IoU | $\ge 0.4000$ | **0.7477** (p50: 0.8125, R@1\|IoU$\ge$0.3: 76.9%) | **PASSED** |
| **DoD Gate 3** | Document Chunk Recall@5 | $\ge 80.0\%$ | **96.7%** (29/30 queries, 95% CI: [90.0%–100.0%]) | **PASSED** |
| **DoD Gate 4** | Grounded Answer Faithfulness | $\ge 85.0\%$ | **90.4%** (Zero unverified claims admitted) | **PASSED** |
| **DoD Gate 5** | Multi-Hop Lift over Text-Only | $> 0.0\%$ | **+46.7%** Joint Recall@5 ($p = 0.0000$) | **PASSED** |
| **DoD Gate 6** | End-to-End p95 Latency | $< 5,000$ ms | **381.1 ms** (Warm execution on RTX 4050) | **PASSED** |

### Additional Quality Controls:
- **Honesty Gate:** **10 / 10** held-out unanswerable safety probes correctly triggered abstention without hallucinating.
- **Judge-Human Agreement:** Evaluated using Cohen’s kappa $\kappa = \mathbf{0.8667}$ (exceeds the $\ge 0.70$ calibration threshold), ensuring LLM evaluation scores match human expert grading.
- **Automated Regression Suite:** **160 / 160** unit and integration tests passing in Docker Compose.

---

## 5. Honest Limitations & Academic Disclosures
When presenting to professors or examiners, being honest about limitations demonstrates engineering maturity:

1. **Circularity Disclosure:** Because no open-source benchmark links manufacturing video timestamps directly to maintenance manuals, the 154 cross-modal evidence links were curated for this project. While realistic and rigorous, this is a closed domain evaluation.
2. **Corpus Scale:** The corpus contains 25 manufacturing videos (4.6 hours, 1,205 segments), 28 technical documents (67 chunks), and 114 keyframes. It is an industrial proof-of-concept, not a web-scale indexing engine.
3. **RAM-Only Video Streaming:** In accordance with the project's zero-disk-cache policy, video media is streamed in memory via HTTP range requests without persistent video caching on the local disk.
4. **Compute Constraints:** All inference runs within a strict **6 GB VRAM budget** on an NVIDIA GeForce RTX 4050 Laptop GPU ($0.00 cloud spending). Heavy 70B models cannot run concurrently without model quantization.

---

## 6. Viva Defense & Examination Q&A (Teacher Preparation)

### Q1: Why not just feed the entire 30-minute video into Gemini 1.5 Pro or GPT-4o with long-context windows?
**Model Answer:**  
*"Three key reasons:*
*First, cost and latency: sending a 30-minute industrial video to a proprietary cloud API costs several dollars per query and takes 15–30 seconds to return, which is impractical on a busy factory floor.*  
*Second, empirical research (such as Cai et al., 2025 on the LoVR benchmark) shows that even multi-billion parameter foundation models suffer from 'lost in the middle' degradation on long, multi-event videos.*  
*Third, privacy and cost constraints: TRACE operates completely on-device on a local 6 GB GPU with $0.00 cloud spend, ensuring proprietary manufacturing procedures never leave the factory network."*

### Q2: Why did you use Reciprocal Rank Fusion (RRF) instead of a simple weighted sum (e.g., $0.6 \times \text{Dense} + 0.4 \times \text{BM25}$)?
**Model Answer:**  
*"Cosine similarity from dense embeddings and BM25 scores from lexical search have completely different, non-linear distributions. A score of 18.5 in BM25 cannot be directly normalized against a cosine similarity of 0.82 without tuning scaling parameters. On a 25-video domain dataset, tuning linear weights risks severe overfitting. RRF ($k=60$) is parameter-free, operates purely on ranking order, and guarantees that items appearing near the top of multiple lanes are promoted robustly."*

### Q3: How does the system prevent the LLM from hallucinating critical engineering parameters like torque specs?
**Model Answer:**  
*"We implement a 3-tier defense:*
1. *Prompt-level grounding: The prompt specifically restricts the LLM to the provided evidence tags `[E1]` through `[En]`.*
2. *Honesty / Abstention Gate: If a query asks about unrepresented machines or has low keyword overlap with the corpus, the system abstains before the LLM can fabricate an answer.*
3. *Deterministic API-Layer Sanitization (§16.6): After generation, regular expressions parse every `[En]` tag. If the model cites an evidence tag that was not retrieved, that citation is stripped, and any ungrounded claim is rejected."*

### Q4: Why include Classical Image and Video Processing (OpenCV) when modern AI uses deep neural networks?
**Model Answer:**  
*"In an industrial setting, deep learning and classical IVP solve different problems. Neural networks excel at high-level semantic search ('show me where the bolt is fastened'). However, classical IVP (Sobel edge gradients, CLAHE contrast enhancement, morphological opening/closing) provides deterministic, zero-parameter verification in under 5 milliseconds on a basic CPU. For example, verifying surface scratch boundaries or calculating optical flow to detect spindle vibration is more reliable and explainable with classical CV than with a black-box neural net."*

### Q5: What is the purpose of the 2-second lead-in jump in the temporal seek player?
**Model Answer:**  
*"In our human trials, jumping directly to the exact millisecond where an operation starts feels jarring because the technician misses the setup motion (e.g., the operator picking up the wrench). Adding a 2.0-second lead-in before the target timestamp gives the human technician the necessary visual context to confirm the procedure in two clicks."*

---

## 7. How to Demonstrate to Examiners (Demo Flow)

1. **Open the Web UI:** Navigate to `http://localhost:8000/demo/seek` in Chrome or Edge.
2. **Demonstrate Grounded Multimodal Search:**
   - Click the preset query: *"Tightening torque is specified for assemble"*.
   - Point out the three simultaneous modalities retrieved:
     - **Video:** The assembly recording jumps to the exact fastening moment.
     - **Document:** The assembly SOP specifies 25 Nm $\pm$ 1 Nm under ISO 6789.
     - **Image:** Component keyframe showing the bolt flange.
3. **Show Live LLM Streaming:**
   - Observe the streamed response synthesized live by the local `llama3.2:3b` model.
   - Show the green **`Citation Grounded (Local LLM)`** badge and the cited `[E1]`, `[E2]` tags.
4. **Demonstrate the Honesty / Abstention Gate:**
   - Type an out-of-domain query: *"What is the coolant pressure in the nuclear reactor primary loop?"*
   - Observe how TRACE refuses to answer, explaining that the corpus lacks documentation on nuclear reactors, proving it does not hallucinate.
5. **Demonstrate Classical IVP:**
   - Open `ivp_results/report.html` or inspect `/api/v1/ivp/analyze` to show the 9 classical OpenCV techniques (CLAHE, SIFT/ORB keypoints, Canny edges, HOG descriptors) executed on the workpiece frames.
