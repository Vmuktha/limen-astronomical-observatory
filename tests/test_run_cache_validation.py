from pathlib import Path
from types import SimpleNamespace

import numpy as np

from backend.ingestion import run as ingestion_run
from backend.ingestion.config import IngestionConfig
from backend.ingestion.legacy_survey import CutoutResult


def test_run_retries_corrupt_cached_image(monkeypatch, tmp_path: Path):
    candidate = SimpleNamespace(
        specid=123,
        targetid=456,
        sparcl_id="test-id",
        ra=12.0,
        dec=-2.0,
        spectype="GALAXY",
        specprimary=True,
        redshift=0.1,
        redshift_warning=0,
        data_release="DESI-DR1",
    )

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def find(self, **kwargs):
            return SimpleNamespace(records=[candidate])

    monkeypatch.setattr("sparcl.client.SparclClient", FakeClient)
    config = IngestionConfig(root=tmp_path, requested_count=1)
    config.raw_spectra_dir.mkdir(parents=True)
    np.savez_compressed(config.raw_spectra_dir / "123.npz", wavelength=[4000.0, 4001.0], flux=[1.0, 2.0], ivar=[1.0, 1.0])
    config.raw_images_dir.mkdir(parents=True)
    (config.raw_images_dir / "123.fits").write_bytes(b"not a FITS file")
    called = []

    def fake_fetch(**kwargs):
        called.append(kwargs["destination"])
        return CutoutResult(False, "legacy_http_Timeout", detail="test interruption")

    monkeypatch.setattr(ingestion_run, "fetch_dr10_cutout", fake_fetch)
    report = ingestion_run.run(config)

    assert called == [config.raw_images_dir / "123.fits"]
    observation = report["observations"][0]
    assert observation["image_status"] == "unavailable"
    assert observation["image_failure_reason"] == "legacy_http_Timeout"
    assert observation["image_failure_detail"] == "test interruption"
