from __future__ import annotations

import math
from typing import Any

import numpy as np


def valid_coordinates(ra: Any, dec: Any) -> bool:
    """Return whether coordinates are finite degrees in ICRS bounds."""
    try:
        return math.isfinite(float(ra)) and math.isfinite(float(dec)) and 0 <= float(ra) < 360 and -90 <= float(dec) <= 90
    except (TypeError, ValueError):
        return False


def usable_spectrum(wavelength: Any, flux: Any, ivar: Any = None) -> tuple[bool, str | None]:
    """Validate arrays without treating a quality mask as a data substitute."""
    try:
        wave = np.asarray(wavelength, dtype=float).ravel()
        values = np.asarray(flux, dtype=float).ravel()
    except (TypeError, ValueError):
        return False, "non_numeric_spectral_array"
    if wave.size == 0 or values.size == 0:
        return False, "empty_spectral_array"
    if wave.size != values.size:
        return False, "wavelength_flux_length_mismatch"
    if np.count_nonzero(np.isfinite(wave) & np.isfinite(values)) < 2:
        return False, "fewer_than_two_finite_samples"
    if ivar is not None:
        try:
            if np.asarray(ivar).size not in (0, wave.size):
                return False, "ivar_length_mismatch"
        except TypeError:
            return False, "invalid_ivar"
    return True, None
