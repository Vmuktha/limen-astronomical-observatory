from backend.prioritization.triage import robustness_summary, triage


def _dossier(spectral_rank=5, image_rank=30, valid=.9, snr=4., invalid=.0):
    return {"phase_3_scores_and_ranks":{"spectral_rank":spectral_rank,"image_rank":image_rank},"spectral_quality":{"valid_pixel_fraction":valid,"snr_abs_p90":snr},"image_evidence":{"quality_and_proxy_metrics":{"image_invalid_fraction":invalid}}}


def _robust(retention=1., displacement=2.):
    return {"top20_retention_fraction":retention,"median_absolute_rank_displacement":displacement}


def test_triage_multimodal_agreement_precedes_evidence_sensitivity():
    category,reasons,_=triage(_dossier(2,3),_robust(.1,30),_robust(.1,30),_robust())
    assert category == "Multimodal agreement: unusual in both modalities"
    assert reasons


def test_triage_identifies_evidence_sensitive_single_modality_candidate():
    category,_,_=triage(_dossier(3,50),_robust(.4,10),_robust(),_robust())
    assert category == "Evidence-sensitive candidate"


def test_triage_preserves_missing_quality_as_insufficient():
    category,_,_=triage(_dossier(3,50,snr=None),_robust(),_robust(),_robust())
    assert category == "Insufficient evidence"


def test_robustness_summary_reports_retention_and_does_not_score():
    rows=[{"mode":"spectral","rank_displacement":"-4","degraded_rank":"19","entered_top20_due_to_degradation":"False","scenario":"spectral_noise"},{"mode":"spectral","rank_displacement":"10","degraded_rank":"30","entered_top20_due_to_degradation":"False","scenario":"spectral_mask"}]
    summary=robustness_summary(rows,"spectral")
    assert summary["top20_retention_fraction"] == .5
    assert summary["median_absolute_rank_displacement"] == 7.
    assert "score" not in summary
