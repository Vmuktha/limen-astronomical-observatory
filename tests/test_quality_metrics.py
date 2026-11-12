import numpy as np
import pytest

from backend.quality.metrics import image_metrics, spectral_metrics


def test_spectral_metrics_do_not_treat_missing_values_as_zero():
    metrics = spectral_metrics(
        wavelength=[4000.0, 4001.0, np.nan], flux=[2.0, np.nan, 100.0],
        ivar=[4.0, 4.0, 4.0], mask=[0, 0, 0], model=[1.0, 1.0, 1.0],
    )
    assert metrics["flux_median"] == 2.0  # only paired finite wavelength/flux samples, no inserted zero
    assert metrics["invalid_spectral_fraction"] == pytest.approx(2 / 3)
    assert metrics["snr_median"] == 4.0
    assert metrics["model_finite_fraction"] == pytest.approx(1 / 3)


def test_spectral_metrics_leave_missing_optional_arrays_as_nan():
    metrics = spectral_metrics([4000, 4001], [1.0, 2.0])
    assert np.isnan(metrics["ivar_positive_fraction"])
    assert np.isnan(metrics["snr_median"])
    assert np.isnan(metrics["model_finite_fraction"])


def test_image_metrics_preserve_nonfinite_pixels_and_report_shape():
    image = np.ones((3, 8, 8), dtype=float)
    image[0, 0, 0] = np.nan
    metrics = image_metrics(image)
    assert metrics["image_band_count"] == 3
    assert metrics["image_height_px"] == 8
    assert metrics["image_invalid_fraction"] == pytest.approx(1 / (3 * 8 * 8))


def test_image_metrics_rejects_non_image_dimensions():
    with pytest.raises(ValueError, match="2 or 3 dimensions"):
        image_metrics(np.ones(4))
