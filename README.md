# LIMEN

LIMEN investigates evidence-aware prioritisation of astronomical outliers. It is a reproducible, small-pilot research workflow built from 200 real DESI DR1 observations catalogue-classified as `GALAXY` and corresponding Legacy Surveys DR10 optical cutouts.

The completed workflow covers:

- Reproducible DESI/SPARCL and Legacy Survey ingestion with provenance and failure recording.
- Spectral/image quality characterisation and dataset audit.
- Spectral-only, image-only, and equalized multimodal Isolation Forest baselines.
- Mask-aware evidence interrogation, DESI `ZWARN` decoding, and controlled degradation experiments.
- Transparent, rule-based evidence-aware triage for the 39-candidate investigation set.

It does **not** claim discoveries, anomaly probabilities, physical-model failures, independent cross-survey confirmation, morphology classifications, or generalisation beyond this small, selected pilot. Phase 6 triage categories are investigation-workflow labels, not a numeric priority score.

## Setup and run

Use Python 3.10 or newer. From this directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python -m backend.ingestion.run --count 200
```

Optional network settings are documented in `.env.example`. The public pilot does not require credentials. Environment variables are read directly by the script; source your environment file in your shell if you use one.

The run is incremental: successfully stored `data/raw/desi_dr1/spectra/<specid>.npz` files and `data/raw/legacy_survey_dr10/images/<specid>.fits` files are retained, while the status manifest and report are regenerated. Re-running does not fabricate a replacement when a record or image is unavailable.

## Outputs

- `data/raw/desi_dr1/spectra/`: compressed arrays returned by SPARCL.
- `data/raw/legacy_survey_dr10/images/`: small (64-pixel default) real DR10 FITS cutouts.
- `data/metadata/observations.jsonl`: one provenance and retrieval-status record per selected SPARCL record.
- `data/metadata/ingestion_report.json` and `.md`: aggregate results, failures, timestamps, and source endpoints.

## Retained fields

| Field | Why it is retained |
| --- | --- |
| `specid`, `sparcl_id`, `targetid` | Stable service, spectrum, and DESI target identifiers for traceability. |
| `ra`, `dec` | ICRS sky position used for the corresponding cutout request. |
| `spectype`, `specprimary` | Catalogue classification and primary-spectrum context; they are selection metadata, not a new classification. |
| `redshift`, `redshift_err`, `redshift_warning` | Available DESI redshift context and quality warning, retained without asserting its validity. |
| `wavelength`, `flux` | Spectral coordinate and calibrated flux samples needed for later controlled analysis. |
| `ivar`, `mask` | Uncertainty weighting and pixel-quality information; masks are retained rather than silently filtering samples. |
| `model` | If supplied by SPARCL, retained only for later *spectral model discrepancy* analysis with its quality context. It is not treated as proof of physical-model failure. |
| Status, paths, URL, failure reason, timestamps | Enables retrying, auditing missing modalities, and exact provenance. |

## Data access and limitations

DESI DR1 is accessed through the public [NOIRLab SPARCL service](https://datalab.noirlab.edu/data/desi), using the `sparclclient` Python package. SPARCL currently serves HEALPixel coadds, so this is not an exposure-level retrieval. Legacy Survey images come from the official [DR10 cutout service](https://www.legacysurvey.org/dr10/description/), which limits cutouts to 512 pixels and may return unavailable or service-error responses for some coordinates. The pipeline stores those failures explicitly.

Legacy Survey imagery is cross-survey consistency evidence only; it does not independently confirm a DESI observation. A 200-object convenience pilot is not assumed to contain rare or genuine anomalies.

## Interactive observatory

The research UI is a local Next.js application in `frontend/`. It reads the existing experiment outputs through local API routes and fetches only the selected candidate's derived display data and FITS-derived image preview. The raw 200-object NPZ/FITS corpus is not included in the browser bundle.

```bash
cd frontend
npm install
npm run dev
```

Before the first UI run, create the lightweight, derived assets from the existing files:

```bash
.venv/bin/python -m backend.api.export_frontend
```

Run `npm test` for frontend data-selection tests and `npm run build` for the production build. The observatory's 3D scene is an RA/Dec projection on a unit sphere, not a physical spatial reconstruction. All anomaly scores remain the existing relative Phase 3 scores; Phase 6 triage categories are rule-based workflow labels, not a replacement priority ranking.
