from __future__ import annotations

from typing import Any
import math
import numpy as np


RULES = {
    "insufficient_evidence": "Spectral valid-pixel fraction is below 0.50, S/N is unavailable, or image invalid-pixel fraction is at least 0.25.",
    "multimodal_agreement": "Both original Phase 3 spectral and image ranks are in their top 20 and evidence is not insufficient.",
    "evidence_sensitive": "For a modality that originally ranked in the top 20, fewer than half of its applicable controlled degradation runs retain top-20 membership, or median absolute rank displacement is at least 25. This is refit-pipeline sensitivity, not a quality score.",
    "spectral_candidate": "Original Phase 3 spectral rank is in the top 20, with sufficient evidence and without the evidence-sensitive rule.",
    "image_candidate": "Original Phase 3 image rank is in the top 20, with sufficient evidence and without the evidence-sensitive rule.",
}


def finite(value: Any) -> bool:
    try: return math.isfinite(float(value))
    except (TypeError, ValueError): return False


def robustness_summary(records: list[dict[str, Any]], modality: str) -> dict[str, Any]:
    relevant = [record for record in records if record["mode"] == modality]
    if not relevant:
        return {"availability": "unavailable", "runs": 0}
    displacements = np.asarray([abs(int(record["rank_displacement"])) for record in relevant], dtype=float)
    retained = np.asarray([int(record["degraded_rank"]) <= 20 for record in relevant])
    entered = sum(str(record["entered_top20_due_to_degradation"]).lower() == "true" for record in relevant)
    return {"availability": "available", "runs": int(len(relevant)), "median_absolute_rank_displacement": float(np.median(displacements)), "max_absolute_rank_displacement": int(np.max(displacements)), "top20_retention_fraction": float(np.mean(retained)), "entered_top20_due_to_degradation_count": int(entered), "scenarios": sorted(set(record["scenario"] for record in relevant)), "interpretation": "controlled refit-pipeline sensitivity; not frozen-model robustness or scientific accuracy"}


def triage(dossier: dict[str, Any], spectral_robustness: dict[str, Any], image_robustness: dict[str, Any], multimodal_robustness: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    ranks = dossier["phase_3_scores_and_ranks"]; quality = dossier["spectral_quality"]; image = dossier["image_evidence"]["quality_and_proxy_metrics"]
    insufficient = quality["valid_pixel_fraction"] < .50 or not finite(quality["snr_abs_p90"]) or image["image_invalid_fraction"] >= .25
    spectral_top, image_top = ranks["spectral_rank"] <= 20, ranks["image_rank"] <= 20
    fragile = (spectral_top and (spectral_robustness["top20_retention_fraction"] < .5 or spectral_robustness["median_absolute_rank_displacement"] >= 25)) or (image_top and (image_robustness["top20_retention_fraction"] < .5 or image_robustness["median_absolute_rank_displacement"] >= 25))
    reasons=[]; uncertainties=[]
    if insufficient:
        reasons.append("Required spectral or image quality evidence is unavailable or below the explicit minimum.")
        return "Insufficient evidence", reasons, ["No anomaly interpretation should be made until the unavailable evidence is resolved."]
    if spectral_top and image_top:
        reasons.append("Both original single-modality rankings are in the Phase 3 top 20.")
        if fragile: uncertainties.append("At least one contributing modality is sensitive under controlled refit-pipeline degradation.")
        return "Multimodal agreement: unusual in both modalities", reasons, uncertainties
    if fragile:
        reasons.append("A top-20 contributing modality has low controlled top-20 retention or a large median rank displacement.")
        return "Evidence-sensitive candidate", reasons, ["This describes simulation/refit sensitivity, not scientific accuracy or invalidity."]
    if spectral_top:
        reasons.append("Original Phase 3 spectral rank is in the top 20 while image rank is not.")
        return "Spectral investigation candidate", reasons, ["Cross-modal agreement is limited; inspect masks, S/N, ZWARN, and model discrepancy context."]
    if image_top:
        reasons.append("Original Phase 3 image rank is in the top 20 while spectral rank is not.")
        return "Image investigation candidate", reasons, ["Cross-modal agreement is limited; image descriptors are proxies, not morphology classifications."]
    return "Neither modality strongly unusual", ["No single-modality top-20 evidence."], ["Included only if selection rules are changed."]
