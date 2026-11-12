from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits

from backend.ingestion.validation import valid_coordinates
from backend.quality.metrics import image_metrics, spectral_metrics


NUMERIC_FEATURES = [
    "redshift", "redshift_warning", "spectral_samples", "wavelength_min_angstrom", "wavelength_max_angstrom",
    "wavelength_spacing_median_angstrom", "flux_median", "flux_mad", "flux_p05", "flux_p95", "ivar_positive_fraction",
    "mask_nonzero_fraction", "snr_median", "snr_p90_abs", "model_finite_fraction", "residual_mad", "residual_rms",
    "image_invalid_fraction", "background_noise_mad", "image_snr_proxy_median", "concentration_proxy_median", "asymmetry_proxy_median",
]


def _finite_summary(values: list[Any]) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if not array.size:
        return {"count": 0, "min": None, "median": None, "max": None, "mean": None, "mad": None}
    median = np.median(array)
    return {"count": int(array.size), "min": float(np.min(array)), "median": float(median), "max": float(np.max(array)), "mean": float(np.mean(array)), "mad": float(np.median(np.abs(array - median)))}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def characterize_observation(metadata: dict[str, Any], root: Path) -> dict[str, Any]:
    """Read one spectrum and one image; record errors rather than invent values."""
    row = {key: metadata.get(key) for key in ("specid", "targetid", "sparcl_id", "ra_deg", "dec_deg", "spectype", "redshift", "redshift_warning")}
    row["coordinates_valid"] = valid_coordinates(row["ra_deg"], row["dec_deg"])
    row["spectral_error"] = None
    row["image_error"] = None
    spectrum_path = root / str(metadata.get("spectrum_path", ""))
    try:
        with np.load(spectrum_path) as spectrum:
            row["spectral_arrays"] = ";".join(sorted(spectrum.files))
            row.update(spectral_metrics(spectrum["wavelength"], spectrum["flux"], spectrum.get("ivar"), spectrum.get("mask"), spectrum.get("model")))
    except (OSError, KeyError, ValueError, TypeError) as exc:
        row["spectral_error"] = f"{type(exc).__name__}: {exc}"
    image_path = root / str(metadata.get("image_path", ""))
    try:
        with fits.open(image_path, memmap=False, lazy_load_hdus=False) as hdus:
            hdus.verify("exception")
            primary = hdus[0]
            if primary.data is None:
                raise ValueError("primary FITS image has no data")
            row["image_bands"] = str(primary.header.get("BANDS", "")) or None
            row.update(image_metrics(primary.data))
    except (OSError, EOFError, ValueError, TypeError) as exc:
        row["image_error"] = f"{type(exc).__name__}: {exc}"
    return row


def _feature_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {"constant_features": [], "highly_correlated_pairs": [], "missing_fraction": {}}
    feature_data: dict[str, np.ndarray] = {}
    for feature in NUMERIC_FEATURES:
        values = np.asarray([row.get(feature, np.nan) for row in rows], dtype=float)
        finite = np.isfinite(values)
        diagnostics["missing_fraction"][feature] = float(1 - np.mean(finite))
        if np.count_nonzero(finite) and np.nanmax(values[finite]) == np.nanmin(values[finite]):
            diagnostics["constant_features"].append(feature)
        feature_data[feature] = values
    for index, left in enumerate(NUMERIC_FEATURES):
        for right in NUMERIC_FEATURES[index + 1 :]:
            valid = np.isfinite(feature_data[left]) & np.isfinite(feature_data[right])
            if np.count_nonzero(valid) < 10:
                continue
            left_values, right_values = feature_data[left][valid], feature_data[right][valid]
            if np.std(left_values) == 0 or np.std(right_values) == 0:
                continue
            correlation = float(np.corrcoef(left_values, right_values)[0, 1])
            if np.isfinite(correlation) and abs(correlation) >= 0.98:
                diagnostics["highly_correlated_pairs"].append({"left": left, "right": right, "pearson_r": correlation})
    return diagnostics


