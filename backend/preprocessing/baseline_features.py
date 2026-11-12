from __future__ import annotations

from typing import Any

import numpy as np

from backend.quality.metrics import finite_median, robust_mad, safe_quantile


def _valid_spectral_pixels(flux: np.ndarray, ivar: np.ndarray | None, mask: np.ndarray | None) -> np.ndarray:
    valid = np.isfinite(flux)
    if ivar is not None and ivar.size == flux.size:
        valid &= np.isfinite(ivar) & (ivar > 0)
    if mask is not None and mask.size == flux.size:
        valid &= mask == 0
    return valid


def spectral_baseline_features(wavelength: Any, flux: Any, ivar: Any = None, mask: Any = None, model: Any = None, bins: int = 24) -> dict[str, float]:
    """Compact quality-aware features from a real spectrum; missing stays NaN."""
    wave, values = np.asarray(wavelength, dtype=float).ravel(), np.asarray(flux, dtype=float).ravel()
    if wave.size != values.size:
        raise ValueError("wavelength and flux lengths differ")
    inverse_variance = np.asarray(ivar, dtype=float).ravel() if ivar is not None else None
    pixel_mask = np.asarray(mask).ravel() if mask is not None else None
    valid = _valid_spectral_pixels(values, inverse_variance, pixel_mask)
    features = {"spec_valid_pixel_fraction": float(np.mean(valid)) if values.size else float("nan"), "spec_flux_mad_valid": robust_mad(values[valid]), "spec_flux_p95_p05_valid": safe_quantile(values[valid], .95) - safe_quantile(values[valid], .05), "spec_structure_mad_diff": robust_mad(np.diff(values[valid])) if np.count_nonzero(valid) > 2 else float("nan")}
    continuum = finite_median(values[valid])
    if np.isfinite(continuum) and continuum != 0:
        normalized = values / continuum
        for index, segment in enumerate(np.array_split(np.arange(values.size), bins)):
            segment_valid = valid[segment]
            features[f"spec_shape_bin_{index:02d}"] = finite_median(normalized[segment][segment_valid]) if np.any(segment_valid) else float("nan")
    else:
        features.update({f"spec_shape_bin_{index:02d}": float("nan") for index in range(bins)})
    if inverse_variance is not None and inverse_variance.size == values.size and np.any(valid):
        snr = values[valid] * np.sqrt(inverse_variance[valid])
        features["spec_snr_abs_p90"] = safe_quantile(np.abs(snr), .90)
    else:
        features["spec_snr_abs_p90"] = float("nan")
    model_values = np.asarray(model, dtype=float).ravel() if model is not None else None
    if model_values is not None and model_values.size == values.size:
        model_valid = valid & np.isfinite(model_values)
        residual = values[model_valid] - model_values[model_valid]
        features["spec_model_residual_mad"] = robust_mad(residual)
        features["spec_model_residual_rms"] = float(np.sqrt(np.mean(residual ** 2))) if residual.size else float("nan")
    else:
        features["spec_model_residual_mad"] = float("nan")
        features["spec_model_residual_rms"] = float("nan")
    return features


def image_baseline_features(image: Any, bands: str = "grz") -> dict[str, float]:
    """Per-band pixel and quality proxies; these are not morphology classes."""
    data = np.asarray(image, dtype=float)
    if data.ndim != 3:
        raise ValueError("expected a bands x height x width image")
    names = list(bands) if len(bands) == data.shape[0] else [f"band{index}" for index in range(data.shape[0])]
    features: dict[str, float] = {}
    band_medians = []
    for name, plane in zip(names, data):
        finite = plane[np.isfinite(plane)]
        features[f"img_{name}_finite_fraction"] = float(np.mean(np.isfinite(plane)))
        features[f"img_{name}_median"] = finite_median(finite)
        features[f"img_{name}_mad"] = robust_mad(finite)
        features[f"img_{name}_contrast_p95_p05"] = safe_quantile(finite, .95) - safe_quantile(finite, .05)
        band_medians.append(features[f"img_{name}_median"])
    for index in range(len(names) - 1):
        left, right = band_medians[index], band_medians[index + 1]
        features[f"img_colour_{names[index]}_minus_{names[index + 1]}"] = left - right if np.isfinite(left) and np.isfinite(right) else float("nan")
    # Reuse audit-consistent proxy definitions where possible, per band then aggregate.
    height, width = data.shape[-2:]
    yy, xx = np.indices((height, width))
    radius = np.sqrt((xx - (width - 1) / 2) ** 2 + (yy - (height - 1) / 2) ** 2)
    outer, core = radius >= .7 * radius.max(), radius <= .25 * min(height, width)
    concentrations, asymmetries, snr_proxies = [], [], []
    for plane in data:
        valid = np.isfinite(plane)
        background = finite_median(plane[valid & outer])
        noise = 1.4826 * robust_mad(plane[valid & outer])
        core_signal = finite_median(plane[valid & core]) - background
        snr_proxies.append(core_signal / noise if np.isfinite(noise) and noise > 0 else float("nan"))
        positive = np.where(valid, np.clip(plane - background, 0, None), 0)
        total = float(positive.sum())
        concentrations.append(float(positive[core].sum() / total) if total > 0 else float("nan"))
        rotated, paired = np.rot90(plane, 2), valid & np.isfinite(np.rot90(plane, 2))
        denom = float(np.abs(plane[paired] - background).sum()) if np.any(paired) else 0.
        asymmetries.append(float(np.abs(plane[paired] - rotated[paired]).sum() / denom) if denom > 0 else float("nan"))
    features.update({"img_snr_proxy_median": finite_median(snr_proxies), "img_concentration_proxy_median": finite_median(concentrations), "img_asymmetry_proxy_median": finite_median(asymmetries)})
    return features
