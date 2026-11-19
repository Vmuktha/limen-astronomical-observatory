# Investigation 001 – Image Evidence for Candidate 39627837216396200

## A. Image provenance & preprocessing
- **Original image file**: `data/raw/legacy_survey_dr10/images/39627837216396200.fits` (referenced in `experiments/results/evidence/dossiers/39627837216396200.json`).
- **Survey / Release**: Legacy Survey DR10, cutout size 64 × 64 px, bands **g, r, z**.
- **Pre‑processing pipeline**:
  1. FITS cutout loaded.
  2. Invalid‑pixel mask applied (none flagged – `image_invalid_fraction = 0.0`).
  3. Per‑band statistics computed (median, MAD, percentiles).
  4. Proxy metrics derived in `backend/preprocessing/basaseline_features.py`:
     - `image_snr_proxy_median`
     - `image_concentration_proxy_median`
     - `asymmetry_proxy_median`
  5. Features assembled for the Isolation‑Forest image detector (`backend/anomaly/basaselines.py`).

## B. Feature extraction & detector input
The image detector consumes **four** proxy features plus the spectral `valid_pixel_fraction`:
| Feature                         | Description                               |
|--------------------------------|-------------------------------------------|
| `image_invalid_fraction`       | Fraction of masked pixels (0 = none).      |
| `image_snr_proxy_median`       | Median signal‑to‑noise proxy across bands.
| `image_concentration_proxy_median` | Compactness of light distribution (higher = more concentrated). |
| `asymmetry_proxy_median`       | Rotational asymmetry metric (higher = more asymmetric).
| `spectral_valid_pixel_fraction`| Fraction of valid spectral pixels (from spectral pipeline).

These values are stored in the dossier under `image_evidence.quality_and_proxy_metrics` and also appear in `experiments/results/image_features.csv`.

## C. Feature values (primary vs. controls)
| SpecID | img_asymmetry | img_concentration | img_snr_proxy | img_invalid_fraction |
|--------|--------------|-------------------|---------------|----------------------|
| **39627837216396200** (primary) | **1.45** | **0.91** | **15.39** | 0.0 |
| 39627785035058811 (control A) | 0.65 | 0.71 | 2.80 | 0.0 |
| 39627646971152189 (control B) | 0.36 | 0.85 | 4.74 | 0.0 |
| 39627805914306114 (control C) | 0.61 | 0.77 | 1.83 | 0.0 |

*All values are taken directly from `image_features.csv` (columns `img_asymmetry_proxy_median`, `img_concentration_proxy_median`, `img_snr_proxy_median`) and corroborated by the dossier JSON (`quality_and_proxy_metrics`).*

## D. Visual diagnostics
The full 64 × 64 px cutout used by the detector is saved as a PNG:

![Primary image plot](file:///Users/vimuktha/Desktop/LIMEN/experiments/results/candidate_investigation/39627837216396200/plots/39627837216396200.png)

The plot shows the g‑r‑z composite used for visual inspection. No obvious artefacts or saturation are present; the object appears centrally located with a bright core and modest extended halo.

## E. Evidence summary & interpretation
- The primary candidate exhibits **exceptionally high image asymmetry (1.45)** compared with the three reference controls (0.36‑0.65). This suggests a disturbed morphology (possible merger or tidal feature).
- **Concentration (0.91)** is also higher than all controls, indicating a very compact light profile.
- **Image S/N proxy (15.4)** is markedly larger than the controls (1.8‑4.7), meaning the detector receives a high‑quality, low‑noise image.
- All four proxy metrics are **within valid ranges** (no masked pixels), so the detector’s high image rank (2) is driven by genuine morphological atypicality rather than data quality issues.
- Spectral rank (43) is modest; the anomaly is therefore **image‑dominated**, consistent with the dossier field `modality_relationship = "Image-dominated"`.
- No redshift‑warning flags are set, and the spectrum is usable (`spectral_valid_pixel_fraction = 0.997`).
- Potential alternative explanations (e.g., data processing artefacts) are unlikely given the clean mask and high S/N.

## F. Assessment label
- **Detector‑ranked statistical outlier candidate**
- **Image‑feature unusualness supported**
- **Observationally robust (no quality concerns)**

---
*Report generated automatically from existing LIMEN artefacts (read‑only, no recomputation).*