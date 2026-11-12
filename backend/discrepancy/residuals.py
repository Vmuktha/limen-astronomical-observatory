from __future__ import annotations

from typing import Any
import numpy as np

from backend.quality.metrics import robust_mad, safe_quantile


def residual_diagnostics(wavelength: Any, flux: Any, ivar: Any, mask: Any, model: Any, threshold: float = 5.0) -> tuple[dict[str, float | int | list[dict[str, float]]], np.ndarray, np.ndarray]:
    """Return diagnostics and standardized residuals only where ivar/mask permit."""
    wave, observed, inverse_variance, pixel_mask, fitted = (np.asarray(item).ravel() for item in (wavelength, flux, ivar, mask, model))
    if not (wave.size == observed.size == inverse_variance.size == pixel_mask.size == fitted.size):
        raise ValueError("residual inputs must have equal lengths")
    valid = np.isfinite(wave) & np.isfinite(observed) & np.isfinite(fitted) & np.isfinite(inverse_variance) & (inverse_variance > 0) & (pixel_mask == 0)
    residual = np.full(wave.size, np.nan); standardized = np.full(wave.size, np.nan)
    residual[valid] = observed[valid] - fitted[valid]
    standardized[valid] = residual[valid] * np.sqrt(inverse_variance[valid])
    high = valid & (np.abs(standardized) >= threshold)
    regions = []
    indices = np.flatnonzero(high)
    for group in np.split(indices, np.where(np.diff(indices) > 1)[0] + 1) if indices.size else []:
        regions.append({"wavelength_start_angstrom": float(wave[group[0]]), "wavelength_end_angstrom": float(wave[group[-1]]), "pixels": int(group.size), "max_abs_standardized_residual": float(np.nanmax(np.abs(standardized[group])))})
    diagnostics = {"residual_valid_pixels": int(valid.sum()), "residual_valid_fraction": float(valid.mean()), "residual_median": float(np.nanmedian(residual)) if valid.any() else float("nan"), "residual_mad": robust_mad(residual), "residual_rms": float(np.sqrt(np.nanmean(residual ** 2))) if valid.any() else float("nan"), "standardized_residual_abs_p95": safe_quantile(np.abs(standardized), .95), "standardized_residual_abs_p99": safe_quantile(np.abs(standardized), .99), "high_standardized_residual_pixel_count": int(high.sum()), "discrepancy_regions": regions}
    return diagnostics, residual, standardized
