# Architectural Decision Record D6 — Interactive Evaluation & Ablation UI (/eval)

- **Status**: Settled (Built and Deployed)
- **Date**: 2026-10-25 / 2026-10-26
- **Spec Reference**: §11.2, §13.2, §19 (D6)
- **Deciders**: Platform Owner, Stakeholder Review
- **Superseding metric note (2026-11-26)**: The older lift claim below has been corrected in docs/eval-reports/final.md and /eval: +46.7 percentage points is a dev-set A7-runner vs A1 difference on Joint Recall@5, not a percentage lift, not a link-expansion result, and not held-out evidence. The old A7/A8 runner comparison does not isolate query analysis.

## Context

Spec §19 D6 posed the question: *Build the `/eval` dashboard UI? Default: Build only if Phase 6 has slack.*
In traditional RAG projects, evaluation metrics and ablation studies reside exclusively in static CLI outputs, CSV tables, or private Jupyter notebooks. This opaque format makes it difficult for non-technical stakeholders, manufacturing plant managers, and quality auditors to inspect why certain components (such as human evidence links or temporal refinement) are necessary, or to verify confidence intervals and significance test p-values.

## Decision

We chose to **BUILD AND INTEGRATE** the `/eval` Evaluation & Ablation Dashboard directly into the Trace web application.

1. **Integrated Multi-Tab Experience**:
   - Deployed at `/eval` and accessible via the top-level tab switcher alongside `Search & Seek` and `Corpus Explorer`.
   - Displays the real-time Definition of Done scorecard (`✓ ALL DOD GATES MET`).
2. **Full Ablation Matrix ($A_0$ to $A_{10}$)**:
   - Renders the complete 11-configuration ablation matrix with 10,000 bootstrap confidence intervals.
   - Shows paired hypothesis tests demonstrating that the full connective multi-modal system ($A_7$) provides a **+46.7 percentage-point dev difference** in Joint Recall@5 for A7 runner vs A1; see the 2026-11-26 superseding metric note above.
3. **Judge Calibration Transparency**:
   - Presents LLM-judge calibration metrics (93.3% agreement with human ground-truth, Cohen's $\kappa = 0.8667 \ge 0.70$) directly to the auditor.
4. **Standalone Portability**:
   - Pre-compiled telemetry data is embedded directly into the frontend, enabling offline stakeholder review without requiring live database or GPU connections.

## Consequences

- Auditing and compliance reviews can be conducted live in executive demonstrations.
- The UI satisfies Spec §11.2 and Spec §18 Checklist Item 11.
