"""Acquire one approved public JWST product for LIMEN validation.

This script is intentionally constrained to one inventory record.  It performs
no MAST discovery query and requires ``--execute`` before it opens a network
connection.  The FITS product remains ignored under ``data/raw/``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
import re

import requests
from astropy.io import fits


SPECID = "243341144883356"
FILENAME = "jw01727-o035_t137_nircam_clear-f150w_i2d.fits"
DATA_URI = "mast:JWST/product/jw01727-o035_t137_nircam_clear-f150w_i2d.fits"
OBSERVATION_ID = "200709916"
EXPECTED_SIZE_BYTES = 1_471_178_880
MAST_DOWNLOAD_ENDPOINT = "https://mast.stsci.edu/api/v0.1/Download/file"
CHUNK_BYTES = 1024 * 1024
SAFETY_BYTES = 64 * 1024 * 1024
ALLOWED_DOWNLOAD_HOSTS = {"mast.stsci.edu"}
PROGRESS_REFRESH_SECONDS = 0.25


def _atomic_json(path: Path, value: dict) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=path.parent, suffix=".json.part") as temporary:
            temporary_name = temporary.name
            json.dump(value, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def _validate_fits(path: Path) -> list[dict[str, object]]:
    """Check FITS parsing without loading the image arrays into ordinary RAM."""
    summary: list[dict[str, object]] = []
    with fits.open(path, memmap=True, lazy_load_hdus=False, checksum=True) as hdus:
        hdus.verify("exception")
        for index, hdu in enumerate(hdus):
            data = hdu.data
            summary.append({
                "index": index,
                "name": hdu.name,
                "type": type(hdu).__name__,
                "shape": list(data.shape) if data is not None and hasattr(data, "shape") else None,
            })
    return summary


def _load_exact_inventory_record(root: Path) -> dict:
    inventory = root / "experiments/results/mast_full_inventory/mast_products.json"
    records = json.loads(inventory.read_text())
    matching = [row for row in records if str(row.get("limen_specid")) == SPECID and row.get("product_filename") == FILENAME]
    if len(matching) != 1:
        raise RuntimeError(f"Expected exactly one approved inventory record, found {len(matching)}")
    record = matching[0]
    expected = {
        "data_uri": DATA_URI,
        "mast_observation_id": OBSERVATION_ID,
        "file_size_bytes": EXPECTED_SIZE_BYTES,
        "data_rights": "PUBLIC",
        "product_type": "SCIENCE",
        "product_subgroup_description": "I2D",
        "calibration_level": 3,
    }
    mismatches = {key: {"expected": value, "actual": record.get(key)} for key, value in expected.items() if record.get(key) != value}
    if mismatches:
        raise RuntimeError(f"Inventory record no longer matches the approved product: {mismatches}")
    return record


def _acquire_lock(path: Path) -> int:
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another acquisition may be active: {path}") from exc


def _format_bytes(value: int | float) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"


def _format_eta(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "--:--"
    minutes, seconds = divmod(max(0, int(round(seconds))), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


class _ProgressDisplay:
    """Low-overhead terminal progress; redraws at most four times per second."""

    def __init__(self, total: int, initial: int, stream: object = sys.stderr) -> None:
        self.total = total
        self.completed = initial
        self.stream = stream
        self.started_at = time.monotonic()
        self.initial = initial
        self.last_rendered_at = 0.0
        self.width = 28

    def _render(self, final: bool = False) -> None:
        elapsed = max(time.monotonic() - self.started_at, 1e-9)
        transferred = self.completed - self.initial
        speed = transferred / elapsed
        ratio = min(1.0, self.completed / self.total) if self.total else 0.0
        filled = int(round(self.width * ratio))
        bar = "#" * filled + "-" * (self.width - filled)
        eta = (self.total - self.completed) / speed if speed > 0 else None
        line = (f"\rDownload [{bar}] {ratio * 100:6.2f}%  "
                f"{_format_bytes(self.completed)} / {_format_bytes(self.total)}  "
                f"{_format_bytes(speed)}/s  ETA {_format_eta(eta)}")
        self.stream.write(line)
        self.stream.flush()
        self.last_rendered_at = time.monotonic()
        if final:
            self.stream.write("\n")
            self.stream.flush()

    def update(self, byte_count: int, force: bool = False) -> None:
        self.completed += byte_count
        if force or time.monotonic() - self.last_rendered_at >= PROGRESS_REFRESH_SECONDS:
            self._render()

    def finish(self) -> None:
        self.completed = min(self.completed, self.total)
        self._render(final=True)


def _validate_response(response: requests.Response, existing_bytes: int) -> dict[str, str | int]:
    """Reject an error page, unexpected redirect, or invalid range response."""
    response.raise_for_status()
    parsed_url = urlparse(response.url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in ALLOWED_DOWNLOAD_HOSTS:
        raise RuntimeError(f"Unexpected final download URL: {response.url}")
    content_type = response.headers.get("Content-Type", "").lower()
    if any(marker in content_type for marker in ("text/html", "application/json", "application/xml", "text/xml")):
        raise RuntimeError(f"Unexpected response content type for FITS: {content_type}")
    if response.headers.get("Content-Encoding", "identity").lower() not in {"identity", ""}:
        raise RuntimeError(f"Unexpected content encoding for FITS: {response.headers.get('Content-Encoding')}")

    content_length = response.headers.get("Content-Length")
    if existing_bytes:
        if response.status_code != 206:
            raise ValueError("range_not_supported_or_not_honoured")
        content_range = response.headers.get("Content-Range", "")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
        if not match or int(match.group(1)) != existing_bytes or int(match.group(2)) != EXPECTED_SIZE_BYTES - 1 or int(match.group(3)) != EXPECTED_SIZE_BYTES:
            raise ValueError(f"invalid_content_range:{content_range}")
        expected_length = EXPECTED_SIZE_BYTES - existing_bytes
    else:
        if response.status_code != 200:
            raise RuntimeError(f"Unexpected initial download status: {response.status_code}")
        expected_length = EXPECTED_SIZE_BYTES
    if content_length is None or int(content_length) != expected_length:
        raise RuntimeError(f"Unexpected Content-Length: {content_length}; expected {expected_length}")
    return {"final_url": response.url, "content_type": content_type, "content_length": int(content_length), "status_code": response.status_code}


def _stream_fits_response(response: requests.Response, partial: Path, mode: str, expect_primary_header: bool, progress: _ProgressDisplay) -> None:
    """Write bounded chunks only after the FITS primary-header signature is seen."""
    prefix = b""
    with partial.open(mode) as handle:
        for chunk in response.iter_content(chunk_size=CHUNK_BYTES):
            if not chunk:
                continue
            if expect_primary_header and len(prefix) < 80:
                prefix = (prefix + chunk)[:80]
                if len(prefix) >= 9 and not prefix.startswith(b"SIMPLE  ="):
                    raise RuntimeError("Response body does not begin with a FITS SIMPLE header; partial retained only if it pre-existed")
            handle.write(chunk)
            progress.update(len(chunk))
        if expect_primary_header and not prefix.startswith(b"SIMPLE  ="):
            raise RuntimeError("Response body is empty or lacks a FITS SIMPLE header")
        handle.flush()
        os.fsync(handle.fileno())
    progress.finish()


def run(root: Path, execute: bool) -> dict:
    root = root.resolve()
    record = _load_exact_inventory_record(root)
    destination_dir = root / "data/raw/archive/jwst" / SPECID
    destination = destination_dir / FILENAME
    partial = destination_dir / f"{FILENAME}.part"
    metadata_path = destination_dir / f"{FILENAME}.metadata.json"
    download_url = f"{MAST_DOWNLOAD_ENDPOINT}?{urlencode({'uri': DATA_URI})}"
    plan = {
        "specid": SPECID,
        "destination": str(destination),
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "mast_data_uri": DATA_URI,
        "mast_download_url": download_url,
        "execute_required": True,
    }
    if not execute:
        return plan

    destination_dir.mkdir(parents=True, exist_ok=True)
    lock_path = destination_dir / f"{FILENAME}.lock"
    lock_fd = _acquire_lock(lock_path)
    try:
        if destination.exists():
            if destination.stat().st_size != EXPECTED_SIZE_BYTES:
                raise RuntimeError(f"Refusing to overwrite unexpected existing final file: {destination}")
            hdu_summary = _validate_fits(destination)
            return {**plan, "status": "already_valid", "fits_hdus": hdu_summary}

        existing_bytes = partial.stat().st_size if partial.exists() else 0
        if existing_bytes > EXPECTED_SIZE_BYTES:
            raise RuntimeError(f"Partial file exceeds expected size; remove it manually after inspection: {partial}")
        if existing_bytes:
            with partial.open("rb") as handle:
                if handle.read(9) != b"SIMPLE  =":
                    partial.unlink(missing_ok=True)
                    existing_bytes = 0
        print(f"{'Resuming' if existing_bytes else 'Starting'} download: {_format_bytes(existing_bytes)} of {_format_bytes(EXPECTED_SIZE_BYTES)} already available.", file=sys.stderr)
        remaining = EXPECTED_SIZE_BYTES - existing_bytes
        free_bytes = shutil.disk_usage(destination_dir).free
        if free_bytes < remaining + SAFETY_BYTES:
            raise RuntimeError(f"Insufficient free disk space: need at least {remaining + SAFETY_BYTES} bytes, have {free_bytes}")

        response_metadata: dict[str, str | int] | None = None
        for attempt in range(2):
            headers = {"Range": f"bytes={existing_bytes}-"} if existing_bytes else {}
            with requests.get(download_url, stream=True, timeout=(20, 180), headers=headers) as response:
                try:
                    response_metadata = _validate_response(response, existing_bytes)
                except ValueError:
                    # The server did not honour the exact byte offset. Discard
                    # only the partial file and repeat a full, validated request.
                    if not existing_bytes or attempt:
                        raise
                    partial.unlink(missing_ok=True)
                    existing_bytes = 0
                    print("Range resumption was not valid; restarting with a clean full download.", file=sys.stderr)
                    free_bytes = shutil.disk_usage(destination_dir).free
                    if free_bytes < EXPECTED_SIZE_BYTES + SAFETY_BYTES:
                        raise RuntimeError(f"Insufficient free disk space for clean restart: need at least {EXPECTED_SIZE_BYTES + SAFETY_BYTES} bytes, have {free_bytes}")
                    continue
                print("Download response accepted; streaming FITS data to the partial file.", file=sys.stderr)
                progress = _ProgressDisplay(EXPECTED_SIZE_BYTES, existing_bytes)
                progress.update(0, force=True)
                _stream_fits_response(response, partial, "ab" if existing_bytes else "wb", expect_primary_header=not bool(existing_bytes), progress=progress)
                break
        if response_metadata is None:
            raise RuntimeError("No valid MAST download response was obtained")

        final_size = partial.stat().st_size
        if final_size != EXPECTED_SIZE_BYTES:
            raise RuntimeError(f"Downloaded size mismatch: expected {EXPECTED_SIZE_BYTES}, received {final_size}; partial retained for safe resume")
        print("Download complete. Verifying FITS structure and checksums before promotion...", file=sys.stderr)
        hdu_summary = _validate_fits(partial)
        print("FITS verification passed. Atomically promoting validated file...", file=sys.stderr)
        os.replace(partial, destination)
        provenance = {
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_catalogue": "experiments/results/mast_full_inventory/mast_products.json",
            "inventory_record": record,
            "mast_data_uri": DATA_URI,
            "mast_download_url": download_url,
            "final_response_url": response_metadata["final_url"],
            "response_validation": response_metadata,
            "mast_observation_id": OBSERVATION_ID,
            "target_coordinates_deg": {"ra": record["desi_ra_deg"], "dec": record["desi_dec_deg"]},
            "expected_size_bytes": EXPECTED_SIZE_BYTES,
            "final_size_bytes": destination.stat().st_size,
            "fits_hdus": hdu_summary,
            "integrity": {"file_size_verified": True, "fits_verify": "exception", "checksum_verification_requested": True},
        }
        _atomic_json(metadata_path, provenance)
        print("Atomic promotion and provenance recording complete.", file=sys.stderr)
        return {**plan, "status": "downloaded_and_validated", "metadata_path": str(metadata_path), "fits_hdus": hdu_summary}
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire exactly one approved public JWST F150W product for LIMEN.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--execute", action="store_true", help="Permit the single network download. Without this flag, print the acquisition plan only.")
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