def _write_plots(rows: list[dict[str, Any]], output_dir: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    features = [("redshift", "Redshift"), ("snr_p90_abs", "Spectral |S/N| 90th percentile"), ("mask_nonzero_fraction", "Spectral masked fraction"), ("wavelength_max_angstrom", "Maximum wavelength (Angstrom)"), ("flux_median", "Median flux"), ("image_snr_proxy_median", "Image S/N proxy (median)")]
    figure, axes = plt.subplots(2, 3, figsize=(13, 7))
    for axis, (field, label) in zip(axes.flat, features):
        values = np.asarray([row.get(field, np.nan) for row in rows], dtype=float)
        values = values[np.isfinite(values)]
        axis.hist(values, bins=min(30, max(5, int(np.sqrt(values.size)))) if values.size else 5, color="#2d6a8e", edgecolor="white")
        axis.set_title(label)
        axis.set_ylabel("observations")
    figure.tight_layout()
    path = output_dir / "feature_distributions.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return [str(path)]


def run_audit(root: Path, write_plots: bool = True) -> dict[str, Any]:
    metadata_path = root / "data/metadata/observations.jsonl"
    manifest = [json.loads(line) for line in metadata_path.read_text().splitlines() if line.strip()]
    rows = [characterize_observation(item, root) for item in manifest]
    results_dir = root / "experiments/results"
    results_dir.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with (results_dir / "dataset_features.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summaries = {field: _finite_summary([row.get(field, np.nan) for row in rows]) for field in NUMERIC_FEATURES}
    specids = [str(row.get("specid")) for row in rows]
    coordinate_pairs = [(row.get("ra_deg"), row.get("dec_deg")) for row in rows if row.get("coordinates_valid")]
    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "observations_manifested": len(manifest), "observations_characterized": len(rows),
        "spectral_errors": [row["specid"] for row in rows if row.get("spectral_error")], "image_errors": [row["specid"] for row in rows if row.get("image_error")],
        "identifier_audit": {"unique_specids": len(set(specids)), "duplicate_specids": len(specids) - len(set(specids)), "valid_coordinates": sum(bool(row.get("coordinates_valid")) for row in rows), "duplicate_coordinate_pairs": len(coordinate_pairs) - len(set(coordinate_pairs))},
        "array_inventory": {"spectral_array_sets": sorted(set(row.get("spectral_arrays", "") for row in rows)), "image_band_sets": sorted(set(row.get("image_bands", "") for row in rows)), "spectral_sample_count": _finite_summary([row.get("spectral_samples", np.nan) for row in rows]), "image_height_px": _finite_summary([row.get("image_height_px", np.nan) for row in rows]), "image_width_px": _finite_summary([row.get("image_width_px", np.nan) for row in rows]), "image_band_count": _finite_summary([row.get("image_band_count", np.nan) for row in rows])},
        "feature_summaries": summaries, "feature_diagnostics": _feature_diagnostics(rows),
        "interpretation": {"scope": "DESI DR1 records catalogue-classified as GALAXY with available DR10 grz cutouts; not representative of all DESI observations.", "image_caveat": "Image S/N, concentration, and asymmetry are simple quality/morphology proxies, not galaxy morphology classifications.", "residual_caveat": "Model residual fields describe spectral model discrepancy only and are not evidence of physical-model failure."},
        "recommendation": "Suitable for a controlled preliminary multimodal pipeline check, but 200 GALAXY-selected records are too small and selection-biased for general anomaly claims. For the next stage, target 2,000–5,000 observations selected in strata of redshift, target program, sky position, signal-to-noise, and spectype; retain quality failures rather than filtering them away.",
    }
    plots = _write_plots(rows, results_dir / "plots") if write_plots else []
    audit["plots"] = [str(Path(item).relative_to(root)) for item in plots]
    (results_dir / "dataset_audit.json").write_text(json.dumps(_json_safe(audit), indent=2) + "\n")
    redshift = summaries["redshift"]
    snr = summaries["snr_p90_abs"]
    quality = summaries["mask_nonzero_fraction"]
    ivar = summaries["ivar_positive_fraction"]
    image_snr = summaries["image_snr_proxy_median"]
    inventory = audit["array_inventory"]
    diagnostics = audit["feature_diagnostics"]
    markdown = ["# LIMEN Phase 2 dataset audit", "", "## Inventory and integrity", "", f"- Manifested / characterized: {len(manifest)} / {len(rows)}", f"- Spectral arrays: {', '.join(inventory['spectral_array_sets'])}", f"- Spectral sample count (all files): {inventory['spectral_sample_count']['min']}", f"- Image bands and shape: {', '.join(inventory['image_band_sets'])}; {inventory['image_band_count']['min']} × {inventory['image_height_px']['min']} × {inventory['image_width_px']['min']}", f"- Spectral / image read errors: {len(audit['spectral_errors'])} / {len(audit['image_errors'])}", f"- Unique specids / valid coordinates / duplicate coordinates: {audit['identifier_audit']['unique_specids']} / {audit['identifier_audit']['valid_coordinates']} / {audit['identifier_audit']['duplicate_coordinate_pairs']}", "", "## Population and quality summaries", "", f"- Redshift (finite n, median, range): {redshift['count']}, {redshift['median']:.4f}, [{redshift['min']:.4f}, {redshift['max']:.4f}]", f"- Spectral |S/N| 90th-percentile statistic (finite n, median): {snr['count']}, {snr['median']:.4f}; it is unavailable for {len(rows) - snr['count']} records with no valid unmasked positive-ivar samples.", f"- Wavelength grid: {summaries['wavelength_min_angstrom']['min']:.1f}–{summaries['wavelength_max_angstrom']['max']:.1f} Angstrom; median spacing {summaries['wavelength_spacing_median_angstrom']['median']:.3f} Angstrom.", f"- Masked-pixel fraction (median, range): {quality['median']:.5f}, [{quality['min']:.5f}, {quality['max']:.5f}]", f"- Positive inverse-variance fraction (median): {ivar['median']:.5f}", f"- Finite model coverage: {summaries['model_finite_fraction']['median']:.3f}; residual metrics are retained only as spectral model discrepancy fields.", f"- Image invalid-pixel fraction (median): {summaries['image_invalid_fraction']['median']:.3f}; central-versus-background S/N proxy median: {image_snr['median']:.4f}", "", "## Feature checks", "", f"- Constant features: {', '.join(diagnostics['constant_features']) or 'none'}; exclude these from any initial feature matrix.", f"- High-correlation pairs (|r| ≥ 0.98): {len(diagnostics['highly_correlated_pairs'])}; inspect the JSON audit before using both members of a pair.", "", "## Suitability and next sample", "", audit["recommendation"], "", "Initial modelling candidates: quality-aware spectral flux summaries or normalized spectra, valid-ivar S/N, mask fraction, redshift context, and cautiously scaled image quality/proxy features. Exclude constant wavelength-grid fields and image-invalid fraction here; do not impute unavailable S/N or quality values as zero.", "", "## Interpretation limits", "", audit["interpretation"]["scope"], audit["interpretation"]["image_caveat"], audit["interpretation"]["residual_caveat"]]
    (results_dir / "dataset_audit.md").write_text("\n".join(markdown) + "\n")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Characterize cached LIMEN spectra and images without downloading data.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    audit = run_audit(args.root, write_plots=not args.no_plots)
    print(json.dumps({"observations": audit["observations_characterized"], "spectral_errors": len(audit["spectral_errors"]), "image_errors": len(audit["image_errors"])}, indent=2))


if __name__ == "__main__":
    main()
