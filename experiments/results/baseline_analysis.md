# LIMEN Phase 3 baseline analysis

- Observations: 200
- Baselines: spectral-only, image-only, and equalized multimodal Isolation Forest.
- Scores are relative ranking values, not probabilities and not discovery claims.
- Feature contribution: Isolation Forest offers no defensible per-object causal attribution here. The retained feature lists are recorded in `baseline_results.json`; score/rank stability is reported instead.

## Top-20 overlap

- spectral_image: 1
- spectral_multimodal: 9
- image_multimodal: 12
- all_three: 1

## Rank correlation (Spearman)

- spectral_image: -0.180
- spectral_multimodal: 0.697
- image_multimodal: 0.406

## Sensitivity

- spectral, n_estimators_100_spearman_rank_correlation: 0.978 rank correlation with the 300-tree reference
- spectral, n_estimators_500_spearman_rank_correlation: 0.996 rank correlation with the 300-tree reference
- image, n_estimators_100_spearman_rank_correlation: 0.990 rank correlation with the 300-tree reference
- image, n_estimators_500_spearman_rank_correlation: 0.998 rank correlation with the 300-tree reference

## Limits

- Anomaly scores are relative rankings within 200 GALAXY-classified DESI DR1 records, not probabilities or discoveries.
- The sample is small, selected, and not representative of all DESI populations.
- Image concentration and asymmetry are morphology proxies, not morphology classifications.
- Spectral model residual features describe model discrepancy only; they do not establish physical-model failure.
- Isolation Forest does not yield defensible per-object causal feature attribution; retained feature lists and sensitivity checks are diagnostics, not explanations.
