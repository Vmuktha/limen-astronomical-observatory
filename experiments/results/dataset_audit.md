# LIMEN Phase 2 dataset audit

## Inventory and integrity

- Manifested / characterized: 200 / 200
- Spectral arrays: flux;ivar;mask;model;wavelength
- Spectral sample count (all files): 7781.0
- Image bands and shape: grz; 3.0 × 64.0 × 64.0
- Spectral / image read errors: 0 / 0
- Unique specids / valid coordinates / duplicate coordinates: 200 / 200 / 0

## Population and quality summaries

- Redshift (finite n, median, range): 200, 0.5759, [0.0262, 1.6963]
- Spectral |S/N| 90th-percentile statistic (finite n, median): 196, 3.4161; it is unavailable for 4 records with no valid unmasked positive-ivar samples.
- Wavelength grid: 3600.0–9824.0 Angstrom; median spacing 0.800 Angstrom.
- Masked-pixel fraction (median, range): 0.00353, [0.00000, 0.01786]
- Positive inverse-variance fraction (median): 0.99621
- Finite model coverage: 1.000; residual metrics are retained only as spectral model discrepancy fields.
- Image invalid-pixel fraction (median): 0.000; central-versus-background S/N proxy median: 0.5711

## Feature checks

- Constant features: spectral_samples, wavelength_min_angstrom, wavelength_max_angstrom, wavelength_spacing_median_angstrom, model_finite_fraction, image_invalid_fraction; exclude these from any initial feature matrix.
- High-correlation pairs (|r| ≥ 0.98): 1; inspect the JSON audit before using both members of a pair.

## Suitability and next sample

Suitable for a controlled preliminary multimodal pipeline check, but 200 GALAXY-selected records are too small and selection-biased for general anomaly claims. For the next stage, target 2,000–5,000 observations selected in strata of redshift, target program, sky position, signal-to-noise, and spectype; retain quality failures rather than filtering them away.

Initial modelling candidates: quality-aware spectral flux summaries or normalized spectra, valid-ivar S/N, mask fraction, redshift context, and cautiously scaled image quality/proxy features. Exclude constant wavelength-grid fields and image-invalid fraction here; do not impute unavailable S/N or quality values as zero.

## Interpretation limits

DESI DR1 records catalogue-classified as GALAXY with available DR10 grz cutouts; not representative of all DESI observations.
Image S/N, concentration, and asymmetry are simple quality/morphology proxies, not galaxy morphology classifications.
Model residual fields describe spectral model discrepancy only and are not evidence of physical-model failure.
