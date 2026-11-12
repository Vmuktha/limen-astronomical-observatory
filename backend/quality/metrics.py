from __future__ import annotations

from typing import Any

import numpy as np


def finite_fraction(values: Any) -> float:
    array = np.asarray(values)
    return float(np.mean(np.isfinite(array))) if array.size else float("nan")


def robust_mad(values: Any) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if not array.size:
        return float("nan")
    return float(np.median(np.abs(array - np.median(array))))


def safe_quantile(values: Any, quantile: float) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    return float(np.quantile(array, quantile)) if array.size else float("nan")


def finite_median(values: Any) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    return float(np.median(array)) if array.size else float("nan")


def spectral_metrics(wavelength: Any, flux: Any, ivar: Any = None, mask: Any = None, model: Any = None) -> dict[str, float]:
    """Calculate per-spectrum statistics while keeping missing values as NaN."""
    wave = np.asarray(wavelength, dtype=float).ravel()
    values = np.asarray(flux, dtype=float).ravel()
    if wave.size != values.size:
        raise ValueError("wavelength and flux must have equal lengths")
    valid_wave_flux = np.isfinite(wave) & np.isfinite(values)
    result: dict[str, float] = {
        "spectral_samples": float(wave.size),
        "wavelength_min_angstrom": float(np.min(wave[valid_wave_flux])) if np.any(valid_wave_flux) else float("nan"),
        "wavelength_max_angstrom": float(np.max(wave[valid_wave_flux])) if np.any(valid_wave_flux) else float("nan"),
        "wavelength_spacing_median_angstrom": float(np.median(np.diff(wave[valid_wave_flux]))) if np.count_nonzero(valid_wave_flux) > 1 else float("nan"),
        "flux_mean": float(np.mean(values[valid_wave_flux])) if np.any(valid_wave_flux) else float("nan"),
        "flux_median": float(np.median(values[valid_wave_flux])) if np.any(valid_wave_flux) else float("nan"),
        "flux_mad": robust_mad(values),
        "flux_p05": safe_quantile(values, 0.05),
        "flux_p95": safe_quantile(values, 0.95),
        "flux_finite_fraction": finite_fraction(values),
        "invalid_spectral_fraction": float(1 - np.mean(valid_wave_flux)) if wave.size else float("nan"),
        "ivar_positive_fraction": float("nan"),
        "mask_nonzero_fraction": float("nan"),
        "snr_median": float("nan"),
        "snr_p90_abs": float("nan"),
        "model_finite_fraction": float("nan"),
        "residual_median": float("nan"),
        "residual_mad": float("nan"),
        "residual_rms": float("nan"),
    }
    valid_for_snr = valid_wave_flux.copy()
    if ivar is not None:
        inverse_variance = np.asarray(ivar, dtype=float).ravel()
        if inverse_variance.size == wave.size:
            positive_ivar = np.isfinite(inverse_variance) & (inverse_variance > 0)
            result["ivar_positive_fraction"] = float(np.mean(positive_ivar))
            valid_for_snr &= positive_ivar
    if mask is not None:
        pixel_mask = np.asarray(mask).ravel()
        if pixel_mask.size == wave.size:
            unmasked = pixel_mask == 0
            result["mask_nonzero_fraction"] = float(np.mean(~unmasked))
            valid_for_snr &= unmasked
    if ivar is not None and np.any(valid_for_snr):
        snr = values[valid_for_snr] * np.sqrt(np.asarray(ivar, dtype=float).ravel()[valid_for_snr])
        result["snr_median"] = float(np.median(snr))
        result["snr_p90_abs"] = safe_quantile(np.abs(snr), 0.90)
    if model is not None:
        model_values = np.asarray(model, dtype=float).ravel()
        if model_values.size == wave.size:
            valid_model = valid_wave_flux & np.isfinite(model_values)
            result["model_finite_fraction"] = float(np.mean(valid_model))
            if np.any(valid_model):
                residual = values[valid_model] - model_values[valid_model]
                result["residual_median"] = float(np.median(residual))
                result["residual_mad"] = robust_mad(residual)
                result["residual_rms"] = float(np.sqrt(np.mean(residual**2)))
    return result


def image_metrics(image: Any) -> dict[str, float]:
    """Compute lightweight image-quality and morphology proxies, not classifications."""
    data = np.asarray(image, dtype=float)
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    if data.ndim != 3:
        raise ValueError("image must have 2 or 3 dimensions")
    bands, height, width = data.shape
    finite = np.isfinite(data)
    yy, xx = np.indices((height, width))
    radius = np.sqrt((xx - (width - 1) / 2) ** 2 + (yy - (height - 1) / 2) ** 2)
    outer = radius >= 0.7 * radius.max()
    core = radius <= 0.25 * min(height, width)
    per_band_background = []
    per_band_noise = []
    snr_proxies = []
    concentrations = []
    asymmetries = []
    for plane in data:
        valid = np.isfinite(plane)
        background_values = plane[valid & outer]
        background = float(np.median(background_values)) if background_values.size else float("nan")
        noise = 1.4826 * robust_mad(background_values)
        per_band_background.append(background)
        per_band_noise.append(noise)
        core_values = plane[valid & core]
        core_signal = float(np.median(core_values) - background) if core_values.size and np.isfinite(background) else float("nan")
        snr_proxies.append(core_signal / noise if np.isfinite(noise) and noise > 0 else float("nan"))
        positive = np.where(valid, np.clip(plane - background, 0, None), 0)
        total = float(np.sum(positive))
        concentrations.append(float(np.sum(positive[core]) / total) if total > 0 else float("nan"))
        rotated = np.rot90(plane, 2)
        paired = valid & np.isfinite(rotated)
        denominator = float(np.sum(np.abs(plane[paired] - background))) if np.any(paired) else 0.0
        asymmetries.append(float(np.sum(np.abs(plane[paired] - rotated[paired])) / denominator) if denominator > 0 else float("nan"))
    return {
        "image_band_count": float(bands), "image_height_px": float(height), "image_width_px": float(width),
        "image_finite_fraction": float(np.mean(finite)), "image_invalid_fraction": float(1 - np.mean(finite)),
        "image_pixel_median": float(np.median(data[finite])) if np.any(finite) else float("nan"),
        "image_pixel_mad": robust_mad(data), "background_median": finite_median(per_band_background),
        "background_noise_mad": finite_median(per_band_noise), "image_snr_proxy_median": finite_median(snr_proxies),
        "concentration_proxy_median": finite_median(concentrations), "asymmetry_proxy_median": finite_median(asymmetries),
    }
