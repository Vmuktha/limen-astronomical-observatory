import numpy as np

from backend.anomaly.baselines import fit_isolation_forest, fit_multimodal


def test_scoring_excludes_constant_columns_and_ranks_all_rows():
    matrix = np.array([[0., 1., 7.], [0., 2., 7.], [0., 3., 7.], [10., 4., 7.]])
    result = fit_isolation_forest(matrix, ["varying", "other", "constant"], n_estimators=20, random_state=3)
    assert result.feature_names == ["varying", "other"]
    assert sorted(result.ranks.tolist()) == [1, 2, 3, 4]
    assert np.all(np.isfinite(result.scores))


def test_multimodal_feature_block_equalization_and_missing_imputation():
    spectral = np.array([[1., np.nan], [2., 2.], [3., 3.], [10., 4.]])
    image = np.array([[1., 1.], [2., 1.], [3., 1.], [4., 10.]])
    result = fit_multimodal(spectral, ["s1", "s2"], image, ["i1", "i2"], n_estimators=20, random_state=3)
    assert len(result.feature_names) == 4
    assert np.all(np.isfinite(result.matrix))
