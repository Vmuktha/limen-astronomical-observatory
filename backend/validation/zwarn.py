from __future__ import annotations

# Source: DESI Data Model, "Bit Masks in DESI", ZWARN definitions.
ZWARN_BITS = {0: ("SKY", "sky fiber"), 1: ("LITTLE_COVERAGE", "too little wavelength coverage"), 2: ("SMALL_DELTA_CHI2", "best and second-best fit chi-squared values are too close"), 3: ("NEGATIVE_MODEL", "synthetic spectrum is negative"), 4: ("MANY_OUTLIERS", "more than 5% of points are over 5 sigma from the best model"), 5: ("Z_FITLIMIT", "chi-squared minimum is at redshift-fit limit"), 6: ("NEGATIVE_EMISSION", "negative QSO emission-line condition"), 7: ("UNPLUGGED", "fiber unplugged or broken"), 8: ("BAD_TARGET", "catastrophically bad targeting data"), 9: ("NODATA", "no data for fiber"), 10: ("BAD_MINFIT", "bad parabola fit to chi-squared minimum"), 11: ("POORDATA", "poor input data quality"), 16: ("LOW_DEL_CHI2", "low DELTACHI2 for DESI SV3 target"), 17: ("LOW_DEL_CHI2_BGS", "low DELTACHI2 for DESI SV3 BGS target"), 18: ("BAD_SPECQA", "spectrum-level QA rejection"), 19: ("BAD_PETALQA", "petal-level QA rejection")}


def decode_zwarn(value: int | None) -> list[dict[str, object]]:
    if value is None:
        return []
    integer = int(value)
    return [{"bit": bit, "name": name, "description": description} for bit, (name, description) in ZWARN_BITS.items() if integer & (1 << bit)]
