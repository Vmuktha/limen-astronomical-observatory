from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import IngestionConfig
from .desi_sparcl import DESI_DR1, find_galaxy_candidates, record_value, retrieve_records
from .legacy_survey import fetch_dr10_cutout, validate_fits_file
from .validation import usable_spectrum, valid_coordinates


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return value


def _save_spectrum(path: Path, record: Any) -> tuple[bool, str | None]:
    fields = {name: record_value(record, name) for name in ("wavelength", "flux", "ivar", "mask", "model")}
    usable, reason = usable_spectrum(fields["wavelength"], fields["flux"], fields["ivar"])
    if not usable:
        return False, reason
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {name: np.asarray(value) for name, value in fields.items() if value is not None and np.asarray(value).size > 0}
    temporary = path.with_suffix(".npz.part")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    temporary.replace(path)
    return True, None


def run(config: IngestionConfig) -> dict[str, Any]:
    from sparcl.client import SparclClient

    started = datetime.now(timezone.utc)
    report: dict[str, Any] = {"requested_observations": config.requested_count, "started_at_utc": started.isoformat(), "dataset_provenance": {"desi_data_release": DESI_DR1, "desi_access": "NOIRLab SPARCL public API", "legacy_survey_release": "Legacy Surveys DR10", "legacy_access": config.legacy_cutout_url}, "counts": {"candidates_found": 0, "spectra_retrieved": 0, "usable_spectra": 0, "images_retrieved": 0, "missing_or_incomplete": 0}, "failures": [], "observations": []}
    try:
        client = SparclClient(url=config.sparcl_url, announcement=False, connect_timeout=min(config.timeout_seconds, 10), read_timeout=config.timeout_seconds)
    except Exception as exc:
        report["failures"].append({"stage": "sparcl_client_initialization", "reason": type(exc).__name__, "detail": str(exc)})
        return _write_report(config, report)
    try:
        candidates = find_galaxy_candidates(client, config.requested_count)
    except Exception as exc:
        report["failures"].append({"stage": "candidate_discovery", "reason": type(exc).__name__, "detail": str(exc)})
        return _write_report(config, report)
    report["counts"]["candidates_found"] = len(candidates)
    by_specid = {str(record_value(record, "specid")): record for record in candidates}
    retrieved: dict[str, Any] = {}
    for offset in range(0, len(candidates), config.batch_size):
        batch = candidates[offset : offset + config.batch_size]
        # Metadata discovery is cheap; full arrays are not re-requested when a
        # previously written, validated cache entry is available.
        ids = [
            record_value(item, "specid")
            for item in batch
            if record_value(item, "specid") is not None
            and not (config.raw_spectra_dir / f"{record_value(item, 'specid')}.npz").exists()
        ]
        if not ids:
            continue
        try:
            for record in retrieve_records(client, ids):
                retrieved[str(record_value(record, "specid"))] = record
        except Exception as exc:
            report["failures"].append({"stage": "spectrum_retrieval", "reason": type(exc).__name__, "detail": str(exc), "specids": [str(item) for item in ids]})
    for specid, candidate in by_specid.items():
        spectrum_path = config.raw_spectra_dir / f"{specid}.npz"
        cached_spectrum = spectrum_path.exists()
        record = retrieved.get(specid) or (candidate if cached_spectrum else None)
        item = {"specid": specid, "targetid": _json_safe(record_value(record or candidate, "targetid")), "sparcl_id": _json_safe(record_value(record or candidate, "sparcl_id")), "ra_deg": _json_safe(record_value(record or candidate, "ra")), "dec_deg": _json_safe(record_value(record or candidate, "dec")), "spectype": _json_safe(record_value(record or candidate, "spectype")), "redshift": _json_safe(record_value(record or candidate, "redshift")), "redshift_warning": _json_safe(record_value(record or candidate, "redshift_warning")), "spectrum_status": "not_retrieved", "image_status": "not_attempted"}
        if record is None:
            item["failure_reason"] = "spectrum_record_not_returned"
            report["counts"]["missing_or_incomplete"] += 1
            report["observations"].append(item)
            continue
        report["counts"]["spectra_retrieved"] += 1
        if spectrum_path.exists():
            try:
                with np.load(spectrum_path) as cached:
                    ok, reason = usable_spectrum(cached["wavelength"], cached["flux"], cached.get("ivar"))
                reason = None if ok else f"cached_{reason}"
            except (OSError, KeyError, ValueError) as exc:
                ok, reason = False, f"cached_spectrum_unreadable_{type(exc).__name__}"
        else:
            ok, reason = _save_spectrum(spectrum_path, record)
        item["spectrum_status"] = "usable" if ok else "incomplete"
        item["spectrum_source"] = "local_cache" if cached_spectrum else "sparcl"
        item["spectrum_path"] = str(spectrum_path.relative_to(config.root)) if ok else None
        if ok:
            report["counts"]["usable_spectra"] += 1
        else:
            item["failure_reason"] = reason
            report["counts"]["missing_or_incomplete"] += 1
        image_path = config.raw_images_dir / f"{specid}.fits"
        if valid_coordinates(item["ra_deg"], item["dec_deg"]):
            if image_path.exists():
                cached_image = validate_fits_file(image_path)
                if cached_image.success:
                    image_ok, image_reason, image_url, image_detail = True, None, "cached_local_file", None
                else:
                    image_result = fetch_dr10_cutout(ra=item["ra_deg"], dec=item["dec_deg"], destination=image_path, endpoint=config.legacy_cutout_url, size=config.cutout_size_pixels, timeout=config.timeout_seconds)
                    image_ok, image_reason, image_url, image_detail = image_result.success, image_result.reason, image_result.url, image_result.detail
            else:
                image_result = fetch_dr10_cutout(ra=item["ra_deg"], dec=item["dec_deg"], destination=image_path, endpoint=config.legacy_cutout_url, size=config.cutout_size_pixels, timeout=config.timeout_seconds)
                image_ok, image_reason, image_url, image_detail = image_result.success, image_result.reason, image_result.url, image_result.detail
            item["image_status"] = "retrieved" if image_ok else "unavailable"
            item["image_url"] = image_url
            item["image_path"] = str(image_path.relative_to(config.root)) if image_ok else None
            if image_ok:
                report["counts"]["images_retrieved"] += 1
            else:
                item["image_failure_reason"] = image_reason
                item["image_failure_detail"] = image_detail
                report["counts"]["missing_or_incomplete"] += 1
        else:
            item["image_status"] = "invalid_coordinates"
            item["image_failure_reason"] = "invalid_coordinates"
            report["counts"]["missing_or_incomplete"] += 1
        report["observations"].append(item)
    return _write_report(config, report)


