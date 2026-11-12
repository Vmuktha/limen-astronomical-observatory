from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler


@dataclass
class BaselineResult:
    scores: np.ndarray
    ranks: np.ndarray
    feature_names: list[str]
    matrix: np.ndarray
    model: IsolationForest


def _usable_columns(matrix: np.ndarray, names: list[str]) -> tuple[np.ndarray, list[str]]:
    usable = []
    for index in range(matrix.shape[1]):
        values = matrix[:, index]
        finite = values[np.isfinite(values)]
        if finite.size >= 2 and not np.allclose(finite, finite[0]):
            usable.append(index)
    return matrix[:, usable], [names[index] for index in usable]


def fit_isolation_forest(matrix: np.ndarray, names: list[str], random_state: int = 42, n_estimators: int = 300, contamination: float = 0.10) -> BaselineResult:
    """Robust-scale finite varying features and return higher-is-more-unusual scores."""
    filtered, used_names = _usable_columns(np.asarray(matrix, dtype=float), names)
    if not used_names:
        raise ValueError("no finite non-constant features available")
    transformed = SimpleImputer(strategy="median").fit_transform(filtered)
    transformed = RobustScaler().fit_transform(transformed)
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=random_state, n_jobs=1)
    model.fit(transformed)
    scores = -model.score_samples(transformed)
    ranks = np.empty(scores.size, dtype=int)
    ranks[np.argsort(-scores, kind="stable")] = np.arange(1, scores.size + 1)
    return BaselineResult(scores=scores, ranks=ranks, feature_names=used_names, matrix=transformed, model=model)


def fit_multimodal(spectral_matrix: np.ndarray, spectral_names: list[str], image_matrix: np.ndarray, image_names: list[str], **kwargs: Any) -> BaselineResult:
    """Scale each modality independently and equalize block norm by dimension."""
    spectral, used_spectral = _usable_columns(np.asarray(spectral_matrix, dtype=float), spectral_names)
    image, used_image = _usable_columns(np.asarray(image_matrix, dtype=float), image_names)
    if not used_spectral or not used_image:
        raise ValueError("both modalities need finite non-constant features")
    spectral = RobustScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(spectral)) / np.sqrt(spectral.shape[1])
    image = RobustScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(image)) / np.sqrt(image.shape[1])
    return fit_isolation_forest(np.column_stack((spectral, image)), [f"spectral:{name}" for name in used_spectral] + [f"image:{name}" for name in used_image], **kwargs)


def top_overlap(*ranks: np.ndarray, top_n: int = 20) -> dict[str, int]:
    selections = [set(np.flatnonzero(rank <= top_n).tolist()) for rank in ranks]
    return {"spectral_image": len(selections[0] & selections[1]), "spectral_multimodal": len(selections[0] & selections[2]), "image_multimodal": len(selections[1] & selections[2]), "all_three": len(set.intersection(*selections))}
