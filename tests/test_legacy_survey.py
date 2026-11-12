from io import BytesIO
from pathlib import Path
import tempfile

import numpy as np
import requests
from astropy.io import fits

from backend.ingestion import legacy_survey
from backend.ingestion.legacy_survey import fetch_dr10_cutout, validate_fits_file


def valid_fits_bytes() -> bytes:
    stream = BytesIO()
    fits.PrimaryHDU(np.ones((3, 4, 4), dtype=np.float32)).writeto(stream)
    return stream.getvalue()


class FakeResponse:
    url = "https://example.test/cutout"

    def __init__(self, chunks):
        self.chunks = chunks

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


def test_cutout_rejects_invalid_coordinates_without_request(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.ingestion.legacy_survey.requests.get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    result = fetch_dr10_cutout(ra=400, dec=0, destination=tmp_path / "x.fits", endpoint="https://example.test", size=64, timeout=1)
    assert (result.success, result.reason, result.url) == (False, "invalid_coordinates", None)


def test_cutout_writes_and_validates_fits_response(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.ingestion.legacy_survey.requests.get", lambda *args, **kwargs: FakeResponse([valid_fits_bytes()]))
    destination = tmp_path / "nested" / "x.fits"
    result = fetch_dr10_cutout(ra=12, dec=-2, destination=destination, endpoint="https://example.test", size=64, timeout=1)
    assert result.success and result.reason is None and result.url == FakeResponse.url
    assert validate_fits_file(destination).success


def test_cutout_records_network_failure(monkeypatch, tmp_path: Path):
    def fail(*args, **kwargs):
        raise requests.Timeout("timeout")
    monkeypatch.setattr("backend.ingestion.legacy_survey.requests.get", fail)
    result = fetch_dr10_cutout(ra=12, dec=-2, destination=tmp_path / "x.fits", endpoint="https://example.test", size=64, timeout=1)
    assert (result.success, result.reason) == (False, "legacy_http_Timeout")


def test_invalid_cached_fits_is_detected(tmp_path: Path):
    corrupt = tmp_path / "corrupt.fits"
    corrupt.write_bytes(b"SIMPLE" + b" " * 16)
    result = validate_fits_file(corrupt)
    assert not result.success
    assert result.reason == "fits_validation_failed"


def test_unique_temporary_files_prevent_destination_part_collisions(monkeypatch, tmp_path: Path):
    created = []
    original = tempfile.NamedTemporaryFile

    def named_temporary_file(*args, **kwargs):
        handle = original(*args, **kwargs)
        created.append(Path(handle.name))
        return handle

    monkeypatch.setattr("backend.ingestion.legacy_survey.tempfile.NamedTemporaryFile", named_temporary_file)
    monkeypatch.setattr("backend.ingestion.legacy_survey.requests.get", lambda *args, **kwargs: FakeResponse([valid_fits_bytes()]))
    destination = tmp_path / "same-destination.fits"
    assert fetch_dr10_cutout(ra=12, dec=-2, destination=destination, endpoint="https://example.test", size=64, timeout=1).success
    assert fetch_dr10_cutout(ra=12, dec=-2, destination=destination, endpoint="https://example.test", size=64, timeout=1).success
    assert len(created) == 2 and created[0] != created[1]
    assert not list(tmp_path.glob("*.fits.part"))


def test_interrupted_download_returns_failure_and_removes_tempfile(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("backend.ingestion.legacy_survey.requests.get", lambda *args, **kwargs: FakeResponse([valid_fits_bytes()[:100], requests.exceptions.ChunkedEncodingError("interrupted")]))
    destination = tmp_path / "x.fits"
    result = fetch_dr10_cutout(ra=12, dec=-2, destination=destination, endpoint="https://example.test", size=64, timeout=1)
    assert not result.success
    assert result.reason == "legacy_http_ChunkedEncodingError"
    assert not destination.exists()
    assert not list(tmp_path.glob("*.fits.part"))