def _write_report(config: IngestionConfig, report: dict[str, Any]) -> dict[str, Any]:
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    config.metadata_dir.mkdir(parents=True, exist_ok=True)
    (config.metadata_dir / "ingestion_report.json").write_text(json.dumps(report, indent=2, default=_json_safe) + "\n")
    lines = ["# LIMEN Phase 1 ingestion report", "", f"- Requested observations: {report['requested_observations']}"]
    lines += [f"- {label.replace('_', ' ').capitalize()}: {value}" for label, value in report["counts"].items()]
    lines += ["", "## Provenance", "", *[f"- {key}: {value}" for key, value in report["dataset_provenance"].items()], "", "## Interpretation boundary", "", "This report records data availability only. Legacy Survey cutouts are cross-survey consistency evidence, not independent confirmation of DESI observations. No anomaly or physical-model conclusion is made."]
    (config.metadata_dir / "ingestion_report.md").write_text("\n".join(lines) + "\n")
    with (config.metadata_dir / "observations.jsonl").open("w") as handle:
        for observation in report["observations"]:
            handle.write(json.dumps(observation, default=_json_safe) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve a small public DESI DR1 galaxy pilot and Legacy Survey DR10 cutouts.")
    parser.add_argument("--count", type=int, default=200, help="Maximum number of candidate observations (default: 200).")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if not 1 <= args.count <= 200:
        parser.error("--count must be between 1 and 200 for this pilot")
    report = run(IngestionConfig.from_environment(args.root, args.count))
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
