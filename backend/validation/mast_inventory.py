"""Metadata-only MAST discovery inventory for LIMEN candidates.

This module queries MAST sequentially around coordinates already present in the
LIMEN observation manifest.  It never calls ``download_products`` (or writes
science data): its outputs are metadata inventories only.  A positional archive
match is discovery evidence, not a confirmed source association.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar


DEFAULT_OUTPUT_DIRECTORY = Path("experiments/results/mast_pilot")
MISSIONS = {"HST", "JWST"}
T = TypeVar("T")


def _json_safe(value: Any) -> Any:
    """Convert Astropy/Numpy scalars and masked values into JSON-safe values."""
    if value is None or getattr(value, "mask", False) is True:
        return None
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except ValueError:
            pass
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _row_dict(row: Any, columns: Iterable[str]) -> dict[str, Any]:
    return {str(name): _json_safe(row[name]) for name in columns}


def _field(row: dict[str, Any], *names: str) -> Any:
    """Return a field while tolerating MAST's mixed historical column casing."""
    lower = {key.lower(): value for key, value in row.items()}
    for name in names:
        if name in row:
            return row[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _normalise_mission(value: Any) -> str:
    return str(value or "").strip().upper()


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    required = {"specid", "targetid", "ra_deg", "dec_deg"}
    if not records:
        raise ValueError(f"Manifest is empty: {path}")
    missing = required - records[0].keys()
    if missing:
        raise ValueError(f"Manifest lacks required fields: {sorted(missing)}")

    specids: set[str] = set()
    for index, record in enumerate(records, start=1):
        absent = required - record.keys()
        if absent:
            raise ValueError(f"Manifest record {index} lacks fields: {sorted(absent)}")
        specid = str(record["specid"])
        if specid in specids:
            raise ValueError(f"Manifest has duplicate specid: {specid}")
        specids.add(specid)
        try:
            ra, dec = float(record["ra_deg"]), float(record["dec_deg"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid coordinate for specid {specid}") from exc
        if not math.isfinite(ra) or not math.isfinite(dec) or not 0 <= ra < 360 or not -90 <= dec <= 90:
            raise ValueError(f"Out-of-range coordinate for specid {specid}: ra_deg={ra}, dec_deg={dec}")
    return records


def _retry(operation: Callable[[], T], retries: int, backoff_seconds: float) -> tuple[T | None, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    for attempt in range(1, retries + 1):
        try:
            return operation(), errors
        except Exception as exc:  # Network and remote-service failures are recorded, not fatal to the pilot.
            errors.append({"attempt": attempt, "reason": type(exc).__name__, "detail": str(exc)})
            if attempt < retries:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))
    return None, errors


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_checkpoint(path: Path, value: dict[str, Any]) -> None:
    """Atomically preserve one completed candidate for resumable full runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=path.parent, suffix=".json.part") as temporary:
            temporary_name = temporary.name
            json.dump(value, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _read_checkpoint(path: Path, specid: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        checkpoint = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return checkpoint if checkpoint.get("specid") == specid else None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _assert_writable_output(output_dir: Path, overwrite: bool, resume: bool) -> None:
    expected = [
        output_dir / "mast_observations.csv",
        output_dir / "mast_observations.json",
        output_dir / "mast_products.csv",
        output_dir / "mast_products.json",
        output_dir / "mast_inventory_report.json",
        output_dir / "mast_inventory_report.md",
    ]
    existing = [path for path in expected if path.exists()]
    if existing and not overwrite and not resume:
        raise FileExistsError("Refusing to overwrite existing inventory outputs; use --overwrite explicitly: " + ", ".join(map(str, existing)))
    output_dir.mkdir(parents=True, exist_ok=True)


def run(
    root: Path,
    limit: int = 10,
    radius_arcsec: float = 2.0,
    retries: int = 3,
    backoff_seconds: float = 2.0,
    output_dir: Path | None = None,
    overwrite: bool = False,
    resume: bool = False,
) -> dict[str, Any]:
    """Create HST/JWST discovery inventories without downloading any products."""
    if limit < 1 or radius_arcsec <= 0 or retries < 1 or backoff_seconds < 0:
        raise ValueError("limit, radius_arcsec and retries must be positive; backoff_seconds cannot be negative")

    root = root.resolve()
    output_dir = (output_dir or root / DEFAULT_OUTPUT_DIRECTORY).resolve()
    _assert_writable_output(output_dir, overwrite, resume)
    manifest_path = root / "data/metadata/observations.jsonl"
    candidates = _load_manifest(manifest_path)[:limit]

    try:
        from astroquery.mast import Observations
    except ImportError as exc:
        raise RuntimeError("astroquery is required. Install the project's requirements before running this MAST inventory.") from exc

    observation_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    query_status: list[dict[str, Any]] = []
    seen_observations: set[tuple[str, str]] = set()
    seen_products: set[tuple[str, str, str, str]] = set()
    checkpoint_dir = output_dir / "checkpoints"

    for candidate in candidates:  # Deliberately sequential: courteous to MAST and memory-light.
        specid, targetid = str(candidate["specid"]), str(candidate["targetid"])
        ra, dec = float(candidate["ra_deg"]), float(candidate["dec_deg"])
        checkpoint_path = checkpoint_dir / f"{specid}.json"
        checkpoint = _read_checkpoint(checkpoint_path, specid) if resume else None
        if checkpoint is not None:
            observation_rows.extend(checkpoint.get("observation_rows", []))
            product_rows.extend(checkpoint.get("product_rows", []))
            failures.extend(checkpoint.get("failures", []))
            query_status.append(checkpoint["query_status"])
            for row in checkpoint.get("observation_rows", []):
                seen_observations.add((str(row["limen_specid"]), str(row["mast_raw_metadata_json"])))
            for row in checkpoint.get("product_rows", []):
                seen_products.add((str(row["limen_specid"]), str(row["mast_observation_id"]), str(row.get("data_uri") or ""), str(row.get("product_filename") or "")))
            continue

        observation_start, product_start, failure_start = len(observation_rows), len(product_rows), len(failures)
        position = f"{ra} {dec}"
        table, query_errors = _retry(
            lambda: Observations.query_region(position, radius=f"{radius_arcsec} arcsec"), retries, backoff_seconds
        )
        if table is None:
            failures.append({"specid": specid, "targetid": targetid, "stage": "query_region", "errors": query_errors})
            query_status.append({"specid": specid, "targetid": targetid, "status": "failed"})
            _write_checkpoint(checkpoint_path, {"specid": specid, "observation_rows": [], "product_rows": [], "failures": failures[failure_start:], "query_status": query_status[-1]})
            continue

        raw_observations = [_row_dict(row, table.colnames) for row in table]
        mission_observations = [row for row in raw_observations if _normalise_mission(_field(row, "obs_collection", "obsCollection")) in MISSIONS]
        query_status.append({"specid": specid, "targetid": targetid, "status": "ok", "all_mast_rows": len(raw_observations), "hst_jwst_rows": len(mission_observations)})
        product_contexts: dict[str, tuple[Any, str, dict[str, Any]]] = {}

        # Preserve every positional-query row in the observation inventory.
        # Product enumeration remains deliberately scoped to HST/JWST, which is
        # the purpose of this pilot; no product-type filter is applied.
        for raw_observation in raw_observations:
            obsid = _field(raw_observation, "obsid", "obs_id", "obsid")
            obsid_text = str(obsid) if obsid is not None else ""
            # Some queries return several distinct metadata rows with the same
            # obsid. Preserve those rows; suppress only exact repeated rows.
            observation_key = (specid, json.dumps(raw_observation, sort_keys=True))
            if observation_key in seen_observations:
                continue
            seen_observations.add(observation_key)
            collection = _normalise_mission(_field(raw_observation, "obs_collection", "obsCollection"))
            observation_rows.append({
                "limen_specid": specid,
                "limen_targetid": targetid,
                "desi_ra_deg": ra,
                "desi_dec_deg": dec,
                "mast_observation_id": obsid,
                "mission_collection": collection,
                "is_hst_or_jwst": collection in MISSIONS,
                "instrument": _field(raw_observation, "instrument_name", "instrument"),
                "filters": _field(raw_observation, "filters", "filter"),
                "proposal_id": _field(raw_observation, "proposal_id", "proposal_pi"),
                "observation_start_mjd": _field(raw_observation, "t_min"),
                "observation_end_mjd": _field(raw_observation, "t_max"),
                "data_rights": _field(raw_observation, "dataRights", "data_rights"),
                "mast_raw_metadata_json": json.dumps(raw_observation, sort_keys=True),
            })

            if collection in MISSIONS and obsid is None:
                failures.append({"specid": specid, "targetid": targetid, "stage": "product_list", "reason": "missing_obsid"})
                continue
            if collection in MISSIONS:
                product_contexts.setdefault(obsid_text, (obsid, collection, raw_observation))

        if product_contexts:
            requested_obsids = [context[0] for context in product_contexts.values()]
            products, product_errors = _retry(lambda: Observations.get_product_list(requested_obsids), retries, backoff_seconds)
            if products is None:
                failures.append({"specid": specid, "targetid": targetid, "mast_observation_ids": [str(value) for value in requested_obsids], "stage": "product_list", "errors": product_errors})
            else:
                for raw_product in (_row_dict(row, products.colnames) for row in products):
                    parent_obsid = _field(raw_product, "parent_obsid", "parentObsid")
                    context = product_contexts.get(str(parent_obsid))
                    if context is None:
                        failures.append({"specid": specid, "targetid": targetid, "mast_observation_id": parent_obsid, "stage": "product_list", "reason": "unmapped_parent_obsid"})
                        obsid, collection, raw_observation = parent_obsid, _normalise_mission(_field(raw_product, "obs_collection", "obsCollection")), raw_product
                    else:
                        obsid, collection, raw_observation = context
                    obsid_text = str(obsid) if obsid is not None else ""
                    data_uri = _field(raw_product, "dataURI", "data_uri")
                    filename = _field(raw_product, "productFilename", "product_filename")
                    key = (specid, obsid_text, str(data_uri or ""), str(filename or ""))
                    if key in seen_products:
                        continue
                    seen_products.add(key)
                    product_rows.append({
                        "limen_specid": specid,
                        "limen_targetid": targetid,
                        "desi_ra_deg": ra,
                        "desi_dec_deg": dec,
                        "mast_observation_id": obsid,
                        "mission_collection": collection,
                        "instrument": _field(raw_observation, "instrument_name", "instrument"),
                        "filters": _field(raw_observation, "filters", "filter"),
                        "proposal_id": _field(raw_observation, "proposal_id", "proposal_pi"),
                        "observation_start_mjd": _field(raw_observation, "t_min"),
                        "observation_end_mjd": _field(raw_observation, "t_max"),
                        "data_rights": _field(raw_product, "dataRights", "data_rights") or _field(raw_observation, "dataRights", "data_rights"),
                        "product_filename": filename,
                        "product_type": _field(raw_product, "productType", "product_type"),
                        "product_subgroup_description": _field(raw_product, "productSubGroupDescription", "product_subgroup_description"),
                        "calibration_level": _field(raw_product, "calib_level", "calibrationLevel"),
                        "file_size_bytes": _field(raw_product, "size", "fileSize"),
                        "data_uri": data_uri,
                        "mast_raw_metadata_json": json.dumps(raw_product, sort_keys=True),
                    })

        _write_checkpoint(checkpoint_path, {
            "specid": specid,
            "observation_rows": observation_rows[observation_start:],
            "product_rows": product_rows[product_start:],
            "failures": failures[failure_start:],
            "query_status": query_status[-1],
        })

    hst_jwst_rows = [row for row in observation_rows if row["is_hst_or_jwst"]]
    mission_counts = Counter(str(row["mission_collection"]) for row in hst_jwst_rows)
    collection_counts = Counter(str(row["mission_collection"]) for row in observation_rows)
    targets_with_mission = {mission: {row["limen_specid"] for row in hst_jwst_rows if row["mission_collection"] == mission} for mission in MISSIONS}
    targets_with_any = {row["limen_specid"] for row in hst_jwst_rows}
    rights = Counter(str(row["data_rights"]) if row["data_rights"] is not None else "unavailable" for row in product_rows)
    completed_targets = {str(row["specid"]) for row in query_status if row["status"] == "ok"}
    failed_targets = {str(row["specid"]) for row in query_status if row["status"] != "ok"}
    repeated_observation_ids = Counter((str(row["limen_specid"]), str(row["mast_observation_id"])) for row in observation_rows)
    candidate_coverage: list[dict[str, Any]] = []
    for candidate in candidates:
        specid = str(candidate["specid"])
        candidate_observations = [row for row in hst_jwst_rows if str(row["limen_specid"]) == specid]
        if not candidate_observations:
            continue
        candidate_products = [row for row in product_rows if str(row["limen_specid"]) == specid]
        candidate_coverage.append({
            "specid": specid,
            "targetid": str(candidate["targetid"]),
            "hst_observations": sum(row["mission_collection"] == "HST" for row in candidate_observations),
            "jwst_observations": sum(row["mission_collection"] == "JWST" for row in candidate_observations),
            "unique_hst_jwst_observation_ids": len({str(row["mast_observation_id"]) for row in candidate_observations}),
            "associated_products": len(candidate_products),
            "metadata_listed_product_volume_bytes": sum(int(row["file_size_bytes"]) for row in candidate_products if row.get("file_size_bytes") is not None),
        })
    candidate_coverage.sort(key=lambda row: (row["associated_products"], row["unique_hst_jwst_observation_ids"]), reverse=True)
    report = {
        "purpose": "Metadata-only MAST discovery inventory. Positional matches are not confirmed astronomical source associations.",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "output_directory": str(output_dir),
        "query": {"missions": sorted(MISSIONS), "radius_arcsec": radius_arcsec, "limit": limit, "retries": retries, "backoff_seconds": backoff_seconds, "sequential": True, "downloads_performed": 0},
        "counts": {
            "targets_queried": len(candidates),
            "targets_completed": len(completed_targets),
            "targets_with_failed_region_query": len(failed_targets),
            "targets_with_hst_observation": len(targets_with_mission["HST"]),
            "targets_with_jwst_observation": len(targets_with_mission["JWST"]),
            "targets_with_both_hst_and_jwst_observations": len(targets_with_mission["HST"] & targets_with_mission["JWST"]),
            "targets_with_no_hst_or_jwst_observation": len({str(row["specid"]) for row in candidates} - targets_with_any),
            "total_mast_observations_returned": len(observation_rows),
            "total_hst_jwst_observations": len(hst_jwst_rows),
            "observations_by_mast_collection": dict(sorted(collection_counts.items())),
            "observations_by_mission": dict(sorted(mission_counts.items())),
            "total_associated_products": len(product_rows),
            "products_by_mission": dict(sorted(Counter(str(row["mission_collection"]) for row in product_rows).items())),
            "products_by_instrument": dict(sorted(Counter(str(row["instrument"]) if row["instrument"] is not None else "unavailable" for row in product_rows).items())),
            "products_by_filter": dict(sorted(Counter(str(row["filters"]) if row["filters"] is not None else "unavailable" for row in product_rows).items())),
            "products_by_type": dict(sorted(Counter(str(row["product_type"]) if row["product_type"] is not None else "unavailable" for row in product_rows).items())),
            "products_by_calibration_level": dict(sorted(Counter(str(row["calibration_level"]) if row["calibration_level"] is not None else "unavailable" for row in product_rows).items())),
            "products_by_data_rights": dict(sorted(rights.items())),
            "total_metadata_listed_product_volume_bytes": sum(int(row["file_size_bytes"]) for row in product_rows if row.get("file_size_bytes") is not None),
            "repeated_candidate_observation_id_pairs": sum(count > 1 for count in repeated_observation_ids.values()),
            "repeated_observation_rows_beyond_first": sum(count - 1 for count in repeated_observation_ids.values() if count > 1),
            "failed_or_incomplete_queries": len(failures),
        },
        "richest_hst_jwst_candidate_coverage": candidate_coverage[:20],
        "query_status": query_status,
        "failures": failures,
        "limitations": [
            "No archive product was downloaded.",
            "Returned observations are preserved as discovery metadata; later validation may reject them.",
            "A two-arcsecond positional query does not establish source identity or footprint overlap.",
            "Data-rights values are reported as returned by MAST and are not overridden by this script.",
        ],
    }
    _write_csv(output_dir / "mast_observations.csv", observation_rows)
    _write_json(output_dir / "mast_observations.json", observation_rows)
    _write_csv(output_dir / "mast_products.csv", product_rows)
    _write_json(output_dir / "mast_products.json", product_rows)
    _write_json(output_dir / "mast_inventory_report.json", report)
    markdown = ["# LIMEN MAST metadata-only pilot", "", "## Counts", ""]
    markdown.extend(f"- {key.replace('_', ' ')}: {value}" for key, value in report["counts"].items())
    markdown += ["", "## Interpretation boundary", "", *[f"- {item}" for item in report["limitations"]], ""]
    (output_dir / "mast_inventory_report.md").write_text("\n".join(markdown))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a metadata-only HST/JWST MAST inventory for LIMEN candidates.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--limit", type=int, default=10, help="Number of manifest records to query (default: 10).")
    parser.add_argument("--radius-arcsec", type=float, default=2.0, help="MAST positional search radius in arcseconds (default: 2).")
    parser.add_argument("--retries", type=int, default=3, help="Attempts for each MAST request (default: 3).")
    parser.add_argument("--backoff-seconds", type=float, default=2.0, help="Initial exponential-backoff delay in seconds (default: 2).")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory; defaults to experiments/results/mast_pilot.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing inventory outputs in the selected output directory only.")
    parser.add_argument("--resume", action="store_true", help="Reuse completed per-target checkpoints in the selected output directory.")
    args = parser.parse_args()
    report = run(args.root, args.limit, args.radius_arcsec, args.retries, args.backoff_seconds, args.output_dir, args.overwrite, args.resume)
    print(json.dumps(report["counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
