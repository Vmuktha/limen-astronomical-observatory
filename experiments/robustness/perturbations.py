from __future__ import annotations

from typing import Any
import numpy as np
from scipy.ndimage import gaussian_filter

from backend.quality.metrics import robust_mad


def degrade_spectrum_noise(flux: Any, ivar: Any, mask: Any, alpha: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Add incremental Gaussian noise and reduce inverse variance by alpha²."""
    if alpha < 1: raise ValueError("alpha must be >= 1")
    values, inverse, pixel_mask = np.asarray(flux, dtype=float).copy(), np.asarray(ivar, dtype=float).copy(), np.asarray(mask)
    valid = np.isfinite(values) & np.isfinite(inverse) & (inverse > 0) & (pixel_mask == 0)
    if alpha > 1:
        values[valid] += rng.normal(0, np.sqrt((alpha**2 - 1) / inverse[valid]))
        inverse[valid] /= alpha**2
    return values, inverse


def contiguous_spectral_mask(wavelength: Any, mask: Any, fraction: float, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, float]]:
    wave, output = np.asarray(wavelength), np.asarray(mask).copy()
    length = max(1, int(round(wave.size * fraction))); start = int(rng.integers(0, wave.size - length + 1)); output[start:start + length] |= 1
    return output, {"start_angstrom": float(wave[start]), "end_angstrom": float(wave[start + length - 1]), "fraction": float(length / wave.size)}


def reduced_spectral_coverage(wavelength: Any, arrays: tuple[np.ndarray, ...], fraction: float, side: str) -> tuple[np.ndarray, ...]:
    wave = np.asarray(wavelength); length = max(2, int(round(wave.size * (1 - fraction))))
    selector = slice(0, length) if side == "red" else slice(wave.size - length, wave.size)
    return tuple(np.asarray(array)[selector].copy() for array in arrays)


def background_noise(image: Any) -> np.ndarray:
    data = np.asarray(image, dtype=float); h,w=data.shape[-2:]; yy,xx=np.indices((h,w)); outer=np.sqrt((xx-(w-1)/2)**2+(yy-(h-1)/2)**2)>=.7*np.sqrt(((w-1)/2)**2+((h-1)/2)**2)
    return np.asarray([1.4826*robust_mad(plane[np.isfinite(plane)&outer]) for plane in data])


def degrade_image_noise(image: Any, multiplier: float, rng: np.random.Generator) -> np.ndarray:
    data=np.asarray(image,dtype=float).copy(); noise=background_noise(data)
    for index, sigma in enumerate(noise):
        valid=np.isfinite(data[index])
        if np.isfinite(sigma) and sigma > 0: data[index,valid]+=rng.normal(0,multiplier*sigma,valid.sum())
    return data


def blur_image(image: Any, sigma: float) -> np.ndarray:
    data=np.asarray(image,dtype=float).copy()
    for index, plane in enumerate(data):
        valid=np.isfinite(plane); fill=np.nanmedian(plane[valid]) if valid.any() else 0.; filtered=gaussian_filter(np.where(valid,plane,fill),sigma=sigma); data[index,valid]=filtered[valid]
    return data


def mask_image_block(image: Any, fraction: float, rng: np.random.Generator) -> tuple[np.ndarray, dict[str,int]]:
    data=np.asarray(image,dtype=float).copy(); h,w=data.shape[-2:]; side=max(1,int(round(min(h,w)*np.sqrt(fraction)))); y=int(rng.integers(0,h-side+1)); x=int(rng.integers(0,w-side+1)); data[:,y:y+side,x:x+side]=np.nan
    return data,{"x":x,"y":y,"width":side,"height":side}
