from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import requests
from astropy.io import fits
from astropy.io.fits.verify import VerifyError

from .validation import valid_coordinates


@dataclass(frozen=True)
class CutoutResult:
    success: bool
    reason: str | None = None
    url: str | None = None
    detail: str | None = None


def validate_fits_file(path: Path) -> CutoutResult:
    """Fully parse a cutout and require at least one non-empty image array."""
    try:
        with fits.open(path, memmap=False, lazy_load_hdus=False) as hdus:
            hdus.verify("exception")
            image_hdus = 0
            for hdu in hdus:
                data = hdu.data  # Force data reads, detecting truncation beyond headers.
                if data is not None and np.asarray(data).size > 0:
                    image_hdus += 1
            if image_hdus == 0:
                return CutoutResult(False, "fits_missing_image_data", detail="No non-empty image HDU found")
    except (OSError, EOFError, ValueError, TypeError, VerifyError) as exc:
        return CutoutResult(False, "fits_validation_failed", detail=f"{type(exc).__name__}: {exc}")
    return CutoutResult(True)


def fetch_dr10_cutout(*, ra: Any, dec: Any, destination: Path, endpoint: str, size: int, timeout: int) -> CutoutResult:
    """Download, validate, and atomically publish a small DR10 FITS cutout.

    A unique same-directory temporary file prevents collisions between runs and
    is removed on every unsuccessful request, write, or validation path.
    """
    if not valid_coordinates(ra, dec):
        return CutoutResult(False, "invalid_coordinates")
    params = {"ra": f"{float(ra):.8f}", "dec": f"{float(dec):.8f}", "layer": "ls-dr10", "bands": "grz", "pixscale": "0.262", "size": size}
    temporary_path: Path | None = None
    response_url: str | None = None
    try:
        response = requests.get(endpoint, params=params, timeout=timeout, stream=True)
        response.raise_for_status()
        response_url = response.url
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=destination.parent, suffix=".fits.part") as temporary:
            temporary_path = Path(temporary.name)
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    temporary.write(chunk)
        validation = validate_fits_file(temporary_path)
        if not validation.success:
            return CutoutResult(False, validation.reason, response_url, validation.detail)
        temporary_path.replace(destination)
        temporary_path = None
        return CutoutResult(True, url=response_url)
    except requests.RequestException as exc:
        return CutoutResult(False, f"legacy_http_{type(exc).__name__}", response_url, str(exc))
    except (OSError, EOFError, ValueError) as exc:
        return CutoutResult(False, "legacy_download_or_write_failed", response_url, f"{type(exc).__name__}: {exc}")
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
