# LIMEN Phase 5 controlled robustness report

- Observations per scenario: 200
- Perturbed model runs: 48.
- Phase 3 model hyperparameters and original rankings are the fixed reference.
- Missing modalities are explicitly unavailable and are never zero-filled.

## Median stability by scenario and baseline

- spectral_noise / spectral: median Spearman 0.861; median top-20 retention 12.0/20
- spectral_noise / multimodal: median Spearman 0.895; median top-20 retention 14.5/20
- spectral_mask / spectral: median Spearman 0.911; median top-20 retention 13.5/20
- spectral_mask / multimodal: median Spearman 0.935; median top-20 retention 16.0/20
- spectral_coverage / spectral: median Spearman 0.937; median top-20 retention 16.0/20
- spectral_coverage / multimodal: median Spearman 0.949; median top-20 retention 18.5/20
- image_noise / image: median Spearman 0.978; median top-20 retention 18.5/20
- image_noise / multimodal: median Spearman 0.992; median top-20 retention 19.5/20
- image_blur / image: median Spearman 0.939; median top-20 retention 19.5/20
- image_blur / multimodal: median Spearman 0.987; median top-20 retention 19.0/20
- image_mask / image: median Spearman 0.937; median top-20 retention 17.5/20
- image_mask / multimodal: median Spearman 0.973; median top-20 retention 18.0/20

## Refitting sensitivity

Every degraded run refits Isolation Forest, imputation, and scaling using fixed Phase 3 hyperparameters and seed. Fitted Phase 3 preprocessing objects were not persisted, so this is refit-pipeline sensitivity rather than frozen-model robustness.

## Limits

- These controlled perturbations do not represent every telescope, reduction, calibration, or astrophysical failure mode.
- Stability is not scientific accuracy.
- Models are refit with fixed Phase 3 hyperparameters so results measure the pipeline response to degraded inputs, not inference under a frozen training population.
- No raw FITS/NPZ input was modified and Phase 3 outputs were not overwritten.
