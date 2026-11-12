import numpy as np

from backend.discrepancy.residuals import residual_diagnostics
from backend.validation.zwarn import decode_zwarn
from experiments.baselines.evidence_audit import image_band_statistics, modality_relationship, spectrum_quality


def test_zwarn_decodes_individual_set_bits():
    flags = decode_zwarn((1 << 2) | (1 << 19))
    assert [flag["name"] for flag in flags] == ["SMALL_DELTA_CHI2", "BAD_PETALQA"]


def test_residual_diagnostics_excludes_masked_invalid_and_zero_ivar_pixels():
    diagnostics, residual, standardized = residual_diagnostics(
        [4000, 4001, 4002, 4003], [1., 10., np.nan, 5.], [1., 1., 1., 0.], [0, 1, 0, 0], [0., 0., 0., 0.],
    )
    assert diagnostics["residual_valid_pixels"] == 1
    assert diagnostics["high_standardized_residual_pixel_count"] == 0
    assert residual[0] == 1.
    assert np.isnan(standardized[1]) and np.isnan(standardized[2]) and np.isnan(standardized[3])


def test_residual_diagnostics_localizes_contiguous_high_residual_region():
    diagnostics, _, _ = residual_diagnostics([1,2,3,4], [0.,6.,7.,0.], [1.,1.,1.,1.], [0,0,0,0], [0.,0.,0.,0.])
    assert diagnostics["high_standardized_residual_pixel_count"] == 2
    assert diagnostics["discrepancy_regions"][0]["wavelength_start_angstrom"] == 2.
    assert diagnostics["discrepancy_regions"][0]["pixels"] == 2


def test_quality_retains_missing_snr_when_no_valid_pixels():
    result = spectrum_quality(np.array([1.,2.]),np.array([1.,2.]),np.array([0.,0.]),np.array([0,0]))
    assert result["valid_pixel_count"] == 0
    assert np.isnan(result["snr_median"])


def test_modality_relationship_is_descriptive():
    assert modality_relationship(1, 2) == "Both modalities unusual"
    assert modality_relationship(1, 21) == "Spectral-dominated"
    assert modality_relationship(22, 1) == "Image-dominated"
    assert modality_relationship(30, 30) == "Neither modality strongly unusual"


def test_image_band_statistics_reports_missing_pixels_per_band():
    image = np.array([[[1., np.nan]], [[2., 3.]], [[4., 5.]]])
    stats = image_band_statistics(image, "grz")
    assert stats["g"]["invalid_fraction"] == .5
    assert stats["r"]["median"] == 2.5
