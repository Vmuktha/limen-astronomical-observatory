from __future__ import annotations

from typing import Any


DESI_DR1 = "DESI-DR1"
RETRIEVAL_FIELDS = ["specid", "sparcl_id", "targetid", "ra", "dec", "spectype", "specprimary", "redshift", "redshift_err", "redshift_warning", "wavelength", "flux", "ivar", "mask", "model", "data_release"]


def record_value(record: Any, field: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def find_galaxy_candidates(client: Any, limit: int) -> list[Any]:
    """Discover public DESI DR1 records classified by the catalogue as GALAXY."""
    found = client.find(
        outfields=["specid", "sparcl_id", "targetid", "ra", "dec", "spectype", "specprimary", "redshift", "redshift_warning", "data_release"],
        constraints={"spectype": ["GALAXY"], "data_release": [DESI_DR1]},
        limit=limit,
    )
    return list(found.records)


def retrieve_records(client: Any, specids: list[Any]) -> list[Any]:
    if not specids:
        return []
    response = client.retrieve_by_specid(specids, include=RETRIEVAL_FIELDS, dataset_list=[DESI_DR1], limit=len(specids), units=False)
    return list(response.records)
