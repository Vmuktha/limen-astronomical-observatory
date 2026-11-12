# LIMEN Phase 6 triage methodology

## Design

This is a rule-based investigation workflow. It deliberately produces categories and reasons, not a weighted score, priority number, probability, or discovery assertion.

## Rules

- **insufficient_evidence** — Spectral valid-pixel fraction is below 0.50, S/N is unavailable, or image invalid-pixel fraction is at least 0.25.
- **multimodal_agreement** — Both original Phase 3 spectral and image ranks are in their top 20 and evidence is not insufficient.
- **evidence_sensitive** — For a modality that originally ranked in the top 20, fewer than half of its applicable controlled degradation runs retain top-20 membership, or median absolute rank displacement is at least 25. This is refit-pipeline sensitivity, not a quality score.
- **spectral_candidate** — Original Phase 3 spectral rank is in the top 20, with sufficient evidence and without the evidence-sensitive rule.
- **image_candidate** — Original Phase 3 image rank is in the top 20, with sufficient evidence and without the evidence-sensitive rule.

## Evidence safeguards

- Original Phase 3 scores and rankings are copied unchanged.
- ZWARN is retained as an integer and decoded flags; it is not collapsed into a generic quality score.
- Model discrepancy is included once as mask-aware residual context and is never called physical-model failure.
- Robustness records are refit-pipeline sensitivity under controlled degradation, not frozen-model robustness or scientific accuracy.
- A missing modality has no multimodal score; it is never substituted with zeros.
- Legacy Survey comparison is cross-survey consistency evidence, not independent confirmation.
