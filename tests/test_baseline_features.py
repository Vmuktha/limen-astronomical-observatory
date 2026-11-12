import numpy as np

from backend.preprocessing.baseline_features import image_baseline_features, spectral_baseline_features


def test_spectral_features_keep_unavailable_snr_missing_not_zero():
    result = spectral_baseline_features([1, 2, 3, 4], [2., 3., 4., 5.], ivar=[0., 0., 0., 0.], mask=[0, 0, 0, 0.], bins=2)
    assert np.isnan(result["spec_snr_abs_p90"])
    assert result["spec_valid_pixel_fraction"] == 0.


def test_spectral_shape_uses_valid_unmasked_positive_ivar_pixels():
    result = spectral_baseline_features([1, 2, 3, 4], [1., 2., 30., 4.], ivar=[1., 1., 1., 1.], mask=[0, 0, 1, 0], bins=2)
    assert result["spec_valid_pixel_fraction"] == .75
    assert np.isfinite(result["spec_shape_bin_00"])


def test_image_features_use_real_bandwise_data_and_colours():
    image = np.stack([np.ones((8, 8)), np.ones((8, 8)) * 2, np.ones((8, 8)) * 4])
    result = image_baseline_features(image, "grz")
    assert result["img_g_median"] == 1.
    assert result["img_colour_g_minus_r"] == -1.
    assert result["img_colour_r_minus_z"] == -2.
