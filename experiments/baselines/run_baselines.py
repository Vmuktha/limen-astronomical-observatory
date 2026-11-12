from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from scipy.stats import spearmanr

from backend.anomaly.baselines import fit_isolation_forest, fit_multimodal, top_overlap
from backend.preprocessing.baseline_features import image_baseline_features, spectral_baseline_features


CONFIG = {"algorithm": "IsolationForest", "random_state": 42, "n_estimators": 300, "contamination": 0.10, "spectral_shape_bins": 24, "multimodal_scaling": "median imputation + RobustScaler per modality + 1/sqrt(number_of_features) block scaling", "notes": "Scores are relative Isolation Forest anomaly scores, higher means more unusual within this pilot and is not a probability."}


def _numeric_matrix(rows: list[dict[str, Any]], names: list[str]) -> np.ndarray:
    return np.asarray([[row.get(name, np.nan) for name in names] for row in rows], dtype=float)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def extract_features(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = [json.loads(line) for line in (root / "data/metadata/observations.jsonl").read_text().splitlines() if line]
    spectral_rows, image_rows, context = [], [], []
    for item in manifest:
        identity = {key: item.get(key) for key in ("specid", "targetid", "ra_deg", "dec_deg", "redshift", "redshift_warning", "spectype")}
        spectral = dict(identity)
        image = dict(identity)
        with np.load(root / item["spectrum_path"]) as data:
            spectral.update(spectral_baseline_features(data["wavelength"], data["flux"], data.get("ivar"), data.get("mask"), data.get("model"), bins=CONFIG["spectral_shape_bins"]))
        with fits.open(root / item["image_path"], memmap=False) as hdus:
            image.update(image_baseline_features(hdus[0].data, str(hdus[0].header.get("BANDS", "grz"))))
        spectral_rows.append(spectral); image_rows.append(image)
        context.append({**identity, "spectrum_status": item.get("spectrum_status"), "image_status": item.get("image_status"), "spectral_valid_pixel_fraction": spectral.get("spec_valid_pixel_fraction"), "spectral_snr_abs_p90": spectral.get("spec_snr_abs_p90"), "image_snr_proxy_median": image.get("img_snr_proxy_median")})
    return spectral_rows, image_rows, context


def _feature_names(rows: list[dict[str, Any]], prefix: str) -> list[str]:
    excluded = {"specid", "targetid", "ra_deg", "dec_deg", "redshift", "redshift_warning", "spectype"}
    return sorted(key for key in rows[0] if key.startswith(prefix) and key not in excluded)


def _sensitivity(matrix: np.ndarray, names: list[str]) -> dict[str, float]:
    reference = fit_isolation_forest(matrix, names, **{key: CONFIG[key] for key in ("random_state", "n_estimators", "contamination")}).ranks
    result = {}
    for trees in (100, 500):
        alternate = fit_isolation_forest(matrix, names, random_state=CONFIG["random_state"], n_estimators=trees, contamination=CONFIG["contamination"]).ranks
        result[f"n_estimators_{trees}_spearman_rank_correlation"] = float(spearmanr(reference, alternate).statistic)
    return result


def run(root: Path) -> dict[str, Any]:
    root = root.resolve(); output = root / "experiments/results"; output.mkdir(parents=True, exist_ok=True)
    spectral_rows, image_rows, context = extract_features(root)
    _write_csv(output / "spectral_features.csv", spectral_rows); _write_csv(output / "image_features.csv", image_rows)
    spectral_names, image_names = _feature_names(spectral_rows, "spec_"), _feature_names(image_rows, "img_")
    spectral_matrix, image_matrix = _numeric_matrix(spectral_rows, spectral_names), _numeric_matrix(image_rows, image_names)
    options = {key: CONFIG[key] for key in ("random_state", "n_estimators", "contamination")}
    spectral = fit_isolation_forest(spectral_matrix, spectral_names, **options)
    image = fit_isolation_forest(image_matrix, image_names, **options)
    multimodal = fit_multimodal(spectral_matrix, spectral_names, image_matrix, image_names, **options)
    score_rows = []
    for index, row in enumerate(context):
        score_rows.append({**row, "spectral_anomaly_score": float(spectral.scores[index]), "spectral_rank": int(spectral.ranks[index]), "image_anomaly_score": float(image.scores[index]), "image_rank": int(image.ranks[index]), "multimodal_anomaly_score": float(multimodal.scores[index]), "multimodal_rank": int(multimodal.ranks[index])})
    _write_csv(output / "anomaly_scores.csv", score_rows)
    correlations = {"spectral_image": float(spearmanr(spectral.ranks, image.ranks).statistic), "spectral_multimodal": float(spearmanr(spectral.ranks, multimodal.ranks).statistic), "image_multimodal": float(spearmanr(image.ranks, multimodal.ranks).statistic)}
    analysis = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "configuration": CONFIG, "observations": len(score_rows), "features_used": {"spectral": spectral.feature_names, "image": image.feature_names, "multimodal": multimodal.feature_names}, "top_20": {"spectral": [row["specid"] for row in sorted(score_rows, key=lambda row: row["spectral_rank"])[:20]], "image": [row["specid"] for row in sorted(score_rows, key=lambda row: row["image_rank"])[:20]], "multimodal": [row["specid"] for row in sorted(score_rows, key=lambda row: row["multimodal_rank"])[:20]]}, "top_20_overlap": top_overlap(spectral.ranks, image.ranks, multimodal.ranks), "rank_correlations_spearman": correlations, "sensitivity": {"spectral": _sensitivity(spectral_matrix, spectral_names), "image": _sensitivity(image_matrix, image_names)}, "limitations": ["Anomaly scores are relative rankings within 200 GALAXY-classified DESI DR1 records, not probabilities or discoveries.", "The sample is small, selected, and not representative of all DESI populations.", "Image concentration and asymmetry are morphology proxies, not morphology classifications.", "Spectral model residual features describe model discrepancy only; they do not establish physical-model failure.", "Isolation Forest does not yield defensible per-object causal feature attribution; retained feature lists and sensitivity checks are diagnostics, not explanations."], "quality_handling": "Non-finite features are median-imputed after constant features are removed; unavailable S/N is never pre-filled as zero."}
    (output / "baseline_results.json").write_text(json.dumps(analysis, indent=2) + "\n")
    _plots(score_rows, output / "plots")
    markdown = ["# LIMEN Phase 3 baseline analysis", "", f"- Observations: {len(score_rows)}", "- Baselines: spectral-only, image-only, and equalized multimodal Isolation Forest.", "- Scores are relative ranking values, not probabilities and not discovery claims.", "- Feature contribution: Isolation Forest offers no defensible per-object causal attribution here. The retained feature lists are recorded in `baseline_results.json`; score/rank stability is reported instead.", "", "## Top-20 overlap", "", *[f"- {key}: {value}" for key, value in analysis["top_20_overlap"].items()], "", "## Rank correlation (Spearman)", "", *[f"- {key}: {value:.3f}" for key, value in correlations.items()], "", "## Sensitivity", "", *[f"- {modality}, {setting}: {value:.3f} rank correlation with the 300-tree reference" for modality, values in analysis["sensitivity"].items() for setting, value in values.items()], "", "## Limits", "", *[f"- {item}" for item in analysis["limitations"]]]
    (output / "baseline_analysis.md").write_text("\n".join(markdown) + "\n")
    return analysis


def _plots(rows: list[dict[str, Any]], destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    destination.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
    for axis, field, label in zip(axes, ("spectral_anomaly_score", "image_anomaly_score", "multimodal_anomaly_score"), ("Spectral", "Image", "Multimodal")):
        axis.hist([row[field] for row in rows], bins=20, color="#5b7c99", edgecolor="white"); axis.set_title(f"{label} baseline score"); axis.set_xlabel("relative anomaly score")
    fig.tight_layout(); fig.savefig(destination / "baseline_score_distributions.png", dpi=160); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run compact LIMEN anomaly baselines on cached data only.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(); result = run(args.root); print(json.dumps({"observations": result["observations"], "top_20_overlap": result["top_20_overlap"]}, indent=2))


if __name__ == "__main__":
    main()
