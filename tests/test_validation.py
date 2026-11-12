import numpy as np

from backend.ingestion.validation import usable_spectrum, valid_coordinates


def test_coordinates_accept_valid_icrs_degrees():
    assert valid_coordinates(359.999, -90)


def test_coordinates_reject_non_finite_and_out_of_range_values():
    assert not valid_coordinates(float("nan"), 1)
    assert not valid_coordinates(360, 1)
    assert not valid_coordinates(1, -91)


def test_spectrum_requires_aligned_finite_arrays():
    assert usable_spectrum(np.array([4000, 4001]), np.array([1.0, 2.0])) == (True, None)
    assert usable_spectrum([4000], [1.0, 2.0]) == (False, "wavelength_flux_length_mismatch")
    assert usable_spectrum([np.nan, np.nan], [1.0, 2.0]) == (False, "fewer_than_two_finite_samples")
