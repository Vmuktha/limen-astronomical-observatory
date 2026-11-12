from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class IngestionConfig:
    root: Path
    requested_count: int = 200
    batch_size: int = 25
    timeout_seconds: int = 45
    cutout_size_pixels: int = 64
    sparcl_url: str = "https://astrosparcl.datalab.noirlab.edu"
    legacy_cutout_url: str = "https://www.legacysurvey.org/viewer/fits-cutout"

    @property
    def raw_spectra_dir(self) -> Path:
        return self.root / "data/raw/desi_dr1/spectra"

    @property
    def raw_images_dir(self) -> Path:
        return self.root / "data/raw/legacy_survey_dr10/images"

    @property
    def metadata_dir(self) -> Path:
        return self.root / "data/metadata"

    @classmethod
    def from_environment(cls, root: Path, requested_count: int = 200) -> "IngestionConfig":
        return cls(
            root=root,
            requested_count=requested_count,
            batch_size=int(os.getenv("LIMEN_BATCH_SIZE", "25")),
            timeout_seconds=int(os.getenv("LIMEN_REQUEST_TIMEOUT_SECONDS", "45")),
            cutout_size_pixels=int(os.getenv("LIMEN_CUTOUT_SIZE_PIXELS", "64")),
            sparcl_url=os.getenv("LIMEN_SPARCL_URL", cls.sparcl_url),
            legacy_cutout_url=os.getenv("LIMEN_LEGACY_CUTOUT_URL", cls.legacy_cutout_url),
        )
